"""Job-description analysis and candidate ranking. Transparent, runs offline, no AI service needed."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

import pandas as pd

import resume_parser as rp

MODES: dict[str, dict] = {
    "Balanced": {
        "weights": {"skills": 0.45, "text": 0.20, "exp": 0.20, "title": 0.15},
        "help": "Skills, keyword relevance, experience fit and job-title similarity all count.",
    },
    "Skills match": {
        "weights": {"skills": 0.70, "text": 0.20, "exp": 0.00, "title": 0.10},
        "help": "Ranks by how many of the required skills and must-have keywords the person has.",
    },
    "Experience weighted": {
        "weights": {"skills": 0.30, "text": 0.15, "exp": 0.40, "title": 0.15},
        "help": "Rewards candidates whose years of experience fit the range in the job description.",
    },
    "Keyword relevance": {
        "weights": {"skills": 0.15, "text": 0.75, "exp": 0.00, "title": 0.10},
        "help": "Full-text match of the job description against the whole resume. Best for non-technical roles.",
    },
    "Role fit": {
        "weights": {"skills": 0.30, "text": 0.10, "exp": 0.20, "title": 0.40},
        "help": "Prefers people already working in a similar role / job title.",
    },
}

_STOP = set(
    "a an and are as at be by for from has have in into is it its of on or our that the their this to we will with you your "
    "who they them these those such can may must should would about across over under per via etc using use used "
    "experience experienced years year yrs yr strong good excellent knowledge ability able skills skill required requirements "
    "requirement preferred plus nice job role position candidate candidates work working team teams looking hiring hire "
    "responsibilities responsibility description location minimum maximum least more than other including include "
    "understanding proven demonstrated solid hands-on handson relevant related well also not any all one two three four five "
    "key title senior junior lead based new join company business".split()
)
_GENERIC_TITLE = {"senior", "sr", "junior", "jr", "lead", "principal", "staff", "associate", "the", "and", "of", "i", "ii", "iii", "iv"}
_TITLE_SYNONYMS = [
    ("back-end", "backend"), ("back end", "backend"), ("front-end", "frontend"), ("front end", "frontend"),
    ("full-stack", "fullstack"), ("full stack", "fullstack"), ("developer", "engineer"), ("programmer", "engineer"),
    ("sde", "engineer"), ("swe", "engineer"), ("ux/ui", "designer"), ("ui/ux", "designer"), ("sre", "devops"),
]
_RANGE = re.compile(r"(\d{1,2})\s*(?:-|to)\s*(\d{1,2})\s*\+?\s*(?:years?|yrs?)", re.I)
_MIN_PLUS = re.compile(r"(\d{1,2})\s*\+\s*(?:years?|yrs?)", re.I)
_MIN_WORD = re.compile(r"(?:minimum|min\.?|at least|over)\s*(?:of\s*)?(\d{1,2})\s*(?:years?|yrs?)", re.I)
_TITLE_LINE = re.compile(r"^\s*(?:job\s*title|title|position|role)\s*[:\-]\s*(.+)$", re.I | re.M)


@dataclass
class JD:
    skills: list[str] = field(default_factory=list)        # from the description (weight 1)
    must_have: list[str] = field(default_factory=list)     # typed by the user (weight 2)
    tokens: list[str] = field(default_factory=list)
    exp_min: float | None = None
    exp_max: float | None = None
    title_tokens: set[str] = field(default_factory=set)

    @property
    def terms(self) -> dict[str, int]:
        t = {s: 1 for s in self.skills}
        for m in self.must_have:
            t[m] = 2
        return t


def tokenize(text: str) -> list[str]:
    return [t.rstrip(".") for t in re.findall(r"[a-z][a-z0-9+#.]{1,}", text.lower())]


def _title_tokens(title: str) -> set[str]:
    t = title.lower()
    for a, b in _TITLE_SYNONYMS:
        t = t.replace(a, b)
    return {w for w in re.findall(r"[a-z]+", t) if w not in _GENERIC_TITLE and len(w) > 1}


def _exp_range(text: str) -> tuple[float | None, float | None]:
    t = re.sub(r"[‐-―−]", "-", text)
    if m := _RANGE.search(t):
        return float(m.group(1)), float(m.group(2))
    if m := _MIN_PLUS.search(t) or _MIN_WORD.search(t):
        return float(m.group(1)), None
    return None, None


def extract_title(jd_text: str) -> str:
    """The text after a 'Job Title:' / 'Position:' / 'Role:' line, or ''."""
    m = _TITLE_LINE.search(jd_text)
    return re.sub(r"\s+", " ", m.group(1)).strip()[:80] if m else ""


def analyze(jd_text: str, must_have_text: str = "", job_title: str = "") -> JD:
    jd = JD()
    jd.skills = rp.scan_vocab(jd_text, loose=True)
    for raw in re.split(r"[,;\n]", must_have_text):
        raw = raw.strip()
        if raw:
            canon = rp.canonical_skill(raw) or raw
            if canon.lower() not in {m.lower() for m in jd.must_have}:
                jd.must_have.append(canon)
    must_lower = {m.lower() for m in jd.must_have}
    jd.skills = [s for s in jd.skills if s.lower() not in must_lower]
    jd.tokens = sorted({t for t in tokenize(jd_text) if len(t) > 2 and t not in _STOP and not t.isdigit()})
    jd.exp_min, jd.exp_max = _exp_range(jd_text)
    job_title = job_title or extract_title(jd_text)
    jd.title_tokens = _title_tokens(job_title)
    return jd


def _term_regex(term: str) -> re.Pattern | None:
    """Regex for finding a skill / keyword in free resume text (None if it is only safe as a skills-list item)."""
    canon = rp.canonical_skill(term)
    forms = rp.aliases_for(canon) if canon else [term.lower()]
    if canon and not forms:
        return None
    pats = [r"\s+".join(re.escape(p) for p in f.split(" ")) for f in forms]
    return re.compile(r"(?<![a-z0-9+#])(?:" + "|".join(pats) + r")(?![a-z0-9+#])")


def _exp_fit(exp: float, lo: float | None, hi: float | None) -> float:
    if lo is None and hi is None:
        return min(100.0, 55 + exp * 8)
    if hi is None:
        return 100.0 if exp >= lo else max(0.0, 100 - 25 * (lo - exp))
    if lo <= exp <= hi + 1:
        return 100.0
    if exp < lo:
        return max(0.0, 100 - 25 * (lo - exp))
    return max(55.0, 100 - 8 * (exp - hi))


def rank(pool: pd.DataFrame, jd: JD, mode: str = "Balanced") -> list[dict]:
    """Score every candidate in `pool` (needs columns id, title, experience, skills, resume_text)."""
    weights = dict(MODES[mode]["weights"])
    terms = jd.terms
    if not jd.title_tokens:  # no job title to compare with: give that weight to skills
        weights["skills"] += weights.pop("title", 0)
        weights["title"] = 0.0
    if not terms:  # no recognisable skills: lean on full-text relevance instead
        weights["text"] += weights["skills"]
        weights["skills"] = 0.0

    rows = pool.to_dict("records")
    texts = [str(r.get("resume_text", "")).lower() for r in rows]
    cand_tokens = [set(tokenize(t)) for t in texts]

    # inverse document frequency of each job-description token across the candidate pool
    n = max(len(rows), 1)
    jd_tokens = set(jd.tokens)
    df = {t: sum(1 for ct in cand_tokens if t in ct) for t in jd_tokens}
    idf = {t: math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5)) for t in jd_tokens}
    idf_total = sum(idf.values()) or 1.0
    raw_text = [100 * sum(idf[t] for t in jd_tokens if t in ct) / idf_total for ct in cand_tokens]
    max_text = max(raw_text, default=0) or 1.0

    term_res = {t: _term_regex(t) for t in terms}
    total_w = sum(terms.values()) or 1

    out = []
    for row, text, tscore in zip(rows, texts, raw_text):
        cand_skills = {s.strip().lower() for s in str(row.get("skills", "")).split(",") if s.strip()}
        matched, missing, got_w = [], [], 0
        for term, w in terms.items():
            rx = term_res[term]
            if term.lower() in cand_skills or (rx is not None and rx.search(text)):
                matched.append(term)
                got_w += w
            else:
                missing.append(term)
        skill_s = 100 * got_w / total_w if terms else 0.0
        text_s = 100 * tscore / max_text
        exp_s = _exp_fit(float(row.get("experience") or 0), jd.exp_min, jd.exp_max)
        ct = _title_tokens(str(row.get("title", "")))
        title_s = 100 * len(ct & jd.title_tokens) / len(jd.title_tokens) if jd.title_tokens else 0.0

        comps = {"skills": skill_s, "text": text_s, "exp": exp_s, "title": title_s}
        score = round(sum(weights[k] * comps[k] for k in comps), 1)

        reasons = []
        if terms:
            reasons.append(f"Has {len(matched)} of {len(terms)} requested skills / keywords")
        if jd.exp_min is not None:
            rng = f"{jd.exp_min:g}-{jd.exp_max:g}" if jd.exp_max else f"{jd.exp_min:g}+"
            reasons.append(f"{row.get('experience', 0):g} yrs vs {rng} yrs asked")
        if title_s >= 50:
            reasons.append("Current job title is similar to the position")
        out.append({
            "id": row["id"], "score": min(score, 100.0), "skill_score": round(skill_s), "text_score": round(text_s),
            "exp_score": round(exp_s), "title_score": round(title_s),
            "matched": matched, "missing": missing, "reasons": reasons,
            "has_all_must": all(m in matched for m in jd.must_have),
        })
    out.sort(key=lambda r: (-r["score"], r["id"]))
    return out
