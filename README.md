# HR resume matcher (local version)

Runs entirely on one computer. Nothing is uploaded anywhere, no IT setup needed, and the whole folder can be
copied to another laptop.

```
resumes\  ──►  database  ──►  Candidates_Database.xlsx  (in the same folder as the resumes)
(drop PDF / Word / text files)   │
                                 └─►  Dashboard: pick a position or paste / upload a job description
                                      → ranked candidates → view the real resume → viewed / shortlisted / rejected (dated)
                                      → export CSV, one combined PDF, or an email draft
```

## Start it

Double-click **`Start_HR_App.bat`**. The browser opens at http://localhost:8501. Keep the black window open while you
work; close it to stop the app. The black window also prints a line every time a new resume is imported.

## Try it with the mock data

The folder comes with **62 mock resumes** (`mock_resumes\`: 47 PDF in 4 different layouts, 11 Word, 4 text, across 16
kinds of roles) and **16 job descriptions** (`sample_job_descriptions\`: text, Word and PDF).

1. Double-click **`Load_Mock_Resumes.bat`**. Within seconds the *Resumes* counter in the sidebar goes up by 62.
2. Open the **Positions** tab. If it does not already list 16 positions, open *Sample positions for testing* and click
   *Load sample positions*.
3. **Find candidates** tab: pick a position, click *Find matching candidates*. Try each of the five ranking modes.
4. Click **View resume** on a candidate. The real resume opens in the side drawer (PDF as is; Word files are shown
   as the actual page). Click *Shortlist* or *Reject*, then check the *Activity* tab for the dated log.
5. Tick several candidates and use *Export* (CSV report, all resumes in one PDF, email draft).
6. Test your own flow: choose *Custom search*, then paste a job description **or upload one** from
   `sample_job_descriptions\` with *Or upload a job description file*.

What the top results should be for each position (the mock resumes were made with these roles):

| Position | Should rank on top |
|---|---|
| Senior Python Backend Engineer | Python / backend developers |
| Java Backend Developer - Microservices | Java developers |
| Full Stack Developer (React + Node) | Full stack / frontend |
| Machine Learning Engineer | ML engineers / data scientists |
| Data Analyst - Power BI and SQL | Data / BI analysts |
| Senior Data Engineer | Data engineers |
| DevOps / SRE Engineer | DevOps / cloud |
| QA Automation Engineer | QA automation |
| Mobile App Developer | Android / iOS / Flutter |
| Product Manager - B2B SaaS | Product managers |
| UI/UX Designer | Designers |
| Talent Acquisition Specialist | HR / recruiters |
| Digital Marketing Manager | Marketing |
| Senior Accountant - GST and Finance | Accountants |
| Business Development Manager - SaaS Sales | Sales / BD |
| Customer Support Team Lead | Support |

To test the automatic folder watching, drag a file from `test_new_resumes\` into `resumes\` while the app is open:
within about 10 seconds the black window prints `Added 1 new resume(s)`, the sidebar counter goes up, and a new row
appears in `resumes\Candidates_Database.xlsx` (close Excel afterwards; if it was open the app updates it by itself
within a minute of you closing it).

To start over: close the app and double-click **`Reset_Demo_Data.bat`** (asks you to type YES; your resume files are kept).

## Take it to another computer (for example your office laptop)

1. Close the app. Optional: run `Reset_Demo_Data.bat` so the other laptop starts clean
   (otherwise `data\hr.db` carries your test candidates and decisions along).
2. Copy the **whole folder** (USB stick, OneDrive, or zip it). It is about 400 MB because the `runtime` folder holds
   a private copy of Python and every package the app needs. A ready-made, clean zip (`HR_Resume_Demo_Portable.zip`,
   about 100 MB, without your test data) is in your Downloads folder. Unzip it somewhere short such as
   `C:\HR` or the Desktop: Windows has a 260-character path limit and some packaged files have long names.
3. On the other laptop, double-click **`Start_HR_App.bat`**. No Python install, no internet and no admin rights are
   needed, because `runtime\python` travels with the folder. (I checked this by copying the folder to a different
   path with spaces in it, with no Python available on the PATH.)
4. Optional: `Load_Mock_Resumes.bat` to get the mock data again.

Good to know:
- The default resume folder is `resumes` inside the project, so nothing needs changing. If `config.json` points to a
  folder that does not exist on the new laptop (for example a OneDrive path from your own PC), the app tells you
  and uses the project's own `resumes` folder. To use a OneDrive folder on the new laptop, edit `config.json`:
  `{ "resumes_dir": "C:/Users/YourName/OneDrive - Company/HR/Resumes" }`.
- If the company laptop blocks running programs from your folders (AppLocker / antivirus), the app can still run
  with a normally installed Python 3.10 or newer: delete the `runtime` folder, and `Start_HR_App.bat` installs the
  packages with pip the first time (needs internet access to PyPI).
- If Microsoft Word is installed, Word resumes are shown exactly as the document looks (converted once, then cached).
  Without Word they are shown as a formatted page, which is close but not identical.
- Only the computer running the app can open it (`address = "localhost"` in `.streamlit\config.toml`). To let
  colleagues use it, run it on one always-on PC and change that to `"0.0.0.0"`. There is no login yet, so do that
  only on a trusted network and ask IT first.
- Rebuilding the runtime (for example after upgrading packages): `Build_Portable_Runtime.bat` on a computer with Python.

## Daily use

1. **Add resumes**: copy PDF / Word / text files into the `resumes` folder (or use the *Add resumes* tab). The watcher
   checks the folder every 10 seconds, reads each new file, adds the candidate and updates
   `Candidates_Database.xlsx`. The same file added twice is skipped.
2. **Find candidates**: pick an open position, or paste / upload any job description. Add must-have skills if you
   like (they count double). Choose a ranking mode: Balanced, Skills match, Experience weighted, Keyword relevance,
   or Role fit.
3. **Review**: *View resume* opens the real resume in a side drawer and marks it **Viewed**. *Shortlist* and *Reject*
   (with a reason) are saved per position with date, time and your name.
4. **Act on several**: tick candidates, then *Shortlist*, *Reject* or *Export* (CSV report, all resumes merged into
   one PDF, or an email draft with the resumes attached: open the `.eml` file in Outlook).
5. **Fix mistakes**: in *All candidates*, select a row to correct name, title, skills, etc. Rows the app was unsure
   about are flagged under *Needs review only*.

## Use your own resumes

Close the app, delete the sample PDFs in `resumes\` (or run `Reset_Demo_Data.bat`), copy your real resumes in, and
start the app. 1000 resumes import in a few minutes.

## Good to know

- Reading resumes is rule-based, not AI. On the 62 mock resumes (which use messy, varied formats) it got name,
  email, phone, location, title, company and skills right every time, but real resumes are messier. Skim
  *Needs review only* after a big import.
- Scanned (image-only) PDFs contain no text. They are added with the file name and flagged for review.
- Ranking is transparent: matched skills are shown in green and missing ones are listed under each candidate.
- Back up by copying the `data` and `resumes` folders.

## Files

| Path | Purpose |
|---|---|
| `Start_HR_App.bat` | Starts the dashboard and the background folder watcher |
| `Load_Mock_Resumes.bat`, `Reset_Demo_Data.bat` | Add the 62 mock resumes / clear the database |
| `Build_Portable_Runtime.bat` | Rebuilds the `runtime` folder |
| `app\` | The application (`app.py` dashboard, `resume_parser.py`, `matcher.py`, `preview.py` and the rest) |
| `mock_resumes\`, `sample_job_descriptions\`, `sample_jobs.json`, `test_new_resumes\` | Test data |
| `tools\` | Scripts behind the .bat files and the generator for the mock data (`generate_mock_data.py`) |
| `config.json` | Resume folder location |
| `data\hr.db` | The database (created on first run) |
| `runtime\` | Private Python that makes the folder portable |
