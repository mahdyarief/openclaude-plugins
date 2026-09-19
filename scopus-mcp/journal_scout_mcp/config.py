import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

PLUGIN_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = PLUGIN_DIR / "config.json"
DEFAULT_CACHE_DIR = PLUGIN_DIR / ".cache"


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


def get_cache_config() -> Dict[str, Any]:
    config = load_config_file()
    cache_dir = os.getenv("JOURNAL_SCOUT_CACHE_DIR") or config.get(
        "cache_dir", str(DEFAULT_CACHE_DIR)
    )
    return {"dir": cache_dir, "default": 86400}