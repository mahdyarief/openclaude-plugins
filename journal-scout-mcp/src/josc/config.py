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


def get_semantic_scholar_key() -> Optional[str]:
    return os.getenv("SEMANTIC_SCHOLAR_API_KEY") or load_config_file().get(
        "semantic_scholar_api_key"
    )


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