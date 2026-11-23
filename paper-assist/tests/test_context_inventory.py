"""Tests for the deterministic project-material inventory."""

from __future__ import annotations

import json

import pytest

from paperassist.context_inventory import (
    ContextError,
    ContextSafetyError,
    format_context_brief,
    inventory_from_payload,
)


def fixture(root):
    (root / "notes.md").write_text(
        "# Background\n\nAlpha is a term.\n\n# Method\n\nBeta follows.\n",
        encoding="utf-8",
    )
    (root / "rows.json").write_text(
        json.dumps(
            [
                {"id": 1, "group": "A", "score": 0.9},
                {"id": 2, "group": "B", "score": 0.7},
                {"id": 3, "group": "A", "score": 0.8},
            ]
        ),
        encoding="utf-8",
    )
    (root / "rows.csv").write_text(
        "id,group,score\n1,A,0.9\n2,B,0.7\n", encoding="utf-8"
    )
    (root / "refs.bib").write_text(
        "@article{k1,\n author={A.},\n title={Alpha},\n year={2020}\n}\n",
        encoding="utf-8",
    )
    (root / "ignored.bin").write_bytes(b"\x00\x01\x02")


def test_empty_payload_returns_empty_inventory(tmp_path):
    inventory = inventory_from_payload(tmp_path, {})
    assert inventory.sources == ()
    assert inventory.digest == ""
    assert inventory.signals()["source_count"] == 0


def test_inventory_is_generic_and_structural(tmp_path):
    fixture(tmp_path)
    payload = {"context_paths": ["notes.md", "rows.json", "rows.csv", "refs.bib"]}
    inventory = inventory_from_payload(tmp_path, payload)
    signals = inventory.signals()
    assert signals["source_count"] == 4
    assert signals["kind_counts"] == {
        "bibliography": 1,
        "data": 2,
        "prose": 1,
    }
    assert signals["heading_count"] == 2
    assert signals["data_sources"] == 2
    assert signals["data_records"] == 5
    assert set(signals["data_fields"]) == {"id", "group", "score"}


def test_digest_is_stable_and_content_sensitive(tmp_path):
    fixture(tmp_path)
    payload = {"context_paths": ["notes.md", "rows.json"]}
    first = inventory_from_payload(tmp_path, payload)
    second = inventory_from_payload(tmp_path, payload)
    assert first.digest == second.digest
    (tmp_path / "notes.md").write_text("# Changed\n", encoding="utf-8")
    third = inventory_from_payload(tmp_path, payload)
    assert third.digest != first.digest


def test_directory_expansion_and_tex_headings(tmp_path):
    sub = tmp_path / "materials"
    sub.mkdir()
    (sub / "draft.tex").write_text(
        "\\section{Intro}\nText.\n\\subsection{Detail}\nMore.\n", encoding="utf-8"
    )
    (sub / "rows.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    inventory = inventory_from_payload(tmp_path, {"context_paths": ["materials"]})
    assert len(inventory.sources) == 2
    tex = next(source for source in inventory.sources if source.path.endswith(".tex"))
    assert tex.headings == ("Intro", "Detail")


def test_binary_pdf_is_recorded_without_text(tmp_path):
    (tmp_path / "scan.pdf").write_bytes(b"%PDF-1.4\n")
    inventory = inventory_from_payload(tmp_path, {"context_paths": ["scan.pdf"]})
    source = inventory.sources[0]
    assert source.kind == "pdf"
    assert source.truncated is True
    assert source.bytes_read == 0


def test_budget_truncates_large_text(tmp_path):
    (tmp_path / "long.txt").write_text("line\n" * 20000, encoding="utf-8")
    inventory = inventory_from_payload(
        tmp_path,
        {"context_paths": ["long.txt"]},
        budget_bytes=4096,
    )
    source = inventory.sources[0]
    assert source.truncated is True
    assert source.bytes_read <= 4096
    assert source.total_bytes > 4096


def test_missing_path_raises(tmp_path):
    with pytest.raises(ContextError):
        inventory_from_payload(tmp_path, {"context_paths": ["absent.md"]})


def test_escape_is_rejected(tmp_path):
    outside = tmp_path.parent / "outside.md"
    outside.write_text("outside\n", encoding="utf-8")
    with pytest.raises(ContextSafetyError):
        inventory_from_payload(tmp_path, {"context_paths": [str(outside)]})


def test_symlink_is_rejected(tmp_path):
    outside = tmp_path.parent / "outside.md"
    outside.write_text("outside\n", encoding="utf-8")
    try:
        (tmp_path / "link.md").symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not available on this platform")
    with pytest.raises(ContextSafetyError):
        inventory_from_payload(tmp_path, {"context_paths": ["link.md"]})


def test_too_many_files_is_rejected(tmp_path):
    many = tmp_path / "many"
    many.mkdir()
    for index in range(50):
        (many / f"f{index}.md").write_text(f"# {index}\n", encoding="utf-8")
    with pytest.raises(ContextError, match="the limit is"):
        inventory_from_payload(tmp_path, {"context_paths": ["many"]})


def test_brief_labels_materials_as_untrusted(tmp_path):
    fixture(tmp_path)
    inventory = inventory_from_payload(
        tmp_path, {"context_paths": ["notes.md", "rows.json"]}
    )
    brief = format_context_brief(inventory)
    assert "UNTRUSTED data" in brief
    assert "notes.md" in brief
    assert "records: 3" in brief
