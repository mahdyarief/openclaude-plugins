# 12 AI Slop Code Patterns Reference

Field guide based on Potapov's taxonomy (June 2026) and CodeRabbit empirical data.
Ranked P1 (fix before merge) / P2 (fix this sprint) / P3 (track and fix).

---

## P1 — Fix Before Merge (Production Risk)

### P1-1. The Try-Except Blanket (`SLP-01`, `SLP-02`)
- **Signal**: `except Exception:` or bare `except:` wrapping multiple operations, especially with `pass` or generic logging.
- **Why AI writes it**: Models optimize for "never crash" as a proxy for robustness.
- **Danger**: Swallows operational failures (failed payment, corrupt write) and proceeds as if successful.
- **Fix**: Catch only specific, expected exceptions (`except (KeyError, ValueError):`). Never wrap multi-step transactions in a single blanket.

### P1-2. The Race Condition Blind Spot (`SLP-03`)
- **Signal**: Read-modify-write on shared state without locks or transactions:
  ```python
  user = db.get(user_id)
  user.credits += amount  # read above, write below
  db.save(user)
  ```
- **Why AI writes it**: Models assume a single-threaded world unless explicitly prompted for concurrency.
- **Danger**: Under concurrent requests, updates overwrite each other and vanish.
- **Fix**: Atomic SQL (`UPDATE users SET credits = credits + %s`), `select_for_update()`, or transactional locking.

### P1-3. The Confident Hallucination
- **Signal**: Plausible-sounding method or parameter that does not exist in the library version installed:
  ```python
  s3.download_bucket_to_folder(bucket, "/tmp")  # boto3 has no such method
  ```
- **Why AI writes it**: Interpolation across similar library APIs in training data.
- **Danger**: Passes review because it sounds authoritative; fails at runtime under production path.
- **Reviewer check**: Treat any unfamiliar method as guilty until verified in installed docs/REPL.

### P1-4. The Security Non-Check (`SLP-04`)
- **Signal**: Authorization logic with inverted or broad boolean:
  ```python
  if user.is_owner or user.is_member:
      grant_access(resource)  # members reached owner-only resource
  ```
  Or trusting client-controlled input (`request.json.get("is_admin")`).
- **Fix**: Strict `and` gates; derive authorization strictly from verified server-side session.

---

## P2 — Fix This Sprint (Architectural Rot)

### P2-1. The Over-Abstraction (`SLP-09`)
- **Signal**: New `AbstractFactory`, `Strategy`, `Interface` with exactly one concrete implementation.
- **Why AI writes it**: Trained on enterprise Java/C# boilerplate; defaults to ceremony.
- **Danger**: Indirection tax without extensibility benefit.
- **Fix**: Inline into a plain function. Add abstraction only on the second real implementation.

### P2-2. The Config Cargo Cult (`SLP-08`)
- **Signal**: Single-use constants promoted to `os.getenv("RETRY_COUNT")`, `os.getenv("DATE_FORMAT")`.
- **Why AI writes it**: Copies production configuration shapes without a reason.
- **Fix**: Inline as module constant unless a second runtime value genuinely exists.

### P2-3. The Import Chaos (`SLP-05`, `SLP-06`)
- **Signal**: Unused imports left at the top; imports buried inside function bodies.
- **Fix**: Hoist to module top, run `ruff check --select F401 --fix`.

### P2-4. The Fake Test (`SLP-07`)
- **Signal**: Test patches the very function it claims to verify:
  ```python
  def test_charge(mocker):
      m = mocker.patch("billing.charge_customer", return_value=True)
      assert m(order) is True  # asserts the mock, not the code
  ```
- **Why AI writes it**: Green coverage without reasoning about real failure modes.
- **Reviewer check**: "What would have to break in real code for this test to fail?" If nothing, test is decorative.

---

## P3 — Track and Fix (Code Drag)

### P3-1. Generic / Paraphrased Comments
- **Signal**: `# loop over users` above `for user in users:`. Comments that repeat the identifier names.
- **Fix**: Delete. Comments should explain non-obvious WHY, never obvious WHAT.

### P3-2. Stale Docstring Copy-Paste
- **Signal**: Docstring describing parameters that don't match the function signature, or copied from an adjacent method.

### P3-3. Defensive Null-Checks on Invariants
- **Signal**: `if x is not None:` checks on variables that internal code guaranteed cannot be None. Adds branch noise without safety.

### P3-4. Dead Code / Premature Helpers (`SLP-10`)
- **Signal**: Helper function added in diff that is never called anywhere in the PR.
