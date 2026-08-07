"""Configuration: default folder resolution and LibreOffice detection.

This module is the single source of truth for two pieces of runtime
configuration:

* The **default folder** for relative paths passed to tool calls
  (env var ``OFFICE_MCP_DEFAULT_FOLDER``, falling back to the server's
  current working directory).
* The **LibreOffice / soffice executable** location, used by the
  export tools (``office_mcp.exporters``) for PDF and HTML
  generation.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

#: Environment variable that overrides the default folder for relative paths.
DEFAULT_FOLDER_ENV: str = "OFFICE_MCP_DEFAULT_FOLDER"

#: Environment variable that overrides the LibreOffice executable path.
#: When set, :func:`find_libreoffice` returns this value (if the file exists)
#: before searching the candidate list.
SOFFICE_ENV: str = "OFFICE_MCP_SOFFICE"

#: Candidate paths for the ``soffice`` executable, in priority order.
#: On Windows, macOS, and Linux we ship the common install locations.
_LO_CANDIDATES: tuple[str, ...] = (
    # Windows
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    # macOS
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    # Linux
    "/usr/bin/soffice",
    "/usr/lib/libreoffice/program/soffice",
    "/opt/libreoffice/program/soffice",
    # Cygwin / Git Bash on Windows
    "/c/Program Files/LibreOffice/program/soffice.exe",
    "/c/Program Files (x86)/LibreOffice/program/soffice.exe",
)


# ---------------------------------------------------------------------------
# Default folder
# ---------------------------------------------------------------------------


def get_default_folder() -> Path:
    """Return the default folder used to resolve relative paths.

    Priority:

    1. ``OFFICE_MCP_DEFAULT_FOLDER`` environment variable, if set. The
       path is ``expanduser``-ed, ``resolve``-d, and the directory is
       created (``parents=True``, ``exist_ok=True``) so callers can
       immediately write to it.
    2. The server's current working directory (``Path.cwd().resolve()``).
    """
    env = os.environ.get(DEFAULT_FOLDER_ENV)
    if env:
        p = Path(env).expanduser().resolve()
        try:
            p.mkdir(parents=True, exist_ok=True)
        except OSError:
            # If the directory cannot be created, fall through to CWD.
            # We do not raise here because the caller may have a
            # pre-existing folder they want to use as a reference.
            pass
        return p
    return Path.cwd().resolve()


# ---------------------------------------------------------------------------
# LibreOffice detection
# ---------------------------------------------------------------------------


def find_libreoffice() -> str | None:
    """Locate the ``soffice`` executable, returning an absolute path or ``None``.

    Search order:

    1. ``OFFICE_MCP_SOFFICE`` environment variable, if the file exists.
    2. Built-in candidate list of common install locations per OS.
       These are checked **before** the ``PATH`` lookup because on
       Windows, when the LibreOffice ``program`` directory is on
       ``PATH``, ``shutil.which("soffice")`` returns ``soffice.COM``
       (a 16-bit DOS wrapper) which hangs when launched by
       ``subprocess.run(capture_output=True, ...)``. Preferring the
       explicit ``soffice.exe`` candidates avoids that footgun.
    3. ``shutil.which("soffice")`` — whatever the current ``PATH``
       resolves. ``.COM`` files are rejected here to keep the
       behaviour aligned with step 2.
    """
    # 1. Explicit override
    override = os.environ.get(SOFFICE_ENV)
    if override:
        p = Path(override).expanduser()
        if p.is_file():
            return str(p.resolve())

    # 2. Built-in candidates (preferred). The first file that exists
    # wins; we deliberately use ``.exe`` here so the resolved path
    # never points at the 16-bit ``soffice.COM`` wrapper.
    for candidate in _LO_CANDIDATES:
        if Path(candidate).is_file():
            return candidate

    # 3. Current PATH. Skip ``.COM`` files (Windows 16-bit console
    # wrappers that don't cooperate with ``subprocess.run``).
    on_path = shutil.which("soffice")
    if on_path and not on_path.lower().endswith(".com"):
        return on_path

    return None
