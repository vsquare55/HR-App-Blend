"""Copies the 62 mock resumes into the resumes folder (the one the app watches)."""

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
import config  # noqa: E402

src = ROOT / "mock_resumes"
if not src.exists():
    sys.exit("The mock_resumes folder was not found next to this script.")
config.RESUMES_DIR.mkdir(parents=True, exist_ok=True)
n = 0
for f in sorted(src.iterdir()):
    if f.is_file() and not (config.RESUMES_DIR / f.name).exists():
        shutil.copy2(f, config.RESUMES_DIR / f.name)
        n += 1
print(f"Copied {n} mock resume(s) into: {config.RESUMES_DIR}")
print("If the app is running it imports them within seconds. If not, start it with Start_HR_App.bat.")
