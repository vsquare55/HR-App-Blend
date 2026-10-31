"""Generates 62 mock resumes (PDF / Word / text, 4 layouts) and 16 job descriptions for testing the app.

Run:  py tools\\generate_mock_data.py        (needs: pip install reportlab python-docx)
Writes: mock_resumes\\, sample_job_descriptions\\, sample_jobs.json, tools\\mock_manifest.json (the answer key)
"""

from __future__ import annotations

import json
import random
import re
import shutil
import sys
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape as esc

sys.path.insert(0, str(Path(__file__).parent))
from mock_data import AREA_TO_INSTITUTE, CITIES, COMPANIES, FAMILIES, FIRST, INSTITUTES, JOBS, LANGS, LAST  # noqa: E402

from docx import Document  # noqa: E402
from docx.shared import Pt  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.enums import TA_CENTER, TA_RIGHT  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle  # noqa: E402
from reportlab.lib.units import mm  # noqa: E402
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "mock_resumes"
JD_OUT = ROOT / "sample_job_descriptions"
rnd = random.Random(2026)
TODAY = date.today()
TODAY_IDX = TODAY.year * 12 + TODAY.month - 1
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
MON3 = [m[:3] for m in MONTHS]
JD_RANGE = {j["family"]: tuple(int(x) for x in re.findall(r"\d+", j["exp"])[:2]) for j in JOBS}
INTERN = {"tech": "Software Engineering Intern", "data": "Data Analytics Intern", "product": "Product Intern",
          "design": "Design Intern", "hr": "HR Intern", "marketing": "Marketing Intern", "finance": "Finance Intern",
          "sales": "Sales Intern", "support": "Customer Support Trainee"}
FORMAT_PLAN = ["pdf"] * 47 + ["docx"] * 11 + ["txt"] * 4


# ---------------------------------------------------------------------------------------------
# Build the people
# ---------------------------------------------------------------------------------------------
def years_for(family: str, i: int) -> float:
    lo, hi = JD_RANGE[family]
    if i < 2:  # the first two of each family fit the job description's experience range
        return float(rnd.randint(lo, hi))
    return rnd.choice([0, 0.5, 1, 1.5, 2, 3, 4, 5, 6, 7, 8, 10, 12, 15])


def level_for(T: float) -> int:
    return 0 if T < 2.5 else 1 if T < 5 else 2 if T < 9 else 3


def fill(template: str, skills: list[str]) -> str:
    vals = dict(
        s1=rnd.choice(skills), s2=rnd.choice(skills), s3=rnd.choice(skills), n=rnd.randint(2, 40), p=rnd.randint(20, 90),
        q=rnd.randint(3, 6), m=rnd.randint(1, 2), k=rnd.randint(2, 9), t=rnd.randint(6, 18), c=rnd.randint(85, 97),
    )
    return template.format(**vals)


def make_jobs(fam_key: str, T: float, city: tuple[str, str]) -> list[dict]:
    F = FAMILIES[fam_key]
    area = F["area"]
    M = max(int(round(T * 12)), 4)
    n = 1 if M < 20 else 2 if M < 66 else 3 if M < 126 else 4
    if n == 1:
        durs = [M]
    else:
        durs = [max(9, int(M / n * rnd.uniform(0.75, 1.25))) for _ in range(n - 1)]
        last = M - sum(durs)
        durs = durs + [last] if last >= 8 else [M // n] * (n - 1) + [M - (M // n) * (n - 1)]
    companies = rnd.sample(COMPANIES[area], n)
    lvl = level_for(T)
    jobs, end = [], TODAY_IDX
    for i, d in enumerate(durs):
        start = end - d
        title = INTERN[area] if T < 0.9 else F["ladder"][max(0, lvl - i)]
        jobs.append(dict(title=title, company=companies[i], city=city[0] if rnd.random() < 0.85 else rnd.choice(CITIES)[0],
                         start=start, end=end, present=(i == 0)))
        end = start - rnd.randint(0, 2)
    return jobs


def fmt_dates(j: dict, style: str, sep: str, present_word: str) -> str:
    def one(idx: int) -> str:
        y, m = divmod(idx, 12)
        m += 1
        return {"year": str(y), "monthyear": f"{MON3[m - 1]} {y}", "full": f"{MONTHS[m - 1]} {y}", "numeric": f"{m:02d}/{y}"}[style]

    end = present_word if j["present"] else one(j["end"])
    return f"{one(j['start'])}{sep}{end}"


def true_years(jobs: list[dict]) -> float:
    return round(sum(j["end"] - j["start"] for j in jobs) / 12, 1)


def phone() -> str:
    a, b = rnd.randint(70000, 99999), rnd.randint(10000, 99999)
    return rnd.choice([f"+91 {a} {b}", f"+91-{a}-{b}", f"+91 {a}{b}", f"{a} {b}", f"+91 {a} {b}"])


def email(first: str, last: str) -> str:
    f, l = first.lower(), last.lower()
    return rnd.choice([f"{f}.{l}@gmail.com", f"{f}_{l}@outlook.com", f"{f[0]}.{l}@yahoo.in", f"{f}{l}{rnd.randint(1, 99)}@gmail.com",
                       f"{f}.{l}@hotmail.com", f"{l}.{f}@gmail.com"])


def build_people() -> list[dict]:
    people, used = [], set()
    for fam_key, F in FAMILIES.items():
        for i in range(F["count"]):
            while True:
                first, last = rnd.choice(FIRST), rnd.choice(LAST)
                if (first, last) not in used:
                    used.add((first, last))
                    break
            T = years_for(fam_key, i)
            city = rnd.choice(CITIES)
            jobs = make_jobs(fam_key, T, city)
            core = rnd.sample(F["core"], rnd.randint(max(5, len(F["core"]) - 3), len(F["core"])))
            extra = rnd.sample(F["extra"], rnd.randint(2, min(5, len(F["extra"]))))
            skills = core + [s for s in extra if s not in core]
            rnd.shuffle(skills)
            level = level_for(T)
            title_now = jobs[0]["title"]
            about = rnd.choice(F["about"])
            yrs = f"{int(T)}" if T == int(T) else f"{T}"
            if T < 0.9:
                summary = f"Recent graduate looking for a role in {about}. Completed an internship and several academic projects."
            else:
                summary = (f"{title_now} with {yrs}+ years of experience in {about}. Skilled in {skills[0]}, {skills[1]} and {skills[2]}. "
                           f"{rnd.choice(['Known for clear communication and ownership.', 'Comfortable working with distributed teams.', 'Focused on quality and delivery.'])}")
            for j in jobs:
                j["bullets"] = [fill(b, skills) for b in rnd.sample(F["bullets"], rnd.randint(2, 4))]
            inst_pool = INSTITUTES[AREA_TO_INSTITUTE[F["area"]]]
            grad_year = TODAY.year - int(T) - rnd.randint(3, 5) if T >= 0.9 else TODAY.year - rnd.randint(0, 1)
            edu = [f"{rnd.choice(F['edu'])} - {rnd.choice(inst_pool)} ({grad_year})"]
            certs = rnd.sample(F["certs"], rnd.randint(0, len(F["certs"]))) if T >= 2 else []
            people.append(dict(
                family=fam_key, first=first, last=last, name=f"{first} {last}", email=email(first, last), phone=phone(),
                city=city[0], state=city[1], show_location=rnd.random() > 0.05, T=T, level=level, jobs=jobs, skills=skills,
                summary=summary, edu=edu, certs=certs, langs=rnd.choice(LANGS), group_labels=F["group_labels"],
                # presentation choices (make the files look different from each other)
                date_style=rnd.choice(["year", "monthyear", "monthyear", "full", "numeric"]),
                sep=rnd.choice([" - ", " – ", " to "]), present_word=rnd.choice(["Present", "Present", "Current", "Till date"]),
                job_fmt=rnd.choice([1, 1, 2, 3, 4]), skills_fmt=rnd.choice(["bullets", "commas", "grouped", "twospace"]),
                contact_fmt=rnd.choice(["oneline", "lines", "labels"]),
                headings=dict(
                    summary=rnd.choice(["PROFESSIONAL SUMMARY", "SUMMARY", "PROFILE", "ABOUT ME", "Professional Profile"]),
                    skills=rnd.choice(["TECHNICAL SKILLS", "SKILLS", "KEY SKILLS", "CORE COMPETENCIES", "TECHNICAL EXPERTISE", "SKILLS & TOOLS"]),
                    experience=rnd.choice(["PROFESSIONAL EXPERIENCE", "WORK EXPERIENCE", "EXPERIENCE", "EMPLOYMENT HISTORY", "WORK HISTORY"]),
                    education=rnd.choice(["EDUCATION", "ACADEMIC BACKGROUND", "QUALIFICATIONS"]),
                ),
                upper_name=rnd.random() < 0.25,
            ))
    rnd.shuffle(people)
    return people


# ---------------------------------------------------------------------------------------------
# Shared text helpers
# ---------------------------------------------------------------------------------------------
def location_text(p: dict) -> str:
    return f"{p['city']}, {p['state']}" if p["show_location"] else ""


def display_name(p: dict) -> str:
    return p["name"].upper() if p["upper_name"] else p["name"]


def contact_lines(p: dict) -> list[str]:
    loc = location_text(p)
    if p["contact_fmt"] == "oneline":
        return [" | ".join(x for x in [p["email"], p["phone"], loc] if x)]
    if p["contact_fmt"] == "lines":
        return [x for x in [p["email"], p["phone"], loc] if x]
    parts = [f"Email: {p['email']}", f"Phone: {p['phone']}"] + ([f"Location: {loc}"] if loc else [])
    return ["   ".join(parts)]


def skills_text(p: dict) -> list[str]:
    s = p["skills"]
    if p["skills_fmt"] == "bullets":
        return [" • ".join(s)]
    if p["skills_fmt"] == "commas":
        return [", ".join(s)]
    if p["skills_fmt"] == "twospace":
        return ["  ".join(s)]
    n = len(p["group_labels"])
    chunks = [s[i::n] for i in range(n)]
    return [f"{lab}: {', '.join(c)}" for lab, c in zip(p["group_labels"], chunks) if c]


def job_header(p: dict, j: dict) -> list[tuple[str, bool]]:
    dates = fmt_dates(j, p["date_style"], p["sep"], p["present_word"])
    f = p["job_fmt"]
    if f == 1:
        return [(j["title"], True), (f"{j['company']} | {dates}", False)]
    if f == 2:
        return [(f"{j['title']} at {j['company']}", True), (dates, False)]
    if f == 3:
        return [(f"{j['title']} - {j['company']}  ({dates})", True)]
    return [(f"{j['company']}, {j['city']}", True), (f"{j['title']}, {dates}", False)]


def file_name(p: dict, ext: str, used: set[str]) -> str:
    f, l = p["first"], p["last"]
    fam = {"python_backend": "Python_Developer", "java_backend": "Java_Developer", "fullstack": "FullStack", "ml": "ML_Engineer",
           "data_analyst": "Data_Analyst", "data_engineer": "Data_Engineer", "devops": "DevOps", "qa": "QA_Automation",
           "mobile": "Mobile_Developer", "pm": "Product_Manager", "designer": "UX_Designer", "hr": "HR_Recruiter",
           "marketing": "Digital_Marketing", "finance": "Accountant", "sales": "Sales_BD", "support": "Customer_Support"}[p["family"]]
    base = rnd.choice([f"{f}_{l}_Resume", f"{l}_{f}_CV", f"{f}{l}_{fam}", f"Resume_{f}_{l}", f"CV - {f} {l}", f"{f}_{l[0]}_Resume_Final",
                       f"{f}_{l}_{fam}_{TODAY.year}", f"{f}-{l}-resume"])
    name, n = f"{base}.{ext}", 1
    while name.lower() in used:
        n += 1
        name = f"{base}_{n}.{ext}"
    used.add(name.lower())
    return name


# ---------------------------------------------------------------------------------------------
# PDF layouts
# ---------------------------------------------------------------------------------------------
PALETTE = [colors.HexColor(c) for c in ["#1f4e79", "#2b6cb0", "#276749", "#8a2be2", "#b03a2e", "#0e6655", "#34495e", "#9c4221"]]


def styles(font: str, bold: str, accent, size: float = 9.5) -> dict[str, ParagraphStyle]:
    lead = size + 3.4
    return dict(
        name=ParagraphStyle("name", fontName=bold, fontSize=22, leading=26, textColor=accent),
        sub=ParagraphStyle("sub", fontName=font, fontSize=11, leading=14, textColor=colors.HexColor("#444444")),
        contact=ParagraphStyle("contact", fontName=font, fontSize=size, leading=lead, textColor=colors.HexColor("#333333")),
        h=ParagraphStyle("h", fontName=bold, fontSize=size + 1, leading=lead + 1, textColor=accent, spaceBefore=9, spaceAfter=2),
        body=ParagraphStyle("body", fontName=font, fontSize=size, leading=lead),
        bold=ParagraphStyle("bold", fontName=bold, fontSize=size + 0.5, leading=lead, spaceBefore=4),
        bullet=ParagraphStyle("bullet", fontName=font, fontSize=size, leading=lead, leftIndent=11, bulletIndent=2),
        right=ParagraphStyle("right", fontName=font, fontSize=size, leading=lead, alignment=TA_RIGHT, textColor=colors.HexColor("#555555")),
    )


def sections(p: dict, st: dict, rule_color=None) -> dict[str, list]:
    """Flowables for each section, shared by the layouts that stack sections vertically."""
    H = p["headings"]

    def head(title: str) -> list:
        out = [Paragraph(esc(title), st["h"])]
        if rule_color is not None:
            out.append(HRFlowable(width="100%", thickness=0.6, color=rule_color, spaceAfter=3))
        return out

    summary = head(H["summary"]) + [Paragraph(esc(p["summary"]), st["body"])]
    skills = head(H["skills"]) + [Paragraph(esc(t), st["body"]) for t in skills_text(p)]
    exp = head(H["experience"])
    for j in p["jobs"]:
        for text, is_bold in job_header(p, j):
            exp.append(Paragraph(esc(text), st["bold"] if is_bold else st["body"]))
        exp += [Paragraph(esc(b), st["bullet"], bulletText="•") for b in j["bullets"]]
    edu = head(H["education"]) + [Paragraph(esc(t), st["body"]) for t in p["edu"]]
    extra = []
    if p["certs"]:
        extra += head("CERTIFICATIONS") + [Paragraph(esc(c), st["bullet"], bulletText="•") for c in p["certs"]]
    extra += head("LANGUAGES") + [Paragraph(esc(p["langs"]), st["body"])]
    return dict(summary=summary, skills=skills, exp=exp, edu=edu, extra=extra)


def doc_for(path: Path, p: dict, margins=(18, 15)) -> SimpleDocTemplate:
    return SimpleDocTemplate(str(path), pagesize=A4, leftMargin=margins[0] * mm, rightMargin=margins[0] * mm,
                             topMargin=margins[1] * mm, bottomMargin=margins[1] * mm, title=f"{p['name']} - Resume", author=p["name"])


def pdf_classic(path: Path, p: dict, serif: bool = False) -> None:
    accent = colors.black if serif else rnd.choice(PALETTE)
    font, bold = ("Times-Roman", "Times-Bold") if serif else ("Helvetica", "Helvetica-Bold")
    st = styles(font, bold, accent, 10 if serif else 9.5)
    center = ParagraphStyle("c", parent=st["name"], alignment=TA_CENTER)
    ccont = ParagraphStyle("cc", parent=st["contact"], alignment=TA_CENTER)
    flow = [Paragraph(esc(display_name(p)), center if not serif else st["name"])]
    flow += [Paragraph(esc(t), ccont if not serif else st["contact"]) for t in contact_lines(p)]
    flow.append(HRFlowable(width="100%", thickness=1.2, color=accent, spaceBefore=4, spaceAfter=4))
    s = sections(p, st, rule_color=accent)
    for key in ("summary", "skills", "exp", "edu", "extra"):
        flow += s[key]
    doc_for(path, p).build(flow)


def pdf_banner(path: Path, p: dict) -> None:
    accent = rnd.choice(PALETTE)
    st = styles("Helvetica", "Helvetica-Bold", accent, 9.5)
    white_name = ParagraphStyle("wn", parent=st["name"], textColor=colors.white, fontSize=24, leading=28)
    white_sub = ParagraphStyle("ws", parent=st["sub"], textColor=colors.white, fontSize=12)
    w = A4[0] - 24 * mm
    banner = Table([[[Paragraph(esc(display_name(p)), white_name), Paragraph(esc(p["jobs"][0]["title"]), white_sub)]]], colWidths=[w])
    banner.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), accent), ("LEFTPADDING", (0, 0), (-1, -1), 12),
                                ("TOPPADDING", (0, 0), (-1, -1), 12), ("BOTTOMPADDING", (0, 0), (-1, -1), 12)]))
    flow = [banner, Spacer(1, 5)] + [Paragraph(esc(t), st["contact"]) for t in contact_lines(p)]
    s = sections(p, st)
    flow += s["summary"] + s["skills"]
    flow += [Paragraph(esc(p["headings"]["experience"]), st["h"])]
    for j in p["jobs"]:  # job title / company on the left, dates on the right (as in many templates)
        dates = fmt_dates(j, p["date_style"], p["sep"], p["present_word"])
        row = Table([[[Paragraph(esc(j["title"]), st["bold"]), Paragraph(esc(j["company"]), st["body"])], Paragraph(esc(dates), st["right"])]],
                    colWidths=[w * 0.68, w * 0.32])
        row.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
        flow.append(row)
        flow += [Paragraph(esc(b), st["bullet"], bulletText="•") for b in j["bullets"]]
    flow += s["edu"] + s["extra"]
    doc_for(path, p, (12, 12)).build(flow)


def pdf_sidebar(path: Path, p: dict) -> None:
    accent = rnd.choice(PALETTE)
    st = styles("Helvetica", "Helvetica-Bold", accent, 9)
    wl = ParagraphStyle("wl", parent=st["body"], textColor=colors.white)
    wh = ParagraphStyle("wh", parent=st["bold"], textColor=colors.white, spaceBefore=10)
    wn = ParagraphStyle("wn", parent=st["name"], textColor=colors.white, fontSize=18, leading=21)
    H = p["headings"]
    left = [Paragraph(esc(display_name(p)), wn), Paragraph(esc(p["jobs"][0]["title"]), wl), Spacer(1, 8)]
    left += [Paragraph(esc(t), wl) for t in contact_lines(p)]
    left += [Paragraph(esc(H["skills"]), wh)] + [Paragraph(esc(t), wl) for t in skills_text(p)]
    left += [Paragraph(esc(H["education"]), wh)] + [Paragraph(esc(t), wl) for t in p["edu"]]
    left += [Paragraph("LANGUAGES", wh), Paragraph(esc(p["langs"]), wl)]
    s = sections(p, st, rule_color=accent)
    right = s["summary"] + s["exp"] + (s["extra"][:-3] if p["certs"] else [])  # languages are already in the sidebar
    t = Table([[left, right]], colWidths=[62 * mm, A4[0] - 24 * mm - 62 * mm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, 0), accent), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("LEFTPADDING", (0, 0), (0, 0), 8), ("RIGHTPADDING", (0, 0), (0, 0), 8), ("LEFTPADDING", (1, 0), (1, 0), 12),
                           ("TOPPADDING", (0, 0), (-1, -1), 10)]))
    doc_for(path, p, (12, 12)).build([t])


def make_pdf(path: Path, p: dict, layout: str) -> str:
    try:
        {"classic": pdf_classic, "banner": pdf_banner, "sidebar": pdf_sidebar, "serif": lambda a, b: pdf_classic(a, b, serif=True)}[layout](path, p)
        return layout
    except Exception:  # a layout that cannot fit the content falls back to the classic one
        path.unlink(missing_ok=True)
        pdf_classic(path, p)
        return "classic"


# ---------------------------------------------------------------------------------------------
# Word and text
# ---------------------------------------------------------------------------------------------
def make_docx(path: Path, p: dict) -> None:
    d = Document()
    normal = d.styles["Normal"]
    normal.font.name = rnd.choice(["Calibri", "Arial", "Cambria"])
    normal.font.size = Pt(10.5)
    para = d.add_paragraph()
    r = para.add_run(display_name(p))
    r.bold, r.font.size = True, Pt(20)
    for t in contact_lines(p):
        d.add_paragraph(t)

    def heading(text: str) -> None:
        hp = d.add_paragraph()
        hr = hp.add_run(text)
        hr.bold, hr.font.size = True, Pt(12)

    H = p["headings"]
    heading(H["summary"])
    d.add_paragraph(p["summary"])
    heading(H["skills"])
    for t in skills_text(p):
        d.add_paragraph(t)
    heading(H["experience"])
    for j in p["jobs"]:
        for text, is_bold in job_header(p, j):
            line = d.add_paragraph()
            run = line.add_run(text)
            run.bold = is_bold
        for b in j["bullets"]:
            d.add_paragraph(b, style="List Bullet")
    heading(H["education"])
    for t in p["edu"]:
        d.add_paragraph(t)
    if p["certs"]:
        heading("CERTIFICATIONS")
        for c in p["certs"]:
            d.add_paragraph(c, style="List Bullet")
    d.save(path)


def make_txt(path: Path, p: dict) -> None:
    H = p["headings"]
    lines = [display_name(p), *contact_lines(p), "", H["summary"], p["summary"], "", H["skills"], *skills_text(p), "", H["experience"]]
    for j in p["jobs"]:
        lines += [t for t, _ in job_header(p, j)]
        lines += [f"- {b}" for b in j["bullets"]]
        lines.append("")
    lines += [H["education"], *p["edu"]]
    if p["certs"]:
        lines += ["", "CERTIFICATIONS", *p["certs"]]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------------------------
# Job descriptions
# ---------------------------------------------------------------------------------------------
def jd_text(j: dict) -> str:
    lines = [f"Job Title: {j['title']}", f"Department: {j['department']}", f"Location: {j['location']}", f"Experience: {j['exp']}", "",
             "About the role", j["about"], "", "Responsibilities", *[f"- {x}" for x in j["resp"]], "", "Requirements",
             *[f"- {x}" for x in j["must"]], "", "Nice to have", *[f"- {x}" for x in j["nice"]]]
    return "\n".join(lines) + "\n"


def write_jd_files() -> None:
    if JD_OUT.exists():
        shutil.rmtree(JD_OUT)
    JD_OUT.mkdir()
    for i, j in enumerate(JOBS, 1):
        slug = re.sub(r"[^A-Za-z0-9]+", "_", j["title"]).strip("_")
        text = jd_text(j)
        stem = f"JD{i:02d}_{slug}"
        if i in (3, 8, 12):  # a few Word and PDF versions so uploading different file types can be tested
            d = Document()
            for k, line in enumerate(text.splitlines()):
                para = d.add_paragraph(line)
                if line in ("About the role", "Responsibilities", "Requirements", "Nice to have") or k == 0:
                    for r in para.runs:
                        r.bold = True
            d.save(JD_OUT / f"{stem}.docx")
        elif i in (5, 14):
            st = styles("Helvetica", "Helvetica-Bold", colors.HexColor("#1f4e79"), 10.5)
            flow = [Paragraph(esc(j["title"]), st["name"]), Spacer(1, 6)]
            for line in text.splitlines()[1:]:
                if line in ("About the role", "Responsibilities", "Requirements", "Nice to have"):
                    flow.append(Paragraph(esc(line), st["h"]))
                elif line.startswith("- "):
                    flow.append(Paragraph(esc(line[2:]), st["bullet"], bulletText="•"))
                elif line:
                    flow.append(Paragraph(esc(line), st["body"]))
            SimpleDocTemplate(str(JD_OUT / f"{stem}.pdf"), pagesize=A4, title=j["title"]).build(flow)
        else:
            (JD_OUT / f"{stem}.txt").write_text(text, encoding="utf-8")
    (ROOT / "sample_jobs.json").write_text(json.dumps([
        dict(title=j["title"], department=j["department"], location=j["location"], experience_required=j["exp"], description=jd_text(j))
        for j in JOBS], indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------------------------
def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    people = build_people()
    formats = FORMAT_PLAN[:]
    rnd.shuffle(formats)
    layouts = ["classic", "banner", "sidebar", "serif"]
    used: set[str] = set()
    manifest = []
    pdf_i = 0
    for p, ext in zip(people, formats):
        fname = file_name(p, ext, used)
        path = OUT / fname
        layout = ext
        if ext == "pdf":
            layout = make_pdf(path, p, layouts[pdf_i % 4])
            pdf_i += 1
        elif ext == "docx":
            make_docx(path, p)
        else:
            make_txt(path, p)
        manifest.append(dict(
            file=fname, family=p["family"], name=p["name"], email=p["email"], phone_digits=re.sub(r"\D", "", p["phone"])[-10:],
            city=p["city"] if p["show_location"] else "", title=p["jobs"][0]["title"], company=p["jobs"][0]["company"],
            experience=true_years(p["jobs"]), skills=p["skills"], format=ext, layout=layout, date_style=p["date_style"],
            job_fmt=p["job_fmt"],
        ))
    (Path(__file__).parent / "mock_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    write_jd_files()
    by_fmt = {k: sum(1 for m in manifest if m["format"] == k) for k in ("pdf", "docx", "txt")}
    print(f"{len(manifest)} resumes written to {OUT} {by_fmt}")
    print("PDF layouts:", {k: sum(1 for m in manifest if m['layout'] == k) for k in ('classic', 'banner', 'sidebar', 'serif')})
    print(f"{len(JOBS)} job descriptions written to {JD_OUT} and sample_jobs.json")


if __name__ == "__main__":
    main()
