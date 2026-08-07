"""Path resolution helpers used by every tool.

Tools never construct absolute paths inline; they call
:func:`resolve_path` with the user-supplied ``file`` (and optional
``folder``) and operate on the returned ``Path``.

The resolver is intentionally permissive: any absolute path is accepted
as-is (after ``.resolve()``), and relative paths are joined with the
caller-supplied ``folder`` or the default folder. It does not sandbox
to a single root — the agent is trusted.

File-lock detection
-------------------
When an Office file is open in Word / Excel / PowerPoint (or any other
application holding an exclusive lock), the underlying library
``save()`` call fails with a platform-specific error. Use
:func:`save_with_lock_check` to wrap the save call so a held lock is
reported as the structured ``ERR_FILE_LOCKED`` error instead of an
uncaught :class:`PermissionError` (which the MCP server would surface
as a 500).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .config import get_default_folder
from .errors import ERR_FILE_LOCKED, OfficeMCPError


def resolve_path(file: str | Path, folder: str | Path | None = None) -> Path:
    """Resolve a user-supplied file reference to an absolute ``Path``.

    Parameters
    ----------
    file:
        The path supplied by the agent. May be absolute or relative.
    folder:
        Optional base folder. When given, relative ``file`` paths are
        joined with this folder (which is itself ``expanduser``-ed and
        ``resolve``-d). When ``None``, the default folder from
        :func:`office_mcp.config.get_default_folder` is used.

    Returns
    -------
    pathlib.Path
        An absolute, canonical path. Parent directories are **not**
        created — that is the caller's responsibility.

    Raises
    ------
    TypeError
        If ``file`` is neither a ``str`` nor a ``Path``.
    """
    if isinstance(file, Path):
        p = file
    elif isinstance(file, str):
        if not file.strip():
            raise ValueError("path must be a non-empty string")
        p = Path(file)
    else:
        raise TypeError(f"path must be str or Path, got {type(file).__name__}")

    if not p.is_absolute():
        if folder is not None:
            base = Path(folder).expanduser().resolve()
        else:
            base = get_default_folder()
        p = (base / p).resolve()
    else:
        p = p.expanduser().resolve()
    return p


def ensure_parent(path: Path) -> Path:
    """Create the parent directory of ``path`` if it does not exist.

    Returns ``path`` unchanged for convenience (so callers can
    ``ensure_parent(resolve_path(...))`` and keep using the value).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


#: Errno value for "Permission denied" (``EACCES``) on POSIX and
#: "The process cannot access the file because it is being used by
#: another process" on Windows. Both surface as :class:`PermissionError`
#: or as :class:`OSError` with ``errno == 13`` depending on the library.
_ERRNO_PERMISSION_DENIED: int = 13


def save_with_lock_check(
    path: Path | str,
    save_fn: Callable[[], Any],
) -> Any:
    """Run ``save_fn`` and translate file-lock failures to ``ERR_FILE_LOCKED``.

    Office libraries raise different exception types when the target
    file is locked by another process:

    * **Windows** — typically :class:`PermissionError` with
      ``WinError 32`` ("The process cannot access the file because it
      is being used by another process").
    * **POSIX** — :class:`PermissionError` with ``errno=13``
      (``EACCES``).
    * Some library versions wrap the underlying OS error in a plain
      :class:`OSError` with ``errno=13`` instead of
      :class:`PermissionError`.

    All three forms are caught here and re-raised as
    :class:`OfficeMCPError` with code ``ERR_FILE_LOCKED``. Any other
    exception propagates unchanged so the caller's broader error
    handling is preserved.

    Parameters
    ----------
    path:
        The absolute (or relative) path the save targets. Used only
        for error reporting — the helper does not touch the filesystem
        itself. It is resolved to an absolute path before being put
        into ``details``.
    save_fn:
        A zero-argument callable that performs the save (typically
        ``lambda: doc.save(str(path))``). Whatever it returns is
        returned to the caller.

    Returns
    -------
    Any
        Whatever ``save_fn`` returns on success.

    Raises
    ------
    OfficeMCPError
        With code ``ERR_FILE_LOCKED`` (-32002) when ``save_fn`` raises
        :class:`PermissionError` (or any subclass) or
        :class:`OSError` with ``errno == 13``. The absolute target
        path is included in ``details["path"]`` so the agent can
        tell the user which file is locked.
    """
    abs_path = Path(path).expanduser().resolve()
    try:
        return save_fn()
    except PermissionError as exc:
        # ``PermissionError`` covers both the bare form and all
        # subclasses (e.g. custom library errors). It is also an
        # ``OSError(errno=13)`` on every supported platform.
        raise OfficeMCPError(
            ERR_FILE_LOCKED,
            (
                f"File is locked or in use by another process: {abs_path}. "
                "Close the file in Word/Excel/PowerPoint (or the "
                "application holding the lock) and retry."
            ),
            {"path": str(abs_path), "reason": str(exc)},
        ) from exc
    except OSError as exc:
        # Some libraries wrap EACCES in a plain ``OSError`` rather
        # than ``PermissionError``. Treat any ``OSError(errno=13)`` the
        # same as a permission error so we report it consistently.
        if getattr(exc, "errno", None) == _ERRNO_PERMISSION_DENIED:
            raise OfficeMCPError(
                ERR_FILE_LOCKED,
                (
                    f"File is locked or in use by another process: {abs_path}. "
                    "Close the file in Word/Excel/PowerPoint (or the "
                    "application holding the lock) and retry."
                ),
                {"path": str(abs_path), "reason": str(exc)},
            ) from exc
        raise
