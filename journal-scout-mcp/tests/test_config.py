import json

import journal_scout_mcp.config as config


def _write_config(tmp_path, data):
    p = tmp_path / "config.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def test_api_key_prefers_env(monkeypatch, tmp_path):
    cfg = _write_config(tmp_path, {"api_key": "from_file"})
    monkeypatch.setattr(config, "CONFIG_FILE", cfg)
    monkeypatch.setenv("SCOPUS_API_KEY", "from_env")
    assert config.get_api_key() == "from_env"


def test_api_key_falls_back_to_file(monkeypatch, tmp_path):
    cfg = _write_config(tmp_path, {"api_key": "from_file"})
    monkeypatch.setattr(config, "CONFIG_FILE", cfg)
    monkeypatch.delenv("SCOPUS_API_KEY", raising=False)
    assert config.get_api_key() == "from_file"


def test_api_key_missing_raises(monkeypatch, tmp_path):
    cfg = _write_config(tmp_path, {})
    monkeypatch.setattr(config, "CONFIG_FILE", cfg)
    monkeypatch.delenv("SCOPUS_API_KEY", raising=False)
    try:
        config.get_api_key()
    except ValueError as e:
        assert "api_key" in str(e)
    else:
        raise AssertionError("expected ValueError")


def test_polite_email_default(monkeypatch, tmp_path):
    cfg = _write_config(tmp_path, {})
    monkeypatch.setattr(config, "CONFIG_FILE", cfg)
    monkeypatch.delenv("JOURNAL_SCOUT_EMAIL", raising=False)
    assert config.get_polite_email() == "anonymous@example.com"


def test_semantic_scholar_key_optional(monkeypatch, tmp_path):
    cfg = _write_config(tmp_path, {})
    monkeypatch.setattr(config, "CONFIG_FILE", cfg)
    monkeypatch.delenv("SEMANTIC_SCHOLAR_API_KEY", raising=False)
    assert config.get_semantic_scholar_key() is None
