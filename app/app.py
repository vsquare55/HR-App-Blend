"""HR resume matcher - local version.

Run from the project folder:  py -m streamlit run app\\app.py   (or double-click Start_HR_App.bat)
"""

from __future__ import annotations

import getpass
import re
from datetime import datetime

import pandas as pd
import streamlit as st

import config
import db
import exports
import ingest
import matcher
import preview
import resume_parser as rp

st.set_page_config(page_title="HR resume matcher", page_icon=":material/groups:", layout="wide")


@st.cache_resource
def _boot() -> bool:
    db.init_db()
    return True


_boot()
ss = st.session_state

CUSTOM = "__custom__"
CUSTOM_JOB_ID = "JOB-CUSTOM"
SORTS = ["Match score", "Experience: high to low", "Experience: low to high", "Name A-Z"]
STATUSES = ["New", "Viewed", "Shortlisted", "Rejected"]
STATUS_COLOR = {"New": "gray", "Viewed": "blue", "Shortlisted": "green", "Rejected": "red"}
REJECT_REASONS = [
    "Skills mismatch", "Not enough experience", "Overqualified", "Location", "Salary expectation",
    "Notice period", "Better candidate selected", "Other",
]
EMPTY_STATE = {"status": "New", "timestamp": "", "by": "", "notes": "", "viewed_at": ""}

ss.setdefault("reviewer", getpass.getuser().replace(".", " ").title())
ss.setdefault("results", None)
ss.setdefault("ctx", None)
ss.setdefault("selected", set())
ss.setdefault("show_n", 20)
ss.setdefault("jd_text", "")
ss.setdefault("job_pick", CUSTOM)
ss.setdefault("sort_by", SORTS[0])
ss.setdefault("uploader_n", 0)
ss.setdefault("upload_report", None)


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
@st.cache_data(show_spinner=False, max_entries=4)
def load_candidates(version: str, with_text: bool) -> pd.DataFrame:
    return db.load_candidates(with_text)


def fmt_ts(ts: str) -> str:
    try:
        return datetime.strptime(ts, db.TS_FORMAT).strftime("%d %b %Y, %H:%M")
    except (TypeError, ValueError):
        return ts or ""


def city(location: str) -> str:
    return location.split(",")[0].strip() if location else ""


def badge(status: str) -> str:
    return f":{STATUS_COLOR[status]}-badge[{status}]"


def status_line(state: dict, job_title: str) -> str:
    """'Rejected for Senior Engineer on 04 Oct 2026, 21:30 by Vishnu - Skills mismatch'"""
    if state["status"] == "New":
        return ""
    text = f":material/schedule: {state['status']} for **{job_title}** on {fmt_ts(state['timestamp'])} by {state['by']}"
    if state["status"] in ("Shortlisted", "Rejected") and state["viewed_at"]:
        text += f" · first viewed {fmt_ts(state['viewed_at'])}"
    if state["notes"]:
        text += f" · _{state['notes']}_"
    return text


def skill_badges(skills: list[str], color: str, limit: int = 10) -> str:
    return " ".join(f":{color}-badge[{s}]" for s in skills[:limit])


def flash(msg: str, icon: str | None = None) -> None:
    """Queue a toast. Callbacks must not draw anything themselves (it breaks when they run in the drawer)."""
    ss.flash = (msg, icon)


def show_flash() -> None:
    if item := ss.pop("flash", None):
        msg, icon = item if isinstance(item, tuple) else (item, None)
        st.toast(msg, icon=icon)


# ----------------------------------------------------------------------------
# Callbacks (run before the page reruns, so the page always shows fresh data)
# ----------------------------------------------------------------------------
def cb_apply_job() -> None:
    if ss.job_pick == CUSTOM:
        ss.jd_text = ""
    elif job := db.get_job(ss.job_pick):
        ss.jd_text = job["description"] or f"Job title: {job['title']}"


def cb_jd_upload() -> None:
    f = ss.get("jd_file")
    if f is None:
        return
    try:
        text = rp.extract_text(f.getvalue(), f.name)
    except Exception as exc:
        ss.search_msg = ("warning", f"Could not read {f.name}: {exc}")
        return
    if len(text.strip()) < 20:
        ss.search_msg = ("warning", f"No text found in {f.name}. If it is a scanned image, paste the text instead.")
        return
    ss.pop("search_msg", None)
    ss.jd_text = text
    flash(f"Loaded the job description from {f.name}")


def cb_load_samples() -> None:
    n = db.load_sample_jobs()
    flash(f"Added {n} sample position(s)." if n else "All sample positions are already there.")


def cb_search() -> None:
    ss.pop("search_msg", None)
    version = db.data_version()
    cands = load_candidates(version, True)
    if cands.empty:
        ss.search_msg = ("warning", "There are no resumes in the database yet. Add some in the 'Add resumes' tab.")
        return
    jd_text, must = ss.jd_text.strip(), ss.get("must_have", "").strip()
    if not jd_text and not must:
        ss.search_msg = ("warning", "Paste a job description or type some must-have skills first.")
        return
    if ss.job_pick == CUSTOM:
        found = matcher.extract_title(jd_text)  # a pasted / uploaded JD usually starts with "Job Title: ..."
        if found:
            job_id = "CUSTOM-" + re.sub(r"[^A-Za-z0-9]+", "-", found).strip("-").upper()[:40]
            job_title, title_hint = found, found
        else:
            job_id, job_title, title_hint = CUSTOM_JOB_ID, "Custom search", ""
    else:
        job = db.get_job(ss.job_pick)
        job_id, job_title = job["id"], job["title"]
        title_hint = job["title"]

    jd = matcher.analyze(jd_text, must, title_hint)
    pool = cands
    lo, hi = ss.exp_range
    pool = pool[(pool["experience"] >= lo) & (pool["experience"] <= hi)]
    if ss.get("loc_filter"):
        pool = pool[pool["location"].map(city).isin(ss.loc_filter)]
    states = db.status_map(job_id)
    if ss.hide_rejected:
        pool = pool[~pool["id"].map(lambda i: states.get(i, EMPTY_STATE)["status"] == "Rejected")]
    if pool.empty:
        ss.search_msg = ("warning", "No candidates left after applying the filters. Widen the filters and try again.")
        return

    ranked = matcher.rank(pool, jd, ss.mode)
    ranked = [r for r in ranked if r["score"] >= ss.min_score]
    if ss.get("strict_must") and jd.must_have:
        ranked = [r for r in ranked if r["has_all_must"]]
    for i, r in enumerate(ranked, 1):
        r["rank"] = i

    ss.results = ranked
    ss.ctx = {
        "job_id": job_id, "job_title": job_title, "mode": ss.mode, "pool": len(pool), "all": len(cands),
        "ran_at": datetime.now().strftime("%d %b %Y, %H:%M"), "terms": list(jd.terms),
    }
    cb_clear_selection()
    ss.show_n = 20
    if not ranked:
        ss.search_msg = ("info", "Nobody matched. Try lowering the minimum score or removing 'must have all'.")


def cb_save_position() -> None:
    title = ss.get("new_position_title", "").strip()
    if not title:
        flash("Give the position a title first.")
        return
    new_id = db.save_job(None, title, "", "", "", ss.jd_text, "Open")
    ss.job_pick = new_id
    flash(f"Saved as {new_id}. Status tracking now belongs to this position.")
    cb_search()


def cb_toggle(cid: str) -> None:
    (ss.selected.add if ss.get(f"sel_{cid}") else ss.selected.discard)(cid)


def cb_clear_selection() -> None:
    for cid in list(ss.selected):
        ss[f"sel_{cid}"] = False
    ss.selected = set()


def cb_select(ids: list[str]) -> None:
    for cid in ids:
        ss.selected.add(cid)
        ss[f"sel_{cid}"] = True


def cb_more() -> None:
    ss.show_n += 20


def cb_set_status(status: str, cid: str, name: str, reason_key: str | None = None) -> None:
    ctx = ss.ctx
    if not ctx:
        return
    notes = ss.get(reason_key, "") if reason_key else ""
    db.add_status(ctx["job_id"], ctx["job_title"], cid, name, status, notes, ss.reviewer)
    label = {"Reset": "status cleared"}.get(status, status.lower())
    flash(f"{name}: {label}")


def cb_bulk_status(status: str, reason_key: str | None = None) -> None:
    ctx = ss.ctx
    if not ctx or not ss.selected:
        return
    notes = ss.get(reason_key, "") if reason_key else "Bulk action"
    names = load_candidates(db.data_version(), False).set_index("id")["name"].to_dict()
    for cid in list(ss.selected):
        db.add_status(ctx["job_id"], ctx["job_title"], cid, names.get(cid, cid), status, notes, ss.reviewer)
    flash(f"{len(ss.selected)} candidate(s) marked {status.lower()}")
    cb_clear_selection()


def cb_open(cid: str, name: str, with_job: bool) -> None:
    ctx = ss.ctx
    if with_job and ctx:
        db.mark_viewed(ctx["job_id"], ctx["job_title"], cid, name, ss.reviewer)
    ss.open_resume = (cid, bool(with_job and ctx))


def cb_export_excel() -> None:
    ok, msg = exports.export_excel()
    flash(msg, ":material/check_circle:" if ok else ":material/error:")


# ----------------------------------------------------------------------------
# Resume side drawer
# ----------------------------------------------------------------------------
@st.dialog("Candidate profile", width="large", position="right", on_dismiss="rerun")
def resume_dialog(cid: str, with_job: bool) -> None:
    show_flash()  # confirmation of the button just pressed in here
    cand = db.get_candidate(cid)
    if not cand:
        st.error("This candidate no longer exists.")
        return
    ctx = ss.ctx if with_job else None
    st.subheader(cand["name"])
    st.caption(
        f"{cand['title'] or 'Title not detected'} · {cand['company'] or 'company not detected'} · "
        f"{cand['location'] or 'location not detected'} · {cand['experience']:g} yrs"
    )
    if ctx:
        state = db.status_map(ctx["job_id"]).get(cid, EMPTY_STATE)
        st.markdown(f"{badge(state['status'])} {status_line(state, ctx['job_title'])}")
        with st.container(horizontal=True):
            st.button("Shortlist", icon=":material/check_circle:", type="primary", key=f"d_sl_{cid}",
                      on_click=cb_set_status, args=("Shortlisted", cid, cand["name"]),
                      disabled=state["status"] == "Shortlisted")
            st.selectbox("Reason", REJECT_REASONS, key=f"d_reason_{cid}", label_visibility="collapsed", width=210)
            st.button("Reject", icon=":material/cancel:", key=f"d_rej_{cid}", on_click=cb_set_status,
                      args=("Rejected", cid, cand["name"], f"d_reason_{cid}"), disabled=state["status"] == "Rejected")
            if state["status"] in ("Shortlisted", "Rejected"):
                st.button("Undo", icon=":material/undo:", key=f"d_undo_{cid}", on_click=cb_set_status,
                          args=("Reset", cid, cand["name"]))

    tab_resume, tab_profile, tab_history = st.tabs(["Resume", "Profile and fit", "History"])
    path = exports.resume_path(cand["resume_file"] or "")
    with tab_resume:
        if cand["resume_file"] and path.exists():
            if path.suffix.lower() == ".txt":
                with st.container(height=620, border=True):
                    st.text(cand["resume_text"] or path.read_text(encoding="utf-8", errors="replace"))
            else:  # PDF as is; Word converted to PDF (cached), or shown as a formatted page
                with st.spinner("Preparing the resume preview (first time only)..."):
                    pdf = preview.pdf_for(path, cand["file_hash"] or cand["id"])
                if pdf:
                    st.pdf(pdf, height=620, alt=f"Resume of {cand['name']}")
                elif page := preview.docx_html(path):
                    with st.container(height=620, border=True):
                        st.html(page)
                else:
                    st.warning("Could not draw this file as a page. Showing the text instead.")
                    with st.container(height=560, border=True):
                        st.text(cand["resume_text"] or "")
            st.download_button("Download original file", data=lambda: path.read_bytes(), file_name=path.name,
                               icon=":material/download:", on_click="ignore", key=f"d_dl_{cid}")
        else:
            st.warning("The resume file was not found in the resumes folder (it may have been moved or deleted).")
            with st.container(height=420, border=True):
                st.text(cand["resume_text"] or "No extracted text stored.")

    with tab_profile:
        contact = []
        if cand["email"]:
            contact.append(f":material/mail: [{cand['email']}](mailto:{cand['email']})")
        if cand["phone"]:
            contact.append(f":material/call: {cand['phone']}")
        if contact:
            st.markdown("  ·  ".join(contact))
        st.markdown("**Summary**")
        st.write(cand["summary"] or "No summary available.")
        skills = [s.strip() for s in (cand["skills"] or "").split(",") if s.strip()]
        st.markdown("**Skills**")
        st.markdown(skill_badges(skills, "blue", 40) if skills else "_None detected_")
        if cand["education"]:
            st.markdown("**Education**")
            st.write(cand["education"])
        if cand["parse_notes"]:
            st.warning("Needs a quick check: " + cand["parse_notes"], icon=":material/rule:")
        res = next((r for r in (ss.results or []) if r["id"] == cid), None) if ctx else None
        if res:
            st.markdown(f"**Why #{res['rank']} for {ctx['job_title']}**")
            for label, key in [("Skills", "skill_score"), ("Keyword relevance", "text_score"),
                               ("Experience fit", "exp_score"), ("Title similarity", "title_score")]:
                st.progress(res[key] / 100, text=f"{label}: {res[key]}")
            if res["matched"]:
                st.markdown("Matched: " + skill_badges(res["matched"], "green", 30))
            if res["missing"]:
                st.markdown("Not found: " + skill_badges(res["missing"], "gray", 30))

    with tab_history:
        log = db.status_log(cid=cid)
        if log.empty:
            st.caption("No actions recorded for this candidate yet.")
        else:
            show = log[["job_title", "status", "timestamp", "reviewed_by", "notes"]].rename(columns={
                "job_title": "Position", "status": "Action", "timestamp": "Date and time",
                "reviewed_by": "By", "notes": "Notes"})
            st.dataframe(show, hide_index=True, width="stretch", alt="Actions recorded for this candidate")


# ----------------------------------------------------------------------------
# Sidebar: reviewer name, folder watcher, Excel
# ----------------------------------------------------------------------------
@st.fragment(run_every="20s")
def folder_watcher() -> None:
    """Looks for new resumes in the folder every 20 seconds while the app is open."""
    result = ingest.scan_folder(max_new=25)  # also done by run_app.py's background watcher; safe to do twice
    if result.added:
        ss.flash = f"Added {len(result.added)} new resume(s): " + ", ".join(result.added[:3]) + ("..." if len(result.added) > 3 else "")
        st.rerun()
    if db.data_version() != ss.get("seen_version"):  # the background watcher added or changed something
        added = db.count_candidates() - ss.get("seen_count", 0)
        if added > 0:
            ss.flash = f"{added} new resume(s) added to the database"
        st.rerun()
    pending = ingest.pending_files()
    if pending:
        st.caption(f":material/sync: {pending} resume(s) waiting to be imported...")
        if result.processed:
            st.rerun(scope="fragment")
    else:
        st.caption(f":material/check_circle: Folder checked at {datetime.now().strftime('%H:%M:%S')}")
    if result.failed:
        st.warning(result.failed[0], icon=":material/error:")


with st.sidebar:
    st.header("HR resume matcher", divider="blue")
    st.text_input("Reviewing as", key="reviewer", help="Your name is saved with every action you take, so the team can see who did what.")
    ss.seen_version = db.data_version()
    cands = load_candidates(ss.seen_version, False)
    ss.seen_count = len(cands)
    jobs = db.load_jobs()
    c1, c2 = st.columns(2)
    c1.metric("Resumes", len(cands))
    c2.metric("Open positions", int((jobs["status"] == "Open").sum()) if not jobs.empty else 0)

    st.markdown("**Resume folder**")
    st.caption(f"`{config.RESUMES_DIR}`")
    if config.CONFIG_NOTE:
        st.warning(config.CONFIG_NOTE, icon=":material/folder_off:")
    folder_watcher()
    st.markdown("**Excel database**")
    exported = db.get_meta("excel_exported_at")
    st.caption(f"`{config.EXCEL_PATH.name}` · updated {exported}" if exported else "Not created yet.")
    if db.get_meta("excel_dirty") == "1":
        st.warning("Excel is out of date (probably open in Excel).", icon=":material/warning:")
    st.button("Update Excel now", icon=":material/table_view:", on_click=cb_export_excel, width="stretch")

show_flash()

cand_idx = cands.set_index("id").to_dict("index") if not cands.empty else {}

st.title("Resume matcher", icon=":material/groups:")
st.caption("Match job descriptions against your resume database, track every decision per position, and export shortlists.")

tab_match, tab_all, tab_add, tab_jobs, tab_activity = st.tabs([
    ":material/search: Find candidates", ":material/groups: All candidates", ":material/upload_file: Add resumes",
    ":material/work: Positions", ":material/history: Activity",
])

# ============================================================================
# Tab 1: find candidates
# ============================================================================
with tab_match:
    open_jobs = jobs[jobs["status"] == "Open"] if not jobs.empty else jobs
    job_ids = [CUSTOM, *open_jobs["id"].tolist()]
    job_labels = {CUSTOM: "Custom search (paste a job description)"}
    job_labels.update({r.id: f"{r.id} · {r.title}" for r in open_jobs.itertuples()})
    if ss.job_pick not in job_ids:
        ss.job_pick = CUSTOM

    with st.container(border=True):
        left, right = st.columns([3, 2], gap="large")
        with left:
            st.selectbox("Position", job_ids, key="job_pick", format_func=job_labels.get, on_change=cb_apply_job,
                         help="Pick an open position to load its job description, or choose 'Custom search'.")
            st.text_area("Job description", key="jd_text", height=190,
                         placeholder="Paste the job description here, or upload a file below...")
            st.file_uploader("Or upload a job description file", type=["pdf", "docx", "txt"], key="jd_file",
                             on_change=cb_jd_upload, help="PDF, Word or text. The text is placed in the box above.")
        with right:
            st.text_input("Must-have skills or keywords", key="must_have", placeholder="e.g. Kubernetes, Terraform, payroll",
                          help="Comma separated. These count double in the score. Works for any skill, not just technical ones.")
            st.toggle("Only show people who have all of them", key="strict_must")

        st.segmented_control("Ranking", list(matcher.MODES), key="mode", default="Balanced", required=True)
        st.caption(matcher.MODES[ss.mode]["help"])

        with st.expander("Filters", icon=":material/tune:"):
            f1, f2, f3 = st.columns(3)
            f1.slider("Experience (years)", 0.0, 40.0, (0.0, 40.0), step=0.5, key="exp_range")
            locations = sorted({city(l) for l in cands["location"] if l}) if not cands.empty else []
            f2.multiselect("Location", locations, key="loc_filter", placeholder="Any location")
            f3.slider("Minimum match score", 0, 90, 0, step=5, key="min_score")
            st.toggle("Hide candidates already rejected for this position", value=True, key="hide_rejected")

        st.button("Find matching candidates", type="primary", icon=":material/search:", on_click=cb_search, width="stretch")

    if msg := ss.get("search_msg"):
        {"warning": st.warning, "info": st.info}[msg[0]](msg[1])

    results, ctx = ss.results, ss.ctx
    if results is not None and ctx:
        states = db.status_map(ctx["job_id"])
        counts = {s: 0 for s in STATUSES}
        for r in results:
            counts[states.get(r["id"], EMPTY_STATE)["status"]] += 1

        head_l, head_r = st.columns([3, 2], vertical_alignment="bottom")
        with head_l:
            st.subheader(f"Ranked candidates for {ctx['job_title']}")
            st.caption(f"{ctx['mode']} ranking · {len(results)} of {ctx['all']} candidates · run {ctx['ran_at']}")
        with head_r:
            if ctx["job_id"].startswith(("JOB-CUSTOM", "CUSTOM-")):
                with st.popover("Save as a position", icon=":material/bookmark_add:"):
                    st.caption("Saves this job description as a position in the Positions tab. "
                               "Viewed / shortlisted / rejected is then tracked against it.")
                    st.text_input("Position title", key="new_position_title",
                                  value=ctx["job_title"] if ctx["job_id"].startswith("CUSTOM-") else "")
                    st.button("Save", on_click=cb_save_position, key="save_pos")

        m = st.columns(4)
        m[0].metric("Strong matches (70+)", sum(r["score"] >= 70 for r in results), border=True)
        m[1].metric("Good matches (40-69)", sum(40 <= r["score"] < 70 for r in results), border=True)
        m[2].metric("Shortlisted", counts["Shortlisted"], border=True)
        m[3].metric("Rejected", counts["Rejected"], border=True)

        c_sort, c_status = st.columns([2, 3])
        c_sort.segmented_control("Sort by", SORTS, key="sort_by", required=True)
        c_status.pills("Show", STATUSES, selection_mode="multi", default=STATUSES, key="status_filter")

        wanted = set(ss.status_filter or STATUSES)
        view = [r for r in results if r["id"] in cand_idx and states.get(r["id"], EMPTY_STATE)["status"] in wanted]
        if ss.sort_by == "Experience: high to low":
            view.sort(key=lambda r: -cand_idx[r["id"]]["experience"])
        elif ss.sort_by == "Experience: low to high":
            view.sort(key=lambda r: cand_idx[r["id"]]["experience"])
        elif ss.sort_by == "Name A-Z":
            view.sort(key=lambda r: cand_idx[r["id"]]["name"].lower())
        shown = view[: ss.show_n]
        shown_ids = [r["id"] for r in shown]

        # ----- bulk actions -----
        selected_ids = [r["id"] for r in results if r["id"] in ss.selected and r["id"] in cand_idx]
        with st.container(border=True):
            b1, b2 = st.columns([2, 5], vertical_alignment="center")
            with b1:
                if selected_ids:
                    st.markdown(f"**{len(selected_ids)} selected**")
                else:
                    st.caption("Tick candidates to act on several at once.")
            with b2, st.container(horizontal=True, horizontal_alignment="right"):
                st.button("Select top 10", icon=":material/done_all:", on_click=cb_select, args=(shown_ids[:10],))
                if selected_ids:
                    st.button("Shortlist", icon=":material/check_circle:", type="primary", on_click=cb_bulk_status, args=("Shortlisted",))
                    with st.popover("Reject", icon=":material/cancel:"):
                        st.selectbox("Reason", REJECT_REASONS, key="bulk_reason")
                        st.button("Reject selected", on_click=cb_bulk_status, args=("Rejected", "bulk_reason"), key="bulk_rej")
                    with st.popover("Export", icon=":material/ios_share:"):
                        order = {r["id"]: r for r in results}
                        report = pd.DataFrame([{
                            "Rank": order[cid]["rank"], "Candidate ID": cid, "Name": cand_idx[cid]["name"],
                            "Title": cand_idx[cid]["title"], "Company": cand_idx[cid]["company"],
                            "Experience": cand_idx[cid]["experience"], "Location": cand_idx[cid]["location"],
                            "Email": cand_idx[cid]["email"], "Phone": cand_idx[cid]["phone"],
                            "Match score": order[cid]["score"],
                            "Status": states.get(cid, EMPTY_STATE)["status"],
                            "Position": ctx["job_title"], "Generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        } for cid in selected_ids]).sort_values("Rank")
                        files = [cand_idx[c]["resume_file"] for c in report["Candidate ID"] if cand_idx[c]["resume_file"]]
                        stamp = datetime.now().strftime("%Y%m%d_%H%M")
                        slug = ctx["job_id"]
                        st.download_button("Shortlist report (CSV)", data=exports.shortlist_csv(report),
                                           file_name=f"Shortlist_{slug}_{stamp}.csv", mime="text/csv",
                                           icon=":material/table_chart:", on_click="ignore", width="stretch", key="x_csv")
                        st.download_button("Resumes combined into one PDF",
                                           data=lambda: exports.merge_pdfs(files)[0],
                                           file_name=f"Resumes_{slug}_{stamp}.pdf", mime="application/pdf",
                                           icon=":material/picture_as_pdf:", on_click="ignore", width="stretch", key="x_pdf")
                        st.caption("Only PDF resumes can be combined; Word files are skipped.")
                        mail_to = st.text_input("Email to", key="mail_to", placeholder="manager@company.com")
                        subject = f"Shortlisted candidates - {ctx['job_title']}"
                        sender, job_title = ss.reviewer, ctx["job_title"]  # captured now: the download is built later
                        st.download_button(
                            "Email draft with resumes attached (.eml)",
                            data=lambda: exports.build_eml(
                                subject, mail_to, exports.email_body_text(job_title, report, sender),
                                report, [(f"Resumes_{slug}.pdf", exports.merge_pdfs(files)[0])]),
                            file_name=f"Email_{slug}_{stamp}.eml", mime="message/rfc822",
                            icon=":material/mail:", on_click="ignore", width="stretch", key="x_eml")
                        st.caption("Open the downloaded file in Outlook to review and send it.")
                    st.button("Clear", icon=":material/close:", on_click=cb_clear_selection)

        # ----- candidate cards -----
        if not view:
            st.info("No candidates to show with the current status filter.")
        for r in shown:
            cid = r["id"]
            c = cand_idx[cid]
            state = states.get(cid, EMPTY_STATE)
            with st.container(border=True):
                col_sel, col_main, col_score = st.columns([0.06, 0.70, 0.24], vertical_alignment="top")
                with col_sel:
                    ss[f"sel_{cid}"] = cid in ss.selected
                    st.checkbox(f"Select {c['name']}", key=f"sel_{cid}", on_change=cb_toggle, args=(cid,),
                                label_visibility="collapsed")
                with col_main:
                    flag = " :orange-badge[Check duplicate]" if "possible duplicate" in (c["parse_notes"] or "") else ""
                    st.markdown(f"**#{r['rank']} · {c['name']}** {badge(state['status'])}{flag}")
                    st.caption(
                        f"{c['title'] or 'Title not detected'}"
                        f"{' · ' + c['company'] if c['company'] else ''}"
                        f"{' · :material/location_on: ' + c['location'] if c['location'] else ''} · {c['experience']:g} yrs"
                    )
                    if r["matched"]:
                        st.markdown(skill_badges(r["matched"], "green", 8))
                    if r["missing"]:
                        st.caption("Not found: " + ", ".join(r["missing"][:6]))
                with col_score:
                    tier = "Strong" if r["score"] >= 70 else "Good" if r["score"] >= 40 else "Weak"
                    st.progress(r["score"] / 100, text=f"{r['score']:.0f}% · {tier}")
                line = status_line(state, ctx["job_title"])
                if line:
                    st.caption(line)
                with st.container(horizontal=True):
                    st.button("View resume", icon=":material/description:", key=f"view_{cid}", on_click=cb_open,
                              args=(cid, c["name"], True))
                    st.button("Shortlist", icon=":material/check_circle:", key=f"sl_{cid}", on_click=cb_set_status,
                              args=("Shortlisted", cid, c["name"]), disabled=state["status"] == "Shortlisted")
                    with st.popover("Reject", icon=":material/cancel:"):
                        st.selectbox("Reason", REJECT_REASONS, key=f"reason_{cid}")
                        st.button("Confirm reject", key=f"rej_{cid}", on_click=cb_set_status,
                                  args=("Rejected", cid, c["name"], f"reason_{cid}"))
                    if state["status"] in ("Shortlisted", "Rejected"):
                        st.button("Undo", icon=":material/undo:", key=f"undo_{cid}", on_click=cb_set_status,
                                  args=("Reset", cid, c["name"]), type="tertiary")
        if len(view) > ss.show_n:
            st.button(f"Show 20 more ({len(view) - ss.show_n} left)", on_click=cb_more, width="stretch")

# ============================================================================
# Tab 2: all candidates
# ============================================================================
with tab_all:
    if cands.empty:
        st.info("No resumes yet. Drop files into the resume folder or use the 'Add resumes' tab.")
    else:
        f1, f2 = st.columns([3, 1], vertical_alignment="bottom")
        q = f1.text_input("Search", key="all_q", placeholder="Name, skill, company, location...", icon=":material/search:")
        review_only = f2.toggle("Needs review only", key="review_only", help="Resumes where the app was unsure about something.")
        table = cands
        if q:
            hay = (table["name"] + " " + table["title"] + " " + table["company"] + " " + table["location"] + " "
                   + table["skills"] + " " + table["email"]).str.lower()
            table = table[hay.str.contains(q.lower().strip(), regex=False)]
        if review_only:
            table = table[table["parse_notes"] != ""]
        table = table.reset_index(drop=True)
        st.caption(f"{len(table)} of {len(cands)} candidates · select a row to see the profile")
        event = st.dataframe(
            table[["id", "name", "title", "company", "location", "experience", "skills", "email", "phone", "parse_notes"]],
            hide_index=True, width="stretch", height=360, on_select="rerun", selection_mode="single-row", key="cand_table",
            alt="All candidates", column_config={
                "id": st.column_config.TextColumn("ID", width="small"), "name": "Name", "title": "Title",
                "company": "Company", "location": "Location",
                "experience": st.column_config.NumberColumn("Exp (yrs)", format="%.1f", width="small"),
                "skills": "Skills", "email": "Email", "phone": "Phone", "parse_notes": "Needs review",
            })
        rows = event.selection.rows
        if rows and rows[0] < len(table):
            cur = table.iloc[rows[0]]
            cid = cur["id"]
            with st.container(border=True):
                h1, h2 = st.columns([3, 1], vertical_alignment="center")
                h1.markdown(f"### {cur['name']}  \n{cur['title']} · {cur['company']} · {cur['location']}")
                h2.button("View resume", icon=":material/description:", key=f"all_view_{cid}", on_click=cb_open,
                          args=(cid, cur["name"], False), type="primary", width="stretch")
                if cur["parse_notes"]:
                    st.warning(cur["parse_notes"], icon=":material/rule:")
                with st.form(f"edit_{cid}"):
                    st.caption("Fix anything the app got wrong. Changes are saved to the database and the Excel file.")
                    e1, e2, e3 = st.columns(3)
                    name = e1.text_input("Name", cur["name"])
                    title = e2.text_input("Current title", cur["title"])
                    company = e3.text_input("Current company", cur["company"])
                    e4, e5, e6 = st.columns(3)
                    email = e4.text_input("Email", cur["email"])
                    phone = e5.text_input("Phone", cur["phone"])
                    location = e6.text_input("Location", cur["location"])
                    e7, e8 = st.columns([1, 3])
                    exp = e7.number_input("Experience (years)", 0.0, 60.0, float(cur["experience"]), step=0.5)
                    skills = e8.text_input("Skills (comma separated)", cur["skills"])
                    summary = st.text_area("Summary", cur["summary"], height=100)
                    if st.form_submit_button("Save changes", type="primary", icon=":material/save:"):
                        db.update_candidate(cid, name=name, title=title, company=company, email=email, phone=phone,
                                            location=location, experience=exp, skills=skills, summary=summary,
                                            parse_notes="")
                        db.set_meta("excel_dirty", "1")
                        exports.export_excel()
                        ss.flash = f"Saved {name}"
                        st.rerun()
                with st.expander("Delete this candidate", icon=":material/delete:"):
                    also_file = st.checkbox("Also delete the resume file from the folder", key=f"delfile_{cid}")
                    sure = st.checkbox("Yes, delete permanently", key=f"delsure_{cid}")
                    if st.button("Delete", disabled=not sure, key=f"del_{cid}"):
                        full = db.get_candidate(cid)
                        db.delete_candidate(cid)
                        if also_file and full and full["resume_file"]:
                            exports.resume_path(full["resume_file"]).unlink(missing_ok=True)
                        db.set_meta("excel_dirty", "1")
                        exports.export_excel()
                        ss.flash = f"Deleted {cur['name']}"
                        st.rerun()

# ============================================================================
# Tab 3: add resumes
# ============================================================================
with tab_add:
    st.markdown(
        f"**Easiest way:** copy resume files (PDF, Word or text) into the folder below. The app checks it every 20 seconds "
        f"and adds them automatically, and the Excel file next to them is updated."
    )
    st.code(str(config.RESUMES_DIR), language=None)
    a1, a2, a3 = st.columns(3)
    a1.metric("Files in folder", len(ingest.list_resume_files()), border=True)
    a2.metric("In database", len(cands), border=True)
    a3.metric("Waiting to import", ingest.pending_files(), border=True)
    if st.button("Import everything in the folder now", icon=":material/sync:"):
        with st.spinner("Reading resumes... a large folder can take a minute or two."):
            res = ingest.scan_folder(max_new=None)
        ss.flash = f"Imported {len(res.added)} new resume(s); {res.duplicates} duplicate(s) skipped."
        if res.failed:
            ss.flash += f" {len(res.failed)} problem(s)."
        st.rerun()

    st.markdown("**Or upload here**")
    uploads = st.file_uploader("Drop resumes", type=["pdf", "docx", "txt"], accept_multiple_files=True,
                               key=f"uploader_{ss.uploader_n}", label_visibility="collapsed")
    if uploads and st.button(f"Add {len(uploads)} resume(s) to the database", type="primary", icon=":material/person_add:"):
        report, progress = [], st.progress(0.0, text="Reading resumes...")
        for i, f in enumerate(uploads, 1):
            out = ingest.ingest_file(ingest.save_upload(f.name, f.getvalue()))
            report.append({"File": f.name, "Result": {"added": "Added", "duplicate": "Already in database",
                                                     "failed": "Failed"}[out["status"]],
                           "Name": out["name"], "Notes": "; ".join(out["notes"])})
            progress.progress(i / len(uploads), text=f"Read {i} of {len(uploads)}")
        if any(r["Result"] == "Added" for r in report):
            db.set_meta("excel_dirty", "1")
            exports.export_excel()
        ss.upload_report = pd.DataFrame(report)
        ss.uploader_n += 1
        st.rerun()
    if ss.upload_report is not None:
        st.markdown("**Last upload**")
        st.dataframe(ss.upload_report, hide_index=True, width="stretch", alt="Result of the last upload")
    st.caption("Scanned (image-only) PDFs have no text to read and are flagged 'needs review'. "
               "Everything stays on this computer.")

# ============================================================================
# Tab 4: positions
# ============================================================================
with tab_jobs:
    if config.SAMPLE_JOBS.exists():
        with st.expander("Sample positions for testing", icon=":material/science:"):
            st.caption("Adds 16 ready-made job descriptions (engineering, data, product, design, HR, finance, sales, "
                       "marketing, support). Positions that already exist are skipped.")
            st.button("Load sample positions", icon=":material/playlist_add:", on_click=cb_load_samples)
    if jobs.empty:
        st.info("No positions yet. Add the first one below.")
        selected_job = None
    else:
        ev = st.dataframe(
            jobs[["id", "title", "department", "location", "experience_required", "status", "posted_date"]],
            hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row", key="jobs_table",
            alt="Open and closed positions",
            column_config={"id": "ID", "title": "Title", "department": "Department", "location": "Location",
                           "experience_required": "Experience", "status": "Status", "posted_date": "Posted"})
        selected_job = jobs.iloc[ev.selection.rows[0]] if ev.selection.rows else None

    mode = st.segmented_control("Action", ["Add new position", "Edit selected position"], default="Add new position",
                                key="job_mode", required=True)
    editing = mode == "Edit selected position"
    if editing and selected_job is None:
        st.info("Select a position in the table above to edit it.")
    else:
        base = selected_job if editing else None
        k = base["id"] if base is not None else "new"
        with st.form(f"job_form_{k}", clear_on_submit=not editing):
            j1, j2 = st.columns(2)
            jt = j1.text_input("Title", base["title"] if base is not None else "")
            jdept = j2.text_input("Department", base["department"] if base is not None else "")
            j3, j4, j5 = st.columns(3)
            jloc = j3.text_input("Location", base["location"] if base is not None else "")
            jexp = j4.text_input("Experience", base["experience_required"] if base is not None else "", placeholder="e.g. 4-8 years")
            jst = j5.selectbox("Status", ["Open", "Closed"], index=0 if base is None or base["status"] != "Closed" else 1)
            jdesc = st.text_area("Job description", base["description"] if base is not None else "", height=220)
            if st.form_submit_button("Save position", type="primary", icon=":material/save:"):
                if not jt.strip():
                    st.error("Title is required.")
                else:
                    db.save_job(base["id"] if base is not None else None, jt.strip(), jdept, jloc, jexp, jdesc, jst)
                    db.set_meta("excel_dirty", "1")
                    ss.flash = f"Saved position '{jt.strip()}'"
                    st.rerun()
        if editing and base is not None:
            with st.expander("Delete this position", icon=":material/delete:"):
                st.caption("The history of viewed / shortlisted / rejected stays in the Activity log.")
                if st.checkbox("Yes, delete it", key=f"jobdel_{base['id']}") and st.button("Delete position"):
                    db.delete_job(base["id"])
                    ss.flash = "Position deleted"
                    st.rerun()

# ============================================================================
# Tab 5: activity
# ============================================================================
with tab_activity:
    pipe = db.pipeline()
    st.subheader("Pipeline by position")
    if pipe.empty:
        st.caption("Nothing yet. View, shortlist or reject candidates and they will appear here.")
    else:
        st.dataframe(pipe, hide_index=True, width="stretch", alt="Candidates per position by status")
    st.subheader("Full activity log")
    log = db.status_log()
    if log.empty:
        st.caption("No activity recorded yet.")
    else:
        l1, l2, l3 = st.columns(3)
        pos = l1.multiselect("Position", sorted(log["job_title"].unique()), placeholder="All positions")
        act = l2.multiselect("Action", ["Viewed", "Shortlisted", "Rejected", "Reset"], placeholder="All actions")
        who = l3.multiselect("Reviewed by", sorted(log["reviewed_by"].unique()), placeholder="Anyone")
        if pos:
            log = log[log["job_title"].isin(pos)]
        if act:
            log = log[log["status"].isin(act)]
        if who:
            log = log[log["reviewed_by"].isin(who)]
        show = log[["timestamp", "job_title", "candidate_name", "status", "notes", "reviewed_by"]].rename(columns={
            "timestamp": "Date and time", "job_title": "Position", "candidate_name": "Candidate", "status": "Action",
            "notes": "Notes", "reviewed_by": "By"})
        st.dataframe(show, hide_index=True, width="stretch", alt="Activity log")
        st.download_button("Download log (CSV)", data=exports.shortlist_csv(show), file_name="Activity_log.csv",
                           mime="text/csv", icon=":material/download:", on_click="ignore")

# Open the resume drawer last, once per click
if opened := ss.pop("open_resume", None):
    resume_dialog(*opened)
