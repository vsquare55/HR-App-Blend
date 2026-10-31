"""Paths and settings. Everything runs locally; nothing is sent to the internet.

The whole project folder is portable: copy it to another computer and start it there. Everything is found relative
to this folder. To use a different resume folder (for example a OneDrive-synced one), edit `config.json`
in the project root:  {"resumes_dir": "C:/Users/you/OneDrive/HR/Resumes"}   or set HR_RESUMES_DIR.
If that folder does not exist on the computer you are on (e.g. you copied the project to another laptop), the app
falls back to the `resumes` folder inside the project and tells you.
"""

import json
import os
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA_DIR = BASE / "data"
DB_PATH = DATA_DIR / "hr.db"
CONFIG_PATH = BASE / "config.json"
LEGACY_EXCEL = DATA_DIR / "Candidates_Database.xlsx"  # old demo workbook, only used to seed positions if nothing else exists
SAMPLE_JOBS = BASE / "sample_jobs.json"

_DEFAULTS = {"resumes_dir": "resumes"}


def _load() -> dict:
    cfg = dict(_DEFAULTS)
    if CONFIG_PATH.exists():
        try:
            cfg.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass
    else:
        try:
            CONFIG_PATH.write_text(json.dumps(_DEFAULTS, indent=2), encoding="utf-8")
        except OSError:
            pass
    env = os.environ.get("HR_RESUMES_DIR")
    if env:
        cfg["resumes_dir"] = env
    return cfg


def _resolve(p: str) -> Path:
    path = Path(p).expanduser()
    return path if path.is_absolute() else (BASE / path)


CONFIG = _load()
RESUMES_DIR = _resolve(CONFIG["resumes_dir"])
CONFIG_NOTE = ""
if not RESUMES_DIR.exists() and not RESUMES_DIR.parent.exists():
    # e.g. config.json points at C:/Users/<someone>/OneDrive/... which this computer does not have
    CONFIG_NOTE = f"The folder in config.json was not found on this computer ({RESUMES_DIR}). Using the project's own 'resumes' folder instead."
    RESUMES_DIR = BASE / "resumes"
EXCEL_PATH = RESUMES_DIR / "Candidates_Database.xlsx"
