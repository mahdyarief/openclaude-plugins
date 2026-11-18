import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

# src/josc/config.py -> src/josc -> src -> repo root
PLUGIN_DIR = Path(__file__).resolve().parents[2]
CONFIG_FILE = PLUGIN_DIR / "config.json"
DEFAULT_CACHE_TTL = 300.0


def load_config_file() -> Dict[str, Any]:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}


def get_api_key() -> str:
    api_key = os.getenv("SCOPUS_API_KEY")
    if api_key:
        return api_key
    api_key = load_config_file().get("api_key")
    if not api_key:
        raise ValueError(
            "Elsevier API key not found. Set 'SCOPUS_API_KEY' or add "
            "'api_key' to config.json next to this plugin."
        )
    return api_key


def _split_keys(raw: str) -> list[str]:
    text = (raw or "").strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            loaded = json.loads(text)
        except json.JSONDecodeError:
            loaded = None
        if isinstance(loaded, list):
            return [k.strip() for k in loaded if isinstance(k, str) and k.strip()]
    parts = text.replace(";", ",").split(",")
    return [k.strip() for k in parts if k.strip()]


def get_consensus_keys() -> list[str]:
    """Consensus keys from ``CONSENSUS_API_KEYS``/``CONSENSUS_API_KEY``, or config.

    A comma- or semicolon-separated list (or JSON array) enables round-robin
    rotation across accounts. A single key still works, and the config file is
    only consulted when the environment is empty.
    """
    keys = _split_keys(os.getenv("CONSENSUS_API_KEYS", ""))
    if not keys:
        keys = _split_keys(os.getenv("CONSENSUS_API_KEY", ""))
    if not keys:
        keys = _split_keys(load_config_file().get("consensus_api_key") or "")
    return list(dict.fromkeys(keys))


def get_consensus_key() -> str:
    keys = get_consensus_keys()
    if not keys:
        raise ValueError(
            "Consensus API key not found. Set 'CONSENSUS_API_KEYS' (or "
            "'CONSENSUS_API_KEY') or add 'consensus_api_key' to config.json "
            "next to this plugin."
        )
    return keys[0]


def get_exa_api_keys() -> list[str]:
    """Multiple Exa keys from the environment, rotated by :mod:`josc.exa_client`."""
    from .exa_client import load_exa_keys

    return load_exa_keys()


def get_polite_email() -> str:
    return (
        os.getenv("JOURNAL_SCOUT_EMAIL")
        or load_config_file().get("polite_email")
        or "anonymous@example.com"
    )


def get_cache_ttl() -> float:
    """Seconds to cache identical upstream queries; ``<= 0`` disables it."""
    raw = os.getenv("JOURNAL_SCOUT_CACHE_TTL")
    if raw is None:
        raw = load_config_file().get("cache_ttl", DEFAULT_CACHE_TTL)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return DEFAULT_CACHE_TTL


def get_turso_url() -> Optional[str]:
    """libSQL/Turso database URL; ``None`` when persistence is not configured."""
    return os.getenv("TURSO_DATABASE_URL") or load_config_file().get("turso_url")


def get_turso_token() -> Optional[str]:
    return os.getenv("TURSO_AUTH_TOKEN") or load_config_file().get("turso_token")