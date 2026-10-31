"""Show the real resume, not just extracted text.

PDF  -> shown as is.
DOCX -> converted to PDF by Microsoft Word when it is installed (looks exactly like the document; the result is
        cached in data/previews), otherwise rendered as a formatted page with `mammoth`.
TXT  -> shown as text (it is plain text anyway).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import config

_PS1 = Path(__file__).with_name("word_to_pdf.ps1")
_RETRY_AFTER_SECONDS = 600
_last_failure: dict[str, float] = {}


def _cache_path(key: str) -> Path:
    return config.DATA_DIR / "previews" / f"{key}.pdf"


def _powershell() -> str | None:
    found = shutil.which("powershell")
    if found:
        return found
    candidate = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    return str(candidate) if candidate.exists() else None


def _convert_with_word(src: Path, target: Path) -> bool:
    ps = _powershell()
    if sys.platform != "win32" or not _PS1.exists() or not ps:
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".part.pdf")
    tmp.unlink(missing_ok=True)
    try:
        proc = subprocess.run(
            [ps, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(_PS1),
             str(src.resolve()), str(tmp)],
            capture_output=True, timeout=120, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (subprocess.TimeoutExpired, OSError):
        tmp.unlink(missing_ok=True)
        return False
    if proc.returncode == 0 and tmp.exists() and tmp.stat().st_size > 0:
        os.replace(tmp, target)
        return True
    tmp.unlink(missing_ok=True)
    return False


def pdf_for(path: Path, key: str) -> bytes | None:
    """PDF bytes that show this resume exactly as the author made it, or None if that is not possible."""
    ext = path.suffix.lower()
    if ext == ".pdf":
        return path.read_bytes()
    if ext == ".docx":
        target = _cache_path(key)
        if target.exists():
            return target.read_bytes()
        if time.time() - _last_failure.get(key, 0) < _RETRY_AFTER_SECONDS:
            return None
        if _convert_with_word(path, target):
            return target.read_bytes()
        _last_failure[key] = time.time()
    return None


def docx_html(path: Path) -> str | None:
    """Formatted HTML of a .docx (headings, bold, lists, tables), used when Word is not available."""
    if path.suffix.lower() != ".docx":
        return None
    try:
        import mammoth

        with open(path, "rb") as f:
            body = mammoth.convert_to_html(f).value
    except Exception:
        return None
    return (
        "<div style=\"background:#fff;color:#1a202c;padding:28px 36px;font-family:Calibri,Segoe UI,Arial,sans-serif;"
        "font-size:14px;line-height:1.45\">" + body + "</div>"
    )
