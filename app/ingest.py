"""Bringing resumes into the database: folder scanning and manual uploads."""

from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

import config
import db
import exports
import resume_parser as rp

SETTLE_SECONDS = 3  # ignore files modified very recently - they may still be copying / syncing
EXCEL_RETRY_SECONDS = 60  # if the workbook is open in Excel, try again this often
_last_excel_try = 0.0


@dataclass
class ScanResult:
    added: list[str] = field(default_factory=list)       # candidate names
    duplicates: int = 0
    needs_review: int = 0
    failed: list[str] = field(default_factory=list)
    remaining: int = 0                                   # files still waiting (batch limit / settling)
    total_files: int = 0
    excel_message: str = ""

    @property
    def processed(self) -> int:
        return len(self.added) + self.duplicates + len(self.failed)


def _relative(path: Path) -> str:
    return path.relative_to(config.RESUMES_DIR).as_posix()


def list_resume_files() -> list[Path]:
    root = config.RESUMES_DIR
    if not root.exists():
        return []
    return sorted(
        p for p in root.rglob("*")
        if p.is_file() and p.suffix.lower() in rp.SUPPORTED_EXTENSIONS and not p.name.startswith("~$")
    )


def ingest_file(path: Path) -> dict:
    """Parse one file already inside the resumes folder and add it to the database.

    Returns {'status': 'added'|'duplicate'|'failed', 'candidate_id', 'name', 'notes'}.
    """
    rel = _relative(path)
    stat = path.stat()
    try:
        data = path.read_bytes()
    except OSError as exc:
        return {"status": "failed", "candidate_id": None, "name": path.stem, "notes": [f"Could not read file: {exc}"]}
    digest = hashlib.sha256(data).hexdigest()

    existing = db.candidate_by_hash(digest)
    if existing:
        db.record_file(rel, stat.st_size, stat.st_mtime, digest, "duplicate", existing, "Same file already imported")
        return {"status": "duplicate", "candidate_id": existing, "name": path.stem, "notes": ["Already in the database"]}

    parsed = rp.parse_resume(data, path.name)
    notes = list(parsed.pop("notes"))
    twin = db.candidate_by_email(parsed["email"])
    if twin:
        notes.append(f"Same email as {twin} - possible duplicate or newer version of a resume")
    parsed.update(resume_file=rel, file_hash=digest, parse_notes="; ".join(notes))
    try:
        cid = db.add_candidate(parsed)
    except db.DuplicateFile as dup:  # another process imported this exact file a moment ago
        db.record_file(rel, stat.st_size, stat.st_mtime, digest, "duplicate", dup.existing_id, "Same file already imported")
        return {"status": "duplicate", "candidate_id": dup.existing_id, "name": path.stem, "notes": ["Already in the database"]}
    db.record_file(rel, stat.st_size, stat.st_mtime, digest, "added", cid, parsed["parse_notes"])
    return {"status": "added", "candidate_id": cid, "name": parsed["name"], "notes": notes}


def scan_folder(max_new: int | None = 25) -> ScanResult:
    """Import every new or changed resume in the folder. Safe to call repeatedly."""
    res = ScanResult()
    files = list_resume_files()
    res.total_files = len(files)
    known = db.known_files()
    now = time.time()
    done = 0
    for path in files:
        rel = _relative(path)
        try:
            st = path.stat()
        except OSError:
            continue
        if rel in known and known[rel][0] == st.st_size and abs(known[rel][1] - st.st_mtime) < 1e-6:
            continue
        if now - st.st_mtime < SETTLE_SECONDS:
            res.remaining += 1
            continue
        if max_new is not None and done >= max_new:
            res.remaining += 1
            continue
        out = ingest_file(path)
        done += 1
        if out["status"] == "added":
            res.added.append(out["name"])
            if out["notes"]:
                res.needs_review += 1
        elif out["status"] == "duplicate":
            res.duplicates += 1
        else:
            res.failed.append(f"{path.name}: {'; '.join(out['notes'])}")
    global _last_excel_try
    if res.added:
        db.set_meta("excel_dirty", "1")
    if res.added or (db.get_meta("excel_dirty") == "1" and time.time() - _last_excel_try > EXCEL_RETRY_SECONDS):
        _last_excel_try = time.time()
        _, res.excel_message = exports.export_excel()  # marks itself clean on success
    return res


def save_upload(filename: str, data: bytes) -> Path:
    """Write an uploaded file into the resumes folder without overwriting a different file."""
    safe = re.sub(r'[\\/:*?"<>|]+', "_", Path(filename).name).strip() or "resume"
    target = config.RESUMES_DIR / safe
    n = 1
    while target.exists() and hashlib.sha256(target.read_bytes()).digest() != hashlib.sha256(data).digest():
        target = config.RESUMES_DIR / f"{Path(safe).stem}_{n}{Path(safe).suffix}"
        n += 1
    if not target.exists():
        config.RESUMES_DIR.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return target


def pending_files() -> int:
    known = db.known_files()
    n = 0
    for p in list_resume_files():
        try:
            st = p.stat()
        except OSError:
            continue
        k = known.get(_relative(p))
        if not k or k[0] != st.st_size or abs(k[1] - st.st_mtime) > 1e-6:
            n += 1
    return n
