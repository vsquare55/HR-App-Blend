"""Clears the database (candidates, positions you added, viewed / shortlisted / rejected history) and the Excel file.

The resume files themselves are NOT touched. After a reset the app re-imports whatever is in the resumes folder.
"""

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
import config  # noqa: E402

print("This will delete:")
print(f"  - the database           {config.DB_PATH}")
print(f"  - the Excel database     {config.EXCEL_PATH}")
print("  - all viewed / shortlisted / rejected history")
print(f"Your resume files in {config.RESUMES_DIR} are kept.")
if input("\nType YES to continue: ").strip() != "YES":
    sys.exit("Cancelled. Nothing was deleted.")

for p in [config.DB_PATH, Path(str(config.DB_PATH) + "-wal"), Path(str(config.DB_PATH) + "-shm"), config.EXCEL_PATH]:
    p.unlink(missing_ok=True)
shutil.rmtree(config.DATA_DIR / "previews", ignore_errors=True)
print("Done. Start the app again; it re-imports the resumes folder.")
