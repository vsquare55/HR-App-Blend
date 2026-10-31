"""SQLite storage: candidates, jobs, status log, and a record of which files were processed."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime

import pandas as pd

import config

TS_FORMAT = "%Y-%m-%d %H:%M:%S"
DECISIONS = ("Shortlisted", "Rejected")
CANDIDATE_FIELDS = [
    "name", "email", "phone", "location", "title", "company", "experience", "education", "skills",
    "summary", "resume_file", "file_hash", "resume_text", "parse_notes",
]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS candidates (
    id TEXT PRIMARY KEY, name TEXT, email TEXT, phone TEXT, location TEXT, title TEXT, company TEXT,
    experience REAL DEFAULT 0, education TEXT, skills TEXT, summary TEXT, resume_file TEXT,
    file_hash TEXT UNIQUE, resume_text TEXT, parse_notes TEXT, added_at TEXT, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY, title TEXT NOT NULL, department TEXT, location TEXT, experience_required TEXT,
    description TEXT, status TEXT DEFAULT 'Open', posted_date TEXT
);
CREATE TABLE IF NOT EXISTS status_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT, job_title TEXT, candidate_id TEXT,
    candidate_name TEXT, status TEXT, timestamp TEXT, notes TEXT, reviewed_by TEXT
);
CREATE INDEX IF NOT EXISTS idx_log_job ON status_log (job_id, candidate_id);
CREATE TABLE IF NOT EXISTS files (
    path TEXT PRIMARY KEY, size INTEGER, mtime REAL, file_hash TEXT, status TEXT, candidate_id TEXT, message TEXT
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""


def now() -> str:
    return datetime.now().strftime(TS_FORMAT)


@contextmanager
def conn():
    c = sqlite3.connect(config.DB_PATH, timeout=20)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def init_db() -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.RESUMES_DIR.mkdir(parents=True, exist_ok=True)
    with conn() as c:
        c.executescript(_SCHEMA)
        if c.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0:
            _seed_jobs(c)


def _insert_sample_jobs(c: sqlite3.Connection) -> int:
    """Add the positions from sample_jobs.json that are not in the database yet (matched by title)."""
    path = config.SAMPLE_JOBS
    if not path.exists():
        return 0
    try:
        items = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 0
    have = {r[0].lower() for r in c.execute("SELECT title FROM jobs")}
    added = 0
    for it in items:
        if it["title"].lower() in have:
            continue
        c.execute(
            "INSERT INTO jobs (id, title, department, location, experience_required, description, status, posted_date)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (_next_id(c, "jobs", "JOB-", 3), it["title"], it.get("department", ""), it.get("location", ""),
             it.get("experience_required", ""), it.get("description", ""), "Open", datetime.now().strftime("%Y-%m-%d")),
        )
        added += 1
    return added


def load_sample_jobs() -> int:
    with conn() as c:
        return _insert_sample_jobs(c)


def _seed_jobs(c: sqlite3.Connection) -> None:
    """First run only: sample positions (sample_jobs.json), or the demo workbook's four jobs if that file is missing."""
    if _insert_sample_jobs(c):
        return
    if not config.LEGACY_EXCEL.exists():
        return
    try:
        jobs = pd.read_excel(config.LEGACY_EXCEL, sheet_name="Open_Jobs")
    except Exception:
        return
    for _, j in jobs.iterrows():
        desc = (
            f"Job title: {j.get('Job_Title', '')}\nLocation: {j.get('Location', '')}\n"
            f"Experience: {j.get('Experience_Required', '')}\n\nKey requirements:\n{j.get('Key_Requirements', '')}"
        )
        c.execute(
            "INSERT OR IGNORE INTO jobs (id, title, department, location, experience_required, description, status, posted_date)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (str(j["Job_ID"]), str(j["Job_Title"]), str(j.get("Department", "")), str(j.get("Location", "")),
             str(j.get("Experience_Required", "")), desc, str(j.get("Status", "Open")), str(j.get("Posted_Date", ""))[:10]),
        )


# ----------------------------------------------------------------------------
# Candidates
# ----------------------------------------------------------------------------
def _next_id(c: sqlite3.Connection, table: str, prefix: str, width: int) -> str:
    row = c.execute(f"SELECT id FROM {table} WHERE id LIKE ? ORDER BY LENGTH(id) DESC, id DESC LIMIT 1", (f"{prefix}%",)).fetchone()
    digits = "".join(ch for ch in (row[0] if row else "") if ch.isdigit())
    return f"{prefix}{(int(digits) if digits else 0) + 1:0{width}d}"


class DuplicateFile(Exception):
    """The same resume file (by content hash) is already in the database."""

    def __init__(self, existing_id: str):
        super().__init__(existing_id)
        self.existing_id = existing_id


def add_candidate(fields: dict) -> str:
    with conn() as c:
        c.execute("BEGIN IMMEDIATE")  # serialise id generation if two processes import at once
        if fields.get("file_hash"):
            twin = c.execute("SELECT id FROM candidates WHERE file_hash=?", (fields["file_hash"],)).fetchone()
            if twin:
                raise DuplicateFile(twin[0])
        cid = _next_id(c, "candidates", "C", 4)
        ts = now()
        cols = ["id", "added_at", "updated_at", *CANDIDATE_FIELDS]
        vals = [cid, ts, ts, *[fields.get(f) for f in CANDIDATE_FIELDS]]
        c.execute(f"INSERT INTO candidates ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})", vals)
        return cid


def update_candidate(cid: str, **fields) -> None:
    allowed = {k: v for k, v in fields.items() if k in CANDIDATE_FIELDS}
    if not allowed:
        return
    sets = ", ".join(f"{k}=?" for k in allowed)
    with conn() as c:
        c.execute(f"UPDATE candidates SET {sets}, updated_at=? WHERE id=?", [*allowed.values(), now(), cid])


def delete_candidate(cid: str) -> None:
    with conn() as c:
        c.execute("DELETE FROM candidates WHERE id=?", (cid,))


def candidate_by_hash(file_hash: str) -> str | None:
    with conn() as c:
        row = c.execute("SELECT id FROM candidates WHERE file_hash=?", (file_hash,)).fetchone()
        return row[0] if row else None


def candidate_by_email(email: str) -> str | None:
    if not email:
        return None
    with conn() as c:
        row = c.execute("SELECT id FROM candidates WHERE LOWER(email)=LOWER(?) LIMIT 1", (email,)).fetchone()
        return row[0] if row else None


def data_version() -> str:
    """Changes whenever a candidate is added, edited or removed (used as a cache key)."""
    with conn() as c:
        n, last = c.execute("SELECT COUNT(*), COALESCE(MAX(updated_at), '') FROM candidates").fetchone()
        return f"{n}|{last}"


def count_candidates() -> int:
    with conn() as c:
        return c.execute("SELECT COUNT(*) FROM candidates").fetchone()[0]


def load_candidates(with_text: bool = False) -> pd.DataFrame:
    cols = "id, name, email, phone, location, title, company, experience, education, skills, summary, resume_file, parse_notes, added_at, updated_at"
    if with_text:
        cols += ", resume_text"
    with conn() as c:
        df = pd.read_sql_query(f"SELECT {cols} FROM candidates ORDER BY id", c)
    df["experience"] = df["experience"].fillna(0.0).astype(float)
    for col in df.columns.difference(["experience"]):
        df[col] = df[col].fillna("")
    return df


def get_candidate(cid: str) -> dict | None:
    with conn() as c:
        row = c.execute("SELECT * FROM candidates WHERE id=?", (cid,)).fetchone()
        return dict(row) if row else None


# ----------------------------------------------------------------------------
# Jobs
# ----------------------------------------------------------------------------
def load_jobs() -> pd.DataFrame:
    with conn() as c:
        return pd.read_sql_query("SELECT * FROM jobs ORDER BY id", c).fillna("")


def get_job(job_id: str) -> dict | None:
    with conn() as c:
        row = c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return dict(row) if row else None


def save_job(job_id: str | None, title: str, department: str, location: str, experience_required: str,
             description: str, status: str) -> str:
    with conn() as c:
        if job_id:
            c.execute(
                "UPDATE jobs SET title=?, department=?, location=?, experience_required=?, description=?, status=? WHERE id=?",
                (title, department, location, experience_required, description, status, job_id),
            )
            return job_id
        new_id = _next_id(c, "jobs", "JOB-", 3)
        c.execute(
            "INSERT INTO jobs (id, title, department, location, experience_required, description, status, posted_date)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (new_id, title, department, location, experience_required, description, status, datetime.now().strftime("%Y-%m-%d")),
        )
        return new_id


def delete_job(job_id: str) -> None:
    with conn() as c:
        c.execute("DELETE FROM jobs WHERE id=?", (job_id,))


# ----------------------------------------------------------------------------
# Status log (one row per event: Viewed / Shortlisted / Rejected / Reset)
# ----------------------------------------------------------------------------
def add_status(job_id: str, job_title: str, cid: str, name: str, status: str, notes: str, reviewer: str) -> None:
    with conn() as c:
        c.execute(
            "INSERT INTO status_log (job_id, job_title, candidate_id, candidate_name, status, timestamp, notes, reviewed_by)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (job_id, job_title, cid, name, status, now(), notes, reviewer or "Unknown"),
        )


def mark_viewed(job_id: str, job_title: str, cid: str, name: str, reviewer: str) -> bool:
    """Record a first view for this position. Returns True if a Viewed event was written."""
    with conn() as c:
        seen = c.execute(
            "SELECT 1 FROM status_log WHERE job_id=? AND candidate_id=? AND status='Viewed' LIMIT 1", (job_id, cid)
        ).fetchone()
    if seen:
        return False
    add_status(job_id, job_title, cid, name, "Viewed", "", reviewer)
    return True


def _resolve(rows: list[sqlite3.Row]) -> dict:
    """Collapse the events of one (job, candidate) into the current state."""
    decision = None
    viewed = None
    for r in rows:  # ascending by id
        if r["status"] in DECISIONS:
            decision = r
        elif r["status"] == "Reset":
            decision = None
        elif r["status"] == "Viewed" and viewed is None:
            viewed = r
    shown = decision or viewed
    return {
        "status": shown["status"] if shown else "New",
        "timestamp": shown["timestamp"] if shown else "",
        "by": shown["reviewed_by"] if shown else "",
        "notes": shown["notes"] if shown else "",
        "viewed_at": viewed["timestamp"] if viewed else "",
    }


def status_map(job_id: str) -> dict[str, dict]:
    """{candidate_id: current state} for one position."""
    with conn() as c:
        rows = c.execute("SELECT * FROM status_log WHERE job_id=? ORDER BY id", (job_id,)).fetchall()
    grouped: dict[str, list] = {}
    for r in rows:
        grouped.setdefault(r["candidate_id"], []).append(r)
    return {cid: _resolve(rs) for cid, rs in grouped.items()}


def status_log(job_id: str | None = None, cid: str | None = None) -> pd.DataFrame:
    sql, args = "SELECT * FROM status_log", []
    where = []
    if job_id:
        where.append("job_id=?")
        args.append(job_id)
    if cid:
        where.append("candidate_id=?")
        args.append(cid)
    if where:
        sql += " WHERE " + " AND ".join(where)
    with conn() as c:
        return pd.read_sql_query(sql + " ORDER BY id DESC", c, params=args).fillna("")


def pipeline() -> pd.DataFrame:
    """Per position: how many candidates are currently New/Viewed/Shortlisted/Rejected (excluding New)."""
    with conn() as c:
        rows = c.execute("SELECT * FROM status_log ORDER BY id").fetchall()
        titles = {r["job_id"]: r["job_title"] for r in rows}
    grouped: dict[tuple, list] = {}
    for r in rows:
        grouped.setdefault((r["job_id"], r["candidate_id"]), []).append(r)
    counts: dict[str, dict[str, int]] = {}
    for (job_id, _), rs in grouped.items():
        st = _resolve(rs)["status"]
        bucket = counts.setdefault(job_id, {"Viewed": 0, "Shortlisted": 0, "Rejected": 0})
        if st in bucket:
            bucket[st] += 1
    out = [{"Position": f"{titles[j]} ({j})", **v} for j, v in counts.items()]
    return pd.DataFrame(out, columns=["Position", "Viewed", "Shortlisted", "Rejected"])


# ----------------------------------------------------------------------------
# Folder scanning bookkeeping + misc
# ----------------------------------------------------------------------------
def file_unchanged(path: str, size: int, mtime: float) -> bool:
    with conn() as c:
        row = c.execute("SELECT size, mtime FROM files WHERE path=?", (path,)).fetchone()
        return bool(row) and row["size"] == size and abs(row["mtime"] - mtime) < 1e-6


def known_files() -> dict[str, tuple[int, float]]:
    with conn() as c:
        return {r["path"]: (r["size"], r["mtime"]) for r in c.execute("SELECT path, size, mtime FROM files")}


def record_file(path: str, size: int, mtime: float, file_hash: str, status: str, cid: str | None, message: str = "") -> None:
    with conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO files (path, size, mtime, file_hash, status, candidate_id, message) VALUES (?,?,?,?,?,?,?)",
            (path, size, mtime, file_hash, status, cid, message),
        )


def forget_file(path: str) -> None:
    with conn() as c:
        c.execute("DELETE FROM files WHERE path=?", (path,))


def get_meta(key: str, default: str = "") -> str:
    with conn() as c:
        row = c.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row[0] if row else default


def set_meta(key: str, value: str) -> None:
    with conn() as c:
        c.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?,?)", (key, value))
