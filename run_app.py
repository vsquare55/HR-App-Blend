"""Starts the dashboard AND a background folder watcher.

The watcher imports new resumes and updates Candidates_Database.xlsx every few seconds, even when no
browser tab is open. Run it with Start_HR_App.bat (or:  py run_app.py).  Press Ctrl+C or close the window to stop.
"""

import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "app"))

import config  # noqa: E402
import db  # noqa: E402
import ingest  # noqa: E402

INTERVAL_SECONDS = 10


def stamp() -> str:
    return datetime.now().strftime("%H:%M:%S")


def watch() -> None:
    db.init_db()
    print(f"[{stamp()}] Watching for new resumes in: {config.RESUMES_DIR}", flush=True)
    while True:
        busy = False
        try:
            res = ingest.scan_folder(max_new=50)
            busy = res.remaining > 0
            if res.added:
                names = ", ".join(res.added[:5]) + ("..." if len(res.added) > 5 else "")
                print(f"[{stamp()}] Added {len(res.added)} new resume(s): {names}", flush=True)
                print(f"[{stamp()}] {res.excel_message}", flush=True)
            if res.duplicates:
                print(f"[{stamp()}] Skipped {res.duplicates} duplicate file(s)", flush=True)
            for problem in res.failed:
                print(f"[{stamp()}] Problem: {problem}", flush=True)
        except Exception as exc:  # never let the watcher die
            print(f"[{stamp()}] Watcher error: {exc}", flush=True)
        time.sleep(1 if busy else INTERVAL_SECONDS)


if __name__ == "__main__":
    threading.Thread(target=watch, daemon=True, name="folder-watcher").start()
    cmd = [sys.executable, "-m", "streamlit", "run", str(ROOT / "app" / "app.py"), *sys.argv[1:]]
    proc = subprocess.Popen(cmd, cwd=ROOT)  # cwd = project root so .streamlit\config.toml is used
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
