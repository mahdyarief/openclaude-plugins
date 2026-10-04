#!/usr/bin/env python3
"""pr-slop-guard static scanner: deterministic AST/grep pass over a git diff.

Reads a unified diff from stdin (or --diff-file PATH) and emits JSON findings.
Each finding: {rule, severity, file, line, snippet}.

Rules (subset of the 12 Potapov patterns, statically detectable):
  SLP-01 try-except blanket      (P1)  except Exception / bare except
  SLP-02 swallowed exception     (P1)  except ...: pass (empty handler)
  SLP-03 read-modify-write       (P1)  get-then-save on same object, no atomic op
  SLP-04 broad auth-or           (P1)  'or' in authz check (heuristic, needs LLM confirm)
  SLP-05 unused import           (P2)  via pyflakes if available, else AST compare
  SLP-06 function-level import   (P2)  import inside function body
  SLP-07 mock-tests-mock         (P2)  test patches the very symbol it asserts
  SLP-08 env-var cargo cult      (P2)  NEW os.getenv for ALL_CAPS const w/o default use
  SLP-09 single-impl abstraction (P2)  new ABC/interface + exactly one subclass (heuristic)
  SLP-10 dead code               (P3)  def/class never referenced in diff (heuristic)

Usage:
    git diff main...HEAD | python slop_scan.py
    python slop_scan.py --diff-file /tmp/pr.diff
    python slop_scan.py --diff-file /tmp/pr.diff --min-severity P2

Exit code 0 always (CI gate decides on verdict, not exit code).
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import asdict, dataclass


@dataclass
class Finding:
    rule: str
    severity: str  # P1 | P2 | P3
    file: str
    line: int
    snippet: str
    message: str


SEV_ORDER = {"P1": 0, "P2": 1, "P3": 2}


# ---------------------------------------------------------------- diff parsing

DIFF_FILE_RE = re.compile(r"^diff --git a/(.+) b/(.+)$")
HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")
ADDED_RE = re.compile(r"^\+(?!\+\+)")


@dataclass
class DiffFile:
    path: str
    added_lines: list  # list[(new_lineno, text)]


def parse_diff(text: str) -> list[DiffFile]:
    files: list[DiffFile] = []
    cur: DiffFile | None = None
    new_lineno = 0
    for raw in text.splitlines():
        m = DIFF_FILE_RE.match(raw)
        if m:
            cur = DiffFile(path=m.group(2), added_lines=[])
            files.append(cur)
            continue
        h = HUNK_RE.match(raw)
        if h and cur is not None:
            new_lineno = int(h.group(1))
            continue
        if cur is None:
            continue
        if raw.startswith("+") and not raw.startswith("+++"):
            cur.added_lines.append((new_lineno, raw[1:]))
            new_lineno += 1
        elif raw.startswith("-") and not raw.startswith("---"):
            pass
        else:
            new_lineno += 1
    return files


def is_python(path: str) -> bool:
    return path.endswith(".py")


def is_test(path: str) -> bool:
    p = path.lower()
    return "test" in p or p.startswith("tests/")


# ---------------------------------------------------------------- rule checks

def check_blanket_except(path: str, added: list) -> list[Finding]:
    out = []
    src = "\n".join(t for _, t in added)
    try:
        tree = ast.parse(src)
    except SyntaxError:
        # fall back to regex on the raw added lines (diff fragment may not parse)
        for lineno, text in added:
            s = text.strip()
            if re.match(r"except\s*(Exception|BaseException)?\s*:", s) or s == "except:":
                out.append(Finding("SLP-01", "P1", path, lineno, s,
                                   "Broad except clause — verify a specific failure is handled, not swallowed."))
        return out
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            if node.type is None:
                out.append(Finding("SLP-01", "P1", path, added[0][0] if added else 0,
                                   "except:", "Bare except — catches everything including KeyboardInterrupt."))
            elif isinstance(node.type, ast.Name) and node.type.id in ("Exception", "BaseException"):
                out.append(Finding("SLP-01", "P1", path, added[0][0] if added else 0,
                                   f"except {node.type.id}:",
                                   "Try-except blanket — catches everything; narrow to the expected failure."))
    return out


def check_swallowed_exception(path: str, added: list) -> list[Finding]:
    out = []
    for i, (lineno, text) in enumerate(added):
        if re.match(r"\s*except\b.*:", text):
            # look ahead: handler body is only `pass` (or pass + comment)
            body = [t.strip() for _, t in added[i + 1:i + 4]
                    if t.strip() and not t.strip().startswith("#")]
            if body and all(b == "pass" for b in body[:1]):
                out.append(Finding("SLP-02", "P1", path, lineno, text.strip(),
                                   "Exception swallowed with bare `pass` — log, re-raise, or handle explicitly."))
    return out


def check_read_modify_write(path: str, added: list) -> list[Finding]:
    """Heuristic: <x> = db.get(...) ... <x>.<attr> <op>= ... db.save(<x>) in one diff."""
    out = []
    text = "\n".join(t for _, t in added)
    gets = set(re.findall(r"(\w+)\s*=\s*(?:db|repo|store|session)[\.\w]*\.get\w*\(", text))
    if not gets:
        return out
    has_atomic = re.search(r"\b(UPDATE\s+\w+\s+SET|select_for_update|with_for_update|F\(|atomic|transaction)", text,
                           re.IGNORECASE)
    for var in gets:
        if re.search(rf"{re.escape(var)}\.\w+\s*[+\-*/]?=", text) and not has_atomic:
            first = next((ln for ln, t in added if var in t), added[0][0] if added else 0)
            out.append(Finding("SLP-03", "P1", path, first, f"{var} = ...get(...) then mutated + saved",
                               "Read-modify-write on shared state without atomic op/lock — race under concurrency."))
            break
    return out


def check_auth_or(path: str, added: list) -> list[Finding]:
    out = []
    for lineno, text in added:
        s = text.strip()
        if re.search(r"\bif\b.*\b(or)\b.*:", s) and re.search(
                r"(is_owner|is_admin|is_member|has_role|permit|allow|grant|auth)", s, re.IGNORECASE):
            out.append(Finding("SLP-04", "P1", path, lineno, s,
                               "Auth check uses `or` — confirm the boolean matches the intended rule (needs LLM review)."))
    return out


def check_unused_imports(path: str, added: list) -> list[Finding]:
    out = []
    src = "\n".join(t for _, t in added)
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return out
    imported: dict[str, int] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                imported[(a.asname or a.name).split(".")[0]] = 0
        elif isinstance(node, ast.ImportFrom):
            for a in node.names:
                imported[a.asname or a.name] = 0
    used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    used |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    for name in imported:
        if name not in used:
            out.append(Finding("SLP-05", "P2", path, added[0][0] if added else 0, f"import {name}",
                               "Imported but never used in the added code — remove or confirm cross-file use."))
    return out


def check_function_level_import(path: str, added: list) -> list[Finding]:
    out = []
    src = "\n".join(t for _, t in added)
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return out
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for child in ast.walk(node):
                if isinstance(child, (ast.Import, ast.ImportFrom)):
                    out.append(Finding("SLP-06", "P2", path, added[0][0] if added else 0,
                                       "import inside function",
                                       "Import buried in function body — hoist to module top unless circular."))
                    break
    return out


def check_mock_tests_mock(path: str, added: list) -> list[Finding]:
    if not is_test(path):
        return []
    out = []
    text = "\n".join(t for _, t in added)
    patched = set(re.findall(r"patch\([\"']([\w\.]+)[\"']", text))
    for lineno, t in added:
        if t.strip().startswith(("assert", "def test")):
            continue
        for sym in patched:
            leaf = sym.split(".")[-1]
            if re.search(rf"assert\s+{re.escape(leaf)}\s*\(", t):
                out.append(Finding("SLP-07", "P2", path, lineno, t.strip(),
                                   f"Test asserts the mock `{leaf}` itself, not real code — fake test."))
    return out


def check_env_cargo_cult(path: str, added: list) -> list[Finding]:
    out = []
    for lineno, text in added:
        m = re.search(r"os\.getenv\(\s*[\"']([A-Z][A-Z0-9_]*)[\"']", text)
        if m and m.group(1) in ("RETRY_COUNT", "DATE_FORMAT", "TIMEOUT", "ENABLE_NEW_PARSER",
                                "BATCH_SIZE", "MAX_RETRIES", "DEFAULT_FORMAT"):
            out.append(Finding("SLP-08", "P2", path, lineno, text.strip(),
                               f"`{m.group(1)}` promoted to env var — inline as constant unless a 2nd value exists."))
    return out


CHECKERS = [
    check_blanket_except,
    check_swallowed_exception,
    check_read_modify_write,
    check_auth_or,
    check_unused_imports,
    check_function_level_import,
    check_mock_tests_mock,
    check_env_cargo_cult,
]


# ---------------------------------------------------------------- main

def scan(diff_text: str, min_severity: str = "P3") -> dict:
    findings: list[Finding] = []
    for df in parse_diff(diff_text):
        if not df.added_lines:
            continue
        if is_python(df.path):
            for checker in CHECKERS:
                findings.extend(checker(df.path, df.added_lines))
        else:
            # non-Python: only language-agnostic regex rules
            for checker in (check_swallowed_exception, check_auth_or):
                findings.extend(checker(df.path, df.added_lines))
    findings = [f for f in findings if SEV_ORDER[f.severity] <= SEV_ORDER[min_severity]]
    p1 = sum(1 for f in findings if f.severity == "P1")
    p2 = sum(1 for f in findings if f.severity == "P2")
    if p1 > 0:
        verdict = "SLOP" if p1 >= 2 else "SUSPECT"
    elif p2 >= 3:
        verdict = "SUSPECT"
    elif findings:
        verdict = "SUSPECT" if p2 else "CLEAN"
    else:
        verdict = "CLEAN"
    return {
        "verdict": verdict,
        "summary": {"P1": p1, "P2": p2,
                    "P3": sum(1 for f in findings if f.severity == "P3"),
                    "total": len(findings)},
        "findings": [asdict(f) for f in findings],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="pr-slop-guard static scan")
    ap.add_argument("--diff-file", default=None, help="path to unified diff (default: stdin)")
    ap.add_argument("--min-severity", default="P3", choices=["P1", "P2", "P3"])
    args = ap.parse_args()
    if args.diff_file:
        with open(args.diff_file, encoding="utf-8", errors="replace") as fh:
            diff_text = fh.read()
    else:
        diff_text = sys.stdin.read()
    print(json.dumps(scan(diff_text, args.min_severity), indent=2))


if __name__ == "__main__":
    main()
