"""Things HR can take away: CSV shortlist, merged PDF, email draft (.eml), and the Excel database."""

from __future__ import annotations

import html
import io
import os
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

import pandas as pd

import config
import db


def shortlist_csv(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")  # BOM so Excel shows accents correctly


def resume_path(resume_file: str) -> Path:
    return config.RESUMES_DIR / resume_file


def merge_pdfs(resume_files: list[str]) -> tuple[bytes, list[str]]:
    """Combine the PDF resumes into one file. Returns (pdf bytes, names that could not be included)."""
    from pypdf import PdfWriter

    writer = PdfWriter()
    skipped: list[str] = []
    for rf in resume_files:
        p = resume_path(rf)
        if p.suffix.lower() != ".pdf" or not p.exists():
            skipped.append(rf)
            continue
        try:
            writer.append(str(p), import_outline=False)
        except Exception:
            skipped.append(rf)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue(), skipped


def email_body_text(job_title: str, rows: pd.DataFrame, sender: str) -> str:
    lines = [f"Hi,", "", f"Please find the shortlisted candidates for the position: {job_title}.", ""]
    for i, r in enumerate(rows.itertuples(), 1):
        lines.append(f"{i}. {r.Name} - {r.Title} at {r.Company} | {r.Experience:g} yrs | {r.Location} | {r.Email} | {r.Phone}")
    lines += ["", "Resumes are attached.", "", "Regards,", sender]
    return "\n".join(lines)


def build_eml(subject: str, to: str, body_text: str, rows: pd.DataFrame, attachments: list[tuple[str, bytes]]) -> bytes:
    """An unsent draft (.eml) with an HTML table and the resumes attached. Double-click to open in Outlook."""
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["To"] = to
    msg["X-Unsent"] = "1"  # tells Outlook to open it as an editable draft
    msg.set_content(body_text)
    table = "".join(
        "<tr>" + "".join(f"<td style='padding:4px 10px;border:1px solid #ccc'>{html.escape(str(v))}</td>" for v in r) + "</tr>"
        for r in rows[["Name", "Title", "Company", "Experience", "Location", "Email", "Phone"]].itertuples(index=False)
    )
    head = "".join(
        f"<th style='padding:4px 10px;border:1px solid #ccc;background:#f3f6fb;text-align:left'>{h}</th>"
        for h in ["Name", "Title", "Company", "Exp (yrs)", "Location", "Email", "Phone"]
    )
    intro = html.escape(body_text.split("\n\n")[1]) if "\n\n" in body_text else ""
    msg.add_alternative(
        f"<p>Hi,</p><p>{intro}</p><table style='border-collapse:collapse;font-family:Segoe UI,Arial;font-size:13px'>"
        f"<tr>{head}</tr>{table}</table><p>Resumes are attached.</p>",
        subtype="html",
    )
    for filename, data in attachments:
        maintype, subtype = ("application", "pdf") if filename.lower().endswith(".pdf") else ("application", "octet-stream")
        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)
    return bytes(msg)


# ----------------------------------------------------------------------------
# Excel database that lives next to the resumes
# ----------------------------------------------------------------------------
_CANDIDATE_COLS = [
    ("id", "Candidate ID", 12), ("name", "Name", 24), ("title", "Current title", 28), ("company", "Current company", 24),
    ("experience", "Experience (yrs)", 12), ("location", "Location", 22), ("skills", "Key skills", 60),
    ("summary", "Summary", 70), ("education", "Education", 40), ("email", "Email", 30), ("phone", "Phone", 18),
    ("resume_file", "Resume file", 36), ("parse_notes", "Needs review", 40), ("added_at", "Added", 18),
]


def export_excel() -> tuple[bool, str]:
    """Rewrite Candidates_Database.xlsx beside the resumes. Returns (ok, message)."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    cands = db.load_candidates()
    wb = Workbook()
    ws = wb.active
    ws.title = "Candidates"

    def style_header(sheet, widths):
        fill = PatternFill("solid", fgColor="2B6CB0")
        for i, w in enumerate(widths, 1):
            cell = sheet.cell(row=1, column=i)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = fill
            cell.alignment = Alignment(vertical="center")
            sheet.column_dimensions[get_column_letter(i)].width = w
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions

    ws.append([label for _, label, _ in _CANDIDATE_COLS])
    for _, r in cands.iterrows():
        ws.append([r[key] for key, _, _ in _CANDIDATE_COLS])
        cell = ws.cell(row=ws.max_row, column=[k for k, _, _ in _CANDIDATE_COLS].index("resume_file") + 1)
        if r["resume_file"]:
            cell.hyperlink = str(r["resume_file"]).replace("\\", "/")
            cell.font = Font(color="0563C1", underline="single")
        for col in (7, 8):
            ws.cell(row=ws.max_row, column=col).alignment = Alignment(wrap_text=True, vertical="top")
    style_header(ws, [w for _, _, w in _CANDIDATE_COLS])

    log = db.status_log()
    ws2 = wb.create_sheet("Application_Status")
    cols = [("job_id", "Job ID", 12), ("job_title", "Position", 32), ("candidate_id", "Candidate ID", 12),
            ("candidate_name", "Candidate", 24), ("status", "Status", 14), ("timestamp", "Date and time", 20),
            ("notes", "Notes", 40), ("reviewed_by", "Reviewed by", 18)]
    ws2.append([c[1] for c in cols])
    for _, r in log.iterrows():
        ws2.append([r[c[0]] for c in cols])
    style_header(ws2, [c[2] for c in cols])

    jobs = db.load_jobs()
    ws3 = wb.create_sheet("Open_Jobs")
    jcols = [("id", "Job ID", 12), ("title", "Title", 32), ("department", "Department", 18), ("location", "Location", 20),
             ("experience_required", "Experience", 14), ("status", "Status", 10), ("posted_date", "Posted", 12),
             ("description", "Description", 80)]
    ws3.append([c[1] for c in jcols])
    for _, r in jobs.iterrows():
        ws3.append([r[c[0]] for c in jcols])
    style_header(ws3, [c[2] for c in jcols])

    target = config.EXCEL_PATH
    tmp = target.with_suffix(".tmp.xlsx")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        wb.save(tmp)
        os.replace(tmp, target)  # fails with PermissionError if the workbook is open in Excel
    except PermissionError:
        tmp.unlink(missing_ok=True)
        return False, "Candidates_Database.xlsx is open in Excel. Close it and it will update by itself within a minute."
    except OSError as exc:
        tmp.unlink(missing_ok=True)
        return False, f"Could not write the Excel file: {exc}"
    db.set_meta("excel_dirty", "0")
    db.set_meta("excel_exported_at", datetime.now().strftime("%d %b %Y, %H:%M"))
    return True, f"Excel updated ({len(cands)} candidates)."
