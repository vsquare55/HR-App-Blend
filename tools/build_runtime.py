"""Builds runtime\\python: a private, relocatable copy of Python plus every package the app needs.

Why: lets you copy the project folder to a computer that has no Python (and no admin rights) and just double-click
Start_HR_App.bat. Run this once on a computer where the app already works:  py tools\\build_runtime.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = Path(sys.base_prefix)
DST = ROOT / "runtime" / "python"
SITE = DST / "Lib" / "site-packages"
ver = f"{sys.version_info.major}{sys.version_info.minor}"

if DST.exists():
    shutil.rmtree(DST)
DST.mkdir(parents=True)

for name in ("python.exe", "pythonw.exe", "python3.dll", f"python{ver}.dll", "vcruntime140.dll", "vcruntime140_1.dll",
             "msvcp140.dll", "LICENSE.txt"):
    if (SRC / name).exists():
        shutil.copy2(SRC / name, DST / name)
shutil.copytree(SRC / "DLLs", DST / "DLLs")
skip = shutil.ignore_patterns("site-packages", "test", "tests", "idlelib", "tkinter", "turtledemo", "__pycache__", "ensurepip")
shutil.copytree(SRC / "Lib", DST / "Lib", ignore=skip)
SITE.mkdir(parents=True, exist_ok=True)

print("Installing the app's packages into the runtime (needs internet the first time)...")
subprocess.check_call([sys.executable, "-m", "pip", "install", "--target", str(SITE), "-r", str(ROOT / "requirements.txt"),
                       "--no-warn-script-location", "--disable-pip-version-check", "--quiet"])

env = dict(os.environ, PYTHONNOUSERSITE="1")
subprocess.check_call([str(DST / "python.exe"), "-c",
                       "import importlib.util as u, sys; "
                       "missing = [m for m in ('streamlit','streamlit_pdf','pandas','openpyxl','pypdf','docx','mammoth') if u.find_spec(m) is None]; "
                       "print('runtime OK:' if not missing else 'MISSING:', missing or sys.version.split()[0]); sys.exit(1 if missing else 0)"],
                      env=env, cwd=str(ROOT))
size = sum(f.stat().st_size for f in DST.rglob("*") if f.is_file()) / 1e6
print(f"Done. runtime\\python is {size:,.0f} MB.")
