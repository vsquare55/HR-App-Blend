"""Resume text extraction and field parsing. Pure Python, works offline.

parse_resume(data, filename) -> dict with name, email, phone, location, title, company,
experience (years), education, skills (comma separated), summary, resume_text, notes.

The parsing is heuristic: it handles the common resume layouts well and flags anything it
is unsure about in `notes` so a human can correct it in the app.
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date
from pathlib import Path

logging.getLogger("pypdf").setLevel(logging.CRITICAL)  # keep the console quiet for slightly broken PDFs

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}


# ----------------------------------------------------------------------------
# Text extraction
# ----------------------------------------------------------------------------
def _pdf_text(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception:
            return ""
    parts = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            parts.append("")
    return "\n".join(parts)


def _docx_text(data: bytes) -> str:
    from docx import Document
    from docx.table import Table

    doc = Document(io.BytesIO(data))
    out: list[str] = []
    for section in doc.sections:  # contact details often live in the page header
        out.extend(p.text for p in section.header.paragraphs if p.text.strip())
    for block in doc.iter_inner_content():
        if isinstance(block, Table):
            for row in block.rows:
                cells = []
                for cell in row.cells:
                    if cell.text.strip() and cell.text.strip() not in cells:
                        cells.append(cell.text.strip())
                if cells:
                    out.append("  ".join(cells))
        elif block.text.strip():
            out.append(block.text)
    return "\n".join(out)


def extract_text(data: bytes, filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        raw = _pdf_text(data)
    elif ext == ".docx":
        raw = _docx_text(data)
    elif ext == ".txt":
        raw = data.decode("utf-8", errors="replace")
    else:
        raise ValueError(f"Unsupported file type: {ext or 'unknown'}")
    return clean_text(raw)


def clean_text(text: str) -> str:
    text = text.replace(" ", " ").replace("\r\n", "\n").replace("\r", "\n")
    # bullet glyphs (and the control / private-use characters PDFs often use for them) -> a plain bullet
    text = re.sub(r"[•●▪◦‣■⁃∙-\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "•", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ----------------------------------------------------------------------------
# Sections
# ----------------------------------------------------------------------------
_HEADINGS = {
    "summary": [
        "professional summary", "summary", "profile", "professional profile", "career objective",
        "objective", "about me", "about", "career summary", "executive summary", "personal profile",
        "summary of qualifications", "profile summary",
    ],
    "skills": [
        "technical skills", "skills", "key skills", "core competencies", "skills & tools",
        "skills and tools", "technical expertise", "core skills", "areas of expertise", "technologies",
        "tech stack", "technical proficiency", "skill set", "skills summary", "it skills", "competencies",
        "tools & technologies", "tools and technologies",
    ],
    "experience": [
        "professional experience", "work experience", "experience", "employment history", "work history",
        "employment", "career history", "relevant experience", "internships", "internship experience",
        "professional background", "experience summary", "employment experience",
    ],
    "education": [
        "education", "academic background", "academic qualifications", "education & training",
        "qualifications", "educational qualifications", "academics", "education and training",
        "academic profile", "educational background",
    ],
    "projects": ["projects", "key projects", "academic projects", "personal projects", "project experience"],
    "other": [
        "certifications", "certification", "certificates", "licenses & certifications", "languages",
        "achievements", "awards", "awards & achievements", "interests", "hobbies", "references",
        "declaration", "personal details", "personal information", "publications", "volunteering",
        "extracurricular activities", "courses", "training", "contact", "contact details",
    ],
}
_HEADING_LOOKUP = {alias: key for key, aliases in _HEADINGS.items() for alias in aliases}
_INLINE_HEADING = re.compile(r"^(?P<h>[A-Za-z &/]{3,32}?)\s*[:：]\s*(?P<rest>\S.*)$")


def _heading_key(line: str) -> str | None:
    s = line.strip().strip(":-_*#|• –—").lower()
    s = re.sub(r"[^a-z &/]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return _HEADING_LOOKUP.get(s) if 0 < len(s) <= 40 else None


def split_sections(text: str) -> dict[str, list[str]]:
    """Return {'header': [...], 'summary': [...], 'skills': [...], ...} (non-empty lines)."""
    sections: dict[str, list[str]] = {"header": []}
    current = "header"
    for raw in text.split("\n"):
        line = raw.strip()
        if not line:
            continue
        key = _heading_key(line)
        if key:
            current = key
            sections.setdefault(current, [])
            continue
        m = _INLINE_HEADING.match(line)
        if m and (k2 := _HEADING_LOOKUP.get(re.sub(r"\s+", " ", m.group("h").strip().lower()))):
            current = k2
            sections.setdefault(current, []).append(m.group("rest").strip())
            continue
        sections.setdefault(current, []).append(line)
    return sections


# ----------------------------------------------------------------------------
# Contact details
# ----------------------------------------------------------------------------
_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)+")
_PHONE = re.compile(r"(?<![\w])(\+?\d[\d\s().\-]{8,17}\d)(?![\w])")
_YEAR_ONLY_RUN = re.compile(r"(?:(?:19|20)\d{2}\D*){2,3}")

CITIES = [
    "Bangalore", "Bengaluru", "Mumbai", "Pune", "Hyderabad", "Chennai", "New Delhi", "Delhi", "Gurgaon",
    "Gurugram", "Noida", "Greater Noida", "Kolkata", "Ahmedabad", "Jaipur", "Kochi", "Cochin",
    "Thiruvananthapuram", "Trivandrum", "Coimbatore", "Chandigarh", "Indore", "Bhopal", "Lucknow", "Nagpur",
    "Surat", "Vadodara", "Visakhapatnam", "Vizag", "Mysore", "Mysuru", "Mangalore", "Mangaluru", "Bhubaneswar",
    "Patna", "Ranchi", "Nashik", "Thane", "Navi Mumbai", "Faridabad", "Ghaziabad", "Kanpur", "Madurai",
    "Hubli", "Belgaum", "Dehradun", "Guwahati", "Raipur", "Goa", "Panaji", "Vijayawada", "Tirupati",
    "Dubai", "Abu Dhabi", "Doha", "Singapore", "London", "New York", "San Francisco", "Toronto", "Sydney",
]
_CITY_RE = re.compile(
    r"(?<![A-Za-z])(" + "|".join(sorted((re.escape(c) for c in CITIES), key=len, reverse=True)) + r")(?![A-Za-z])",
    re.I,
)
_STATE_AFTER = re.compile(r"^\s*,\s*([A-Z][a-z]+(?: [A-Z][a-z]+)?)")
_PLACE_WORDS = {c.lower() for city in CITIES for c in city.split()} | {
    "karnataka", "maharashtra", "telangana", "tamil", "nadu", "delhi", "haryana", "gujarat", "kerala",
    "uttar", "pradesh", "india", "west", "bengal", "rajasthan", "odisha", "punjab", "madhya", "bihar",
}


def find_email(text: str) -> str:
    m = _EMAIL.search(text)
    return m.group(0).lower().rstrip(".") if m else ""


def find_phone(text: str) -> str:
    for m in _PHONE.finditer(text):
        raw = m.group(1)
        digits = re.sub(r"\D", "", raw)
        if 10 <= len(digits) <= 13 and not _YEAR_ONLY_RUN.fullmatch(raw.strip()):
            return re.sub(r"\s+", " ", raw).strip()
    return ""


def find_location(text: str) -> str:
    m = _CITY_RE.search(text)
    if not m:
        return ""
    city = " ".join(w.capitalize() for w in m.group(1).split())
    state = _STATE_AFTER.match(text[m.end():m.end() + 40])
    return f"{city}, {state.group(1)}" if state else city


# ----------------------------------------------------------------------------
# Skills vocabulary
# ----------------------------------------------------------------------------
# canonical name -> extra aliases (all lower case). Aliases of 1-2 letters and the names in
# _STRICT are only recognised when they appear as a standalone item in a Skills section.
_SKILL_DEFS: dict[str, list[str]] = {
    # languages
    "Python": [], "Java": [], "JavaScript": ["js", "es6", "ecmascript"], "TypeScript": ["ts"],
    "C++": [], "C#": [], "C": [], "Go": ["golang"], "Rust": [], "Kotlin": [], "Swift": [], "Scala": [],
    "PHP": [], "Ruby": [], "R": [], "SQL": [], "PL/SQL": ["plsql"], "Bash": ["shell scripting", "shell"],
    "MATLAB": [], "Perl": [], "Dart": [],
    # web
    "React": ["react.js", "reactjs", "react js"], "Angular": ["angularjs", "angular.js"],
    "Vue": ["vue.js", "vuejs"], "Node.js": ["nodejs", "node js", "node"], "Express": ["express.js", "expressjs"],
    "Next.js": ["nextjs"], "Django": [], "Flask": [], "FastAPI": [], "Spring Boot": ["springboot", "spring"],
    ".NET": ["dotnet", ".net core", "asp.net", "asp.net core"], "HTML/CSS": ["html", "css", "html5", "css3"],
    "Redux": [], "jQuery": [], "Tailwind": ["tailwind css"], "Bootstrap": [], "GraphQL": [],
    "REST APIs": ["rest api", "restful", "rest", "restful apis", "rest apis"], "Microservices": ["microservice"],
    # data / ML
    "Machine Learning": ["ml"], "Deep Learning": [], "NLP": ["natural language processing"],
    "Computer Vision": [], "TensorFlow": [], "PyTorch": [], "Keras": [], "Scikit-learn": ["sklearn", "scikit learn"],
    "Pandas": [], "NumPy": [], "Spark": ["pyspark", "apache spark"], "Hadoop": [], "Kafka": ["apache kafka"],
    "Airflow": ["apache airflow"], "dbt": [], "ETL": [], "Data Warehousing": ["data warehouse"],
    "Power BI": ["powerbi"], "Tableau": [], "Excel": ["ms excel", "microsoft excel", "advanced excel"],
    "Statistics": [], "A/B Testing": ["ab testing", "a/b tests"], "MLOps": [], "Kubeflow": [],
    "Feature Stores": ["feature store"], "LLM": ["llms", "large language models"], "Generative AI": ["genai", "gen ai"],
    "Data Analysis": ["data analytics"], "Data Engineering": [],
    # cloud / devops
    "AWS": ["amazon web services"], "Azure": ["microsoft azure"], "GCP": ["google cloud", "google cloud platform"],
    "Docker": [], "Kubernetes": ["k8s"], "Terraform": [], "Ansible": [], "Jenkins": [], "CI/CD": ["cicd", "ci cd"],
    "GitHub Actions": [], "GitLab CI": ["gitlab ci/cd"], "Prometheus": [], "Grafana": [], "Linux": [],
    "Helm": [], "CloudFormation": [], "AWS SageMaker": ["sagemaker"], "Serverless": [], "Nginx": [],
    "DevOps": [], "SRE": [],
    # databases
    "PostgreSQL": ["postgres", "postgresql"], "MySQL": [], "MongoDB": ["mongo"], "Redis": [],
    "Elasticsearch": ["elastic search"], "Oracle": [], "SQL Server": ["mssql", "ms sql"], "DynamoDB": [],
    "Cassandra": [], "Snowflake": [], "BigQuery": [], "SQLite": [], "NoSQL": [],
    "Oracle DB": ["oracle db", "oracle database"],
    # QA
    "Selenium": [], "Cypress": [], "Appium": [], "TestNG": [], "JUnit": [], "Pytest": [], "Jest": [],
    "API Testing": [], "Performance Testing": [], "JMeter": [], "Postman": [], "Test Automation": ["automation testing"],
    # product / design
    "Figma": [], "Adobe XD": [], "Sketch": [], "User Research": [], "Prototyping": [], "Design Systems": [],
    "Accessibility": [], "Product Strategy": [], "Roadmapping": ["product roadmap"], "Agile": [], "Scrum": [],
    "Jira": [], "User Stories": [], "Stakeholder Management": [], "Wireframing": [],
    # engineering general
    "Git": [], "GitHub": [], "RabbitMQ": [], "System Design": [], "Salesforce": [], "SAP": [],
    # business
    "Recruitment": ["talent acquisition"], "Payroll": [], "Tally": [], "GST": [], "SEO": [],
    "Digital Marketing": [], "Content Writing": [], "Customer Support": [], "Project Management": [],
    "Business Analysis": [],
    # mobile / java ecosystem / extra engineering
    "Android": ["android sdk"], "iOS": ["ios development"], "Flutter": [], "React Native": [], "Firebase": [],
    "Hibernate": [], "Maven": [], "Gradle": [], "Mockito": [], "Webpack": [], "NestJS": [], "WebSockets": [],
    "gRPC": [], "OAuth": ["oauth2"], "JWT": [], "Material UI": ["mui"], "Storybook": [], "Redux Toolkit": ["rtk"],
    "Sass": [],
    # data / ML extras
    "Databricks": [], "Hive": [], "Redshift": [], "Looker": [], "Data Modeling": ["data modelling"],
    "Data Visualization": ["data visualisation"], "Matplotlib": [], "XGBoost": [], "Time Series": ["time series analysis"],
    "MLflow": [], "Hugging Face": ["huggingface"], "LangChain": [], "OpenCV": [],
    "Recommendation Systems": ["recommender systems"], "Feature Engineering": [],
    # devops / QA extras
    "Azure DevOps": [], "ArgoCD": ["argo cd"], "ELK Stack": ["elk"], "Datadog": [], "Splunk": [], "Networking": [],
    "Playwright": [], "Robot Framework": [], "Cucumber": [], "BDD": [], "Manual Testing": [], "Load Testing": [],
    "REST Assured": ["restassured"],
    # product / design extras
    "Product Management": [], "OKRs": ["okr"], "Market Research": [], "Competitive Analysis": [],
    "Go-to-Market": ["gtm", "go to market"], "Product Analytics": [], "Mixpanel": [], "Amplitude": [],
    "Photoshop": ["adobe photoshop"], "Illustrator": ["adobe illustrator"], "InVision": [], "Usability Testing": [],
    "Design Thinking": [], "Information Architecture": [], "Visual Design": [], "Interaction Design": [], "Zeplin": [],
    "Kanban": [], "Confluence": [], "PMP": [], "MS Project": ["microsoft project"], "Risk Management": [],
    # HR
    "Onboarding": [], "Employee Engagement": [], "HRIS": ["hr information system"], "Performance Management": [],
    "Compensation and Benefits": ["compensation & benefits", "c&b"], "Labour Laws": ["labor laws", "labour law", "employment law"],
    "Sourcing": ["candidate sourcing"], "Campus Hiring": ["campus recruitment"], "Workday": [], "Naukri": [],
    "LinkedIn Recruiter": [], "Employee Relations": [], "HR Policies": [], "Statutory Compliance": [],
    "ATS": ["applicant tracking system"], "Interview Scheduling": [],
    # marketing
    "SEM": [], "Google Ads": ["adwords"], "Social Media Marketing": ["social media"], "Content Marketing": [],
    "Email Marketing": [], "Google Analytics": ["ga4"], "Copywriting": [], "Brand Management": [],
    "Marketing Automation": [], "HubSpot": [], "Meta Ads": ["facebook ads"], "Performance Marketing": [],
    "Influencer Marketing": [], "Lead Generation": ["lead gen"], "Campaign Management": [], "Canva": [], "WordPress": [],
    # finance / accounting
    "Accounts Payable": [], "Accounts Receivable": [], "Bank Reconciliation": [], "Financial Reporting": [],
    "Budgeting": ["budget planning"], "Forecasting": [], "Tally": ["tally erp", "tally prime"],
    "GST": ["gst filing", "gst returns"], "TDS": [], "Taxation": ["income tax"],
    "Auditing": ["internal audit", "statutory audit"], "IFRS": [], "Ind AS": [], "Financial Modeling": ["financial modelling"],
    "SAP FICO": ["sap fi/co", "sap fi"], "QuickBooks": [], "General Ledger": [], "MIS Reporting": [],
    "Month-end Close": ["month end closing", "month-end closing"], "Cost Accounting": [], "Financial Analysis": [],
    "Zoho Books": [],
    # sales
    "Business Development": [], "B2B Sales": ["enterprise sales"], "CRM": ["crm software"],
    "Account Management": ["key account management"], "Negotiation": [], "Cold Calling": [], "Sales Strategy": [],
    "Pipeline Management": ["sales pipeline"], "Client Relationship Management": ["client relationship"],
    "Territory Management": [], "Presentation Skills": [], "Inside Sales": [], "Channel Sales": [],
    "SaaS Sales": [], "Proposal Writing": [], "Zoho CRM": [],
    # support / operations
    "Zendesk": [], "Freshdesk": [], "Ticketing": ["ticketing systems"], "SLA Management": ["sla"],
    "Escalation Management": [], "Customer Success": [], "CSAT": [], "Process Improvement": [], "Six Sigma": [],
    "Supply Chain": ["supply chain management", "scm"], "Logistics": [], "Inventory Management": [],
    "Vendor Management": [], "Operations Management": [], "Team Management": ["team handling"],
    "Call Center": ["call centre", "bpo"], "Voice Process": [], "Email Support": [], "Live Chat": ["chat support"],
    "Data Entry": [], "MS Office": ["microsoft office"], "Leadership": [],
}
_STRICT = {
    "excel", "go", "r", "c", "express", "sketch", "swift", "node", "shell", "rest", "spring", "ml", "js", "ts",
    "oracle", "salesforce", "sap",  # also employer names, so only trusted inside a Skills section
}

_ALIAS_TO_CANON: dict[str, str] = {}
for _canon, _aliases in _SKILL_DEFS.items():
    for _a in [_canon.lower(), *_aliases]:
        _ALIAS_TO_CANON[_a] = _canon
_FREE_ALIASES = sorted(
    (a for a in _ALIAS_TO_CANON if (len(a) > 2 or re.search(r"[+#.]", a)) and a not in _STRICT),
    key=len, reverse=True,
)


def _alias_pattern(alias: str) -> str:
    return r"\s+".join(re.escape(part) for part in alias.split(" "))


_SKILL_RE = re.compile(
    r"(?<![A-Za-z0-9+#])(?:" + "|".join(_alias_pattern(a) for a in _FREE_ALIASES) + r")(?![A-Za-z0-9+#])", re.I
)
_SKILL_STOP = {
    "and", "etc", "others", "other", "tools", "technologies", "languages", "frameworks", "databases", "skills",
    "proficient", "basic", "advanced", "intermediate", "beginner", "expert", "good", "strong", "knowledge",
    "familiar", "working", "experience", "programming", "platforms", "cloud", "concepts", "methodologies",
}


def canonical_skill(token: str) -> str | None:
    return _ALIAS_TO_CANON.get(re.sub(r"\s+", " ", token.strip().lower()))


# Capitalised words that are only trusted as skills inside a job description (in resumes they are often employers)
_LOOSE_NAMES = ["Excel", "Swift", "Sketch", "Express", "Oracle", "Salesforce", "SAP"]
_LOOSE_RE = re.compile(r"(?<![A-Za-z0-9+#])(" + "|".join(_LOOSE_NAMES) + r")(?![A-Za-z0-9+#])")


def scan_vocab(text: str, loose: bool = False) -> list[str]:
    """Skills from the vocabulary mentioned anywhere in `text`, in order of appearance.

    loose=True (used for job descriptions) also accepts capitalised ambiguous names such as 'Excel' or 'Swift'.
    """
    seen: dict[str, str] = {}
    for m in _SKILL_RE.finditer(text):
        canon = _ALIAS_TO_CANON.get(re.sub(r"\s+", " ", m.group(0).lower()))
        if canon:
            seen.setdefault(canon.lower(), canon)
    if loose:
        for m in _LOOSE_RE.finditer(text):
            seen.setdefault(m.group(1).lower(), m.group(1))
    return list(seen.values())


def aliases_for(canonical: str) -> list[str]:
    """Aliases of a vocabulary skill that are safe to search for in free text."""
    return [a for a, c in _ALIAS_TO_CANON.items() if c == canonical and a in _FREE_ALIASES]


# Inside a Skills section every known name is trusted, even ambiguous ones like 'Excel' or 'Swift' (but not 1-2 letter ones)
_SECTION_RE = re.compile(
    r"(?<![A-Za-z0-9+#])(?:"
    + "|".join(_alias_pattern(a) for a in sorted((a for a in _ALIAS_TO_CANON if len(a) > 2), key=len, reverse=True))
    + r")(?![A-Za-z0-9+#])", re.I,
)


def _skills_from_section(lines: list[str]) -> list[str]:
    tokens: list[str] = []
    for line in lines:
        line = re.sub(r"\([^)]*\)", "", line)
        line = re.sub(r"^[A-Za-z &/]{2,30}:\s*", "", line)  # "Languages: Python, Java"
        found = 0
        for tok in re.split(r"[,;|•·]|\s{2,}|\t|\s[-–]\s", line):
            tok = tok.strip(" -–—*•.:[]")
            if not tok or len(tok) > 30 or len(tok.split()) > 4 or not re.search(r"[A-Za-z]", tok):
                continue
            if tok.lower() in _SKILL_STOP:
                continue
            tokens.append(tok)
            found += 1
        if not found and len(line.split()) > 4:  # skills run together with no separators (spacing lost in a PDF)
            for m in _SECTION_RE.finditer(line):
                canon = _ALIAS_TO_CANON.get(re.sub(r"\s+", " ", m.group(0).lower()))
                if canon:
                    tokens.append(canon)
    return tokens


def extract_skills(text: str, skills_lines: list[str]) -> list[str]:
    found: dict[str, str] = {}
    for tok in _skills_from_section(skills_lines):
        found.setdefault((canonical_skill(tok) or tok).lower(), canonical_skill(tok) or tok)
    for canon in scan_vocab(text):
        found.setdefault(canon.lower(), canon)
    return list(found.values())[:40]


# ----------------------------------------------------------------------------
# Experience
# ----------------------------------------------------------------------------
_MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
_MON = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*"
_DATE = rf"(?:{_MON}\.?,?\s+|\d{{1,2}}\s*[/.\-]\s*)?(?:19|20)\d{{2}}"
_PRESENT = r"present|current|till\s+date|till\s+now|to\s+date|now|ongoing|today"
_RANGE_RE = re.compile(rf"({_DATE})\s*(?:-|\bto\b|\buntil\b|\btill\b|\bthrough\b)\s*({_DATE}|\b(?:{_PRESENT})\b)", re.I)
_EXP_CLAIM = [
    re.compile(r"(\d{1,2}(?:\.\d{1,2})?)\s*\+?\s*(?:years?|yrs?)\b(?:\s+of)?\s+(?:[\w/&\-]+\s+){0,4}?experience", re.I),
    re.compile(r"experience\s*(?:of|:|-)?\s*(?:over|around|about|more than)?\s*(\d{1,2}(?:\.\d{1,2})?)\s*\+?\s*(?:years?|yrs?)\b", re.I),
]
_EDU_WORDS = re.compile(
    r"\b(b\.?\s?tech|m\.?\s?tech|b\.?\s?e\b|m\.?\s?e\b|b\.?\s?sc|m\.?\s?sc|b\.?\s?com|m\.?\s?com|bca|mca|mba|bachelor|master|"
    r"diploma|university|college|institute|school|ssc|hsc|cbse|icse|10th|12th|ph\.?d)\b", re.I,
)


def _norm_dashes(s: str) -> str:
    return re.sub(r"[‐-―−]", "-", s)


def _ym(text: str, default_month: int, today: date) -> tuple[int, int]:
    s = text.lower()
    year = int(re.search(r"(?:19|20)\d{2}", s).group(0))
    month = default_month
    mm = re.match(r"\s*([a-z]{3})", s)
    if mm and mm.group(1) in _MONTHS:
        month = _MONTHS[mm.group(1)]
    else:
        nm = re.match(r"\s*(\d{1,2})\s*[/.\-]", s)
        if nm and 1 <= int(nm.group(1)) <= 12:
            month = int(nm.group(1))
        elif year == today.year:
            month = min(default_month, today.month)
    return year, month


def years_from_dates(lines: list[str], today: date | None = None) -> float:
    """Total months covered by the date ranges found in `lines` (overlaps counted once)."""
    today = today or date.today()
    now_idx = today.year * 12 + today.month - 1
    spans: list[tuple[int, int]] = []
    for line in lines:
        for m in _RANGE_RE.finditer(_norm_dashes(line)):
            sy, sm = _ym(m.group(1), 6, today)
            end_txt = m.group(2)
            if re.fullmatch(_PRESENT, end_txt.strip(), re.I):
                ey, em = today.year, today.month
            else:
                ey, em = _ym(end_txt, 6, today)
            start, end = sy * 12 + sm - 1, min(ey * 12 + em - 1, now_idx)
            if sy < 1975 or end < start or end - start > 45 * 12:
                continue
            spans.append((start, end))
    if not spans:
        return 0.0
    spans.sort()
    total, (cur_s, cur_e) = 0, spans[0]
    for s, e in spans[1:]:
        if s <= cur_e:
            cur_e = max(cur_e, e)
        else:
            total += cur_e - cur_s
            cur_s, cur_e = s, e
    total += cur_e - cur_s
    return round(total / 12, 1)


def explicit_years(text: str) -> float:
    best = 0.0
    for rx in _EXP_CLAIM:
        for m in rx.finditer(text):
            v = float(m.group(1))
            if 0 < v <= 45:
                best = max(best, v)
    return best


def compute_experience(sections: dict[str, list[str]], text: str) -> float:
    if sections.get("experience"):
        lines = sections["experience"]
    else:  # no experience heading: use everything that is not obviously education
        skip = set(sections.get("education", []))
        lines = [l for l in text.split("\n") if l.strip() and l.strip() not in skip and not _EDU_WORDS.search(l)]
    return round(max(years_from_dates(lines), explicit_years(text)), 1)


# ----------------------------------------------------------------------------
# Current title / company
# ----------------------------------------------------------------------------
TITLE_WORDS = {
    "engineer", "developer", "manager", "analyst", "architect", "designer", "consultant", "lead", "director",
    "scientist", "administrator", "specialist", "officer", "executive", "intern", "associate", "programmer",
    "tester", "head", "president", "vp", "coordinator", "technician", "supervisor", "accountant", "recruiter",
    "writer", "strategist", "owner", "sde", "devops", "sre", "qa", "trainee", "assistant", "founder", "partner",
    "professor", "teacher", "representative", "agent", "advisor", "controller", "editor", "marketer",
}
_JOB_SEP = re.compile(r"\s+(?:at|@)\s+|\s*\|\s*|\s+-\s+|\s*,\s*")


def _title_like(s: str) -> bool:
    return any(w in TITLE_WORDS for w in re.findall(r"[a-z]+", s.lower()))


def _clean_role(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip(" |,-–—:•*()")).strip()


def _split_role(line: str) -> tuple[str, str]:
    """'Senior Engineer at Acme' -> ('Senior Engineer', 'Acme'); a plain title -> (title, '')."""
    parts = [p for p in (_clean_role(x) for x in _JOB_SEP.split(line)) if p]
    if len(parts) >= 2:
        t = next((p for p in parts if _title_like(p)), parts[0])
        return t, next((p for p in parts if p != t), "")
    return (parts[0] if parts else ""), ""


def _strip_city(company: str) -> str:
    """'Infosys, Indore' -> 'Infosys' (a trailing known city is a location, not part of the company name)."""
    head, sep, tail = company.rpartition(",")
    if sep and _CITY_RE.fullmatch(tail.strip()):
        return head.strip()
    return company


def current_role(sections: dict[str, list[str]], header: list[str], text: str = "") -> tuple[str, str]:
    title = company = ""
    lines = sections.get("experience") or [
        l.strip() for l in text.split("\n") if _clean_role(l) and not _EDU_WORDS.search(l)
    ]
    for i, raw in enumerate(lines):
        m = _RANGE_RE.search(_norm_dashes(raw))
        if not m:
            continue
        rest = _clean_role(_RANGE_RE.sub(" ", _norm_dashes(raw)))
        prev = [_clean_role(l) for l in lines[max(0, i - 2):i]]
        if rest:
            parts = [p for p in (_clean_role(x) for x in _JOB_SEP.split(rest)) if p]
            if len(parts) >= 2:
                t = next((p for p in parts if _title_like(p)), None)
                if t:
                    title = t
                    company = next((p for p in parts if p != t), "")
                elif prev and _title_like(prev[-1]):
                    title, company = prev[-1], parts[0]
                else:
                    title, company = parts[0], parts[1]
            elif _title_like(parts[0]):
                title, company = parts[0], (prev[-1] if prev and len(prev[-1]) <= 60 else "")
            else:
                company = parts[0]
                title = prev[-1] if prev else ""
        elif prev:
            if _title_like(prev[-1]):
                title, company = _split_role(prev[-1])
                if not company and len(prev) > 1 and len(prev[-2]) <= 60 and not prev[-2].endswith("."):
                    company = prev[-2]
            elif len(prev) > 1 and _title_like(prev[-2]):
                title, company = prev[-2], prev[-1]
            else:
                title = prev[-1]
        break
    if not title:  # fall back to the line under the name, which is often the headline title
        for line in header[1:6]:
            if _title_like(line) and len(line.split()) <= 8 and "@" not in line and not re.search(r"\d{5,}", line):
                title, company = _split_role(line)
                break
    company = _strip_city(company)
    if len(title.split()) > 8:
        title = ""
    if len(company.split()) > 8:
        company = ""
    return title[:80], company[:80]


# ----------------------------------------------------------------------------
# Name
# ----------------------------------------------------------------------------
_NAME_BAN = {
    "resume", "curriculum", "vitae", "cv", "profile", "summary", "contact", "email", "phone", "mobile",
    "address", "objective", "page", "linkedin", "github", "portfolio", "declaration",
}


def guess_name(header: list[str], email: str, filename: str) -> tuple[str, bool]:
    """Return (name, confident)."""
    for line in header[:8]:
        l = re.sub(r"^(?:name|full name)\s*[:\-]\s*", "", line, flags=re.I).strip()
        if not l or "@" in l or re.search(r"\d", l):
            continue
        words = l.replace(",", " ").split()
        if not 2 <= len(words) <= 4:
            continue
        low = [w.lower().strip(".") for w in words]
        if any(w in _NAME_BAN or w in TITLE_WORDS or w in _PLACE_WORDS for w in low):
            continue
        if not all(re.fullmatch(r"[A-Za-z][A-Za-z.'\-]*", w) for w in words):
            continue
        l = re.sub(r"\s+", " ", l)
        return (l.title() if l.isupper() else l), True
    if email:
        toks = [t for t in re.split(r"[._\-\d]+", email.split("@")[0]) if len(t) >= 2]
        if toks:
            return " ".join(t.capitalize() for t in toks), False
    stem = re.sub(r"^[A-Za-z]?\d+[_\-\s]+", "", Path(filename).stem)
    stem = re.sub(r"(?i)\b(resume|cv|curriculum vitae)\b", "", re.sub(r"[_\-.]+", " ", stem)).strip()
    stem = re.sub(r"\s+", " ", stem).strip()
    return (stem.title() if stem else Path(filename).stem), False


# ----------------------------------------------------------------------------
# Top level
# ----------------------------------------------------------------------------
def parse_text(text: str, filename: str = "") -> dict:
    notes: list[str] = []
    sections = split_sections(text)
    header = sections["header"]
    if len(header) < 2 or len(sections) == 1:  # no usable headings: treat the top of the file as the header
        header = [l.strip() for l in text.split("\n") if l.strip()][:12]

    head_text = "\n".join(header[:14])
    email = find_email(head_text) or find_email(text)
    phone = find_phone(head_text) or find_phone(text)
    name, confident = guess_name(header, email, filename)
    if not confident:
        notes.append("Name guessed from email/file name - please check")

    body_wo_edu = "\n".join(l for k, ls in sections.items() if k != "education" for l in ls)
    location = find_location(head_text) or find_location(body_wo_edu)
    title, company = current_role(sections, header, text)
    experience = compute_experience(sections, text)
    skills = extract_skills(text, sections.get("skills", []))

    summary = " ".join(sections.get("summary", []))[:600]
    if not summary:
        bits = [b for b in [title, f"at {company}" if company else ""] if b]
        summary = " ".join(bits)
        if experience:
            summary += f" with about {experience:g} years of experience" if summary else f"{experience:g} years of experience"
        if skills:
            summary += f". Key skills: {', '.join(skills[:8])}."
        summary = summary.strip()

    education = " · ".join(sections.get("education", [])[:2])[:200]

    if not email:
        notes.append("No email found")
    if not skills:
        notes.append("No skills detected")
    if not experience:
        notes.append("Experience could not be determined (fresher, or dates not found)")
    if not title:
        notes.append("Current title not detected")

    return {
        "name": name, "email": email, "phone": phone, "location": location, "title": title,
        "company": company, "experience": experience, "education": education,
        "skills": ", ".join(skills), "summary": summary, "resume_text": text, "notes": notes,
    }


def parse_resume(data: bytes, filename: str) -> dict:
    """Extract text from a PDF/DOCX/TXT and parse it. Never raises for bad files."""
    try:
        text = extract_text(data, filename)
    except Exception as exc:  # corrupt, password protected, wrong type...
        text = ""
        err = f"Could not read file ({type(exc).__name__}: {exc})"
    else:
        err = ""
    if len(text.strip()) < 40:
        name, _ = guess_name([], "", filename)
        reason = err or "No text found - the file may be a scanned image (needs OCR) or empty"
        return {
            "name": name, "email": "", "phone": "", "location": "", "title": "", "company": "",
            "experience": 0.0, "education": "", "skills": "", "summary": "", "resume_text": text,
            "notes": [reason],
        }
    return parse_text(text, filename)
