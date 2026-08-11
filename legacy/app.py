"""
Job Application Assistant — Streamlit Web UI
Run: streamlit run app.py
"""
import sys
import os
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

import streamlit as st

st.set_page_config(
    page_title="Job Application Assistant",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.title("📄 Job Application\nAssistant")
page = st.sidebar.radio(
    "Navigate",
    ["New Application", "Applications Tracker"],
    label_visibility="collapsed",
)
st.sidebar.divider()

from dotenv import load_dotenv
load_dotenv()
_env_key = os.environ.get("GROQ_API_KEY", "")

ANTHROPIC_API_KEY = st.sidebar.text_input(
    "Groq API Key (free)",
    value=_env_key,
    type="password",
    placeholder="gsk_...",
    help="Get a free key at console.groq.com",
).strip()

if not ANTHROPIC_API_KEY:
    st.sidebar.warning("Enter your free Groq API key to use AI features.")

st.sidebar.divider()
st.sidebar.caption("Powered by Llama 3.3 via Groq (free)")

# ── Session state ─────────────────────────────────────────────────────────────
for k, v in {
    "cv_path": None,
    "job_path": None,
    "cv_text": "",
    "job_text": "",
    "job_analysis": None,
    "job_title": "",
    "company": "",
    "applicant_name": "",
    "tailored_cv_path": None,
    "cover_letter_path": None,
    "generated": False,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v


def save_upload(uploaded_file, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    out = dest_dir / uploaded_file.name
    out.write_bytes(uploaded_file.getbuffer())
    return out


# ── Page: New Application ─────────────────────────────────────────────────────
if page == "New Application":
    from config import MASTER_CV_DIR, JOB_DESCRIPTIONS_DIR

    st.title("New Job Application")

    # ── Step 1: CV ────────────────────────────────────────────────────────────
    st.header("Step 1 — Your CV")
    col1, col2 = st.columns([2, 1])

    with col1:
        existing_cvs = sorted(
            list(MASTER_CV_DIR.glob("*.pdf")) + list(MASTER_CV_DIR.glob("*.docx"))
        )
        cv_source = st.radio("CV source", ["Choose existing CV", "Upload new CV"], horizontal=True)

        if cv_source == "Choose existing CV":
            if existing_cvs:
                selected = st.selectbox("Select CV", [p.name for p in existing_cvs])
                st.session_state.cv_path = str(MASTER_CV_DIR / selected)
                st.success(f"Selected: {selected}")
            else:
                st.warning("No CV found in master_cv/ — upload one using the option above.")
                st.session_state.cv_path = None
        else:
            uploaded_cv = st.file_uploader("Upload your CV", type=["pdf", "docx"], key="cv_upload")
            if uploaded_cv:
                saved = save_upload(uploaded_cv, MASTER_CV_DIR)
                st.session_state.cv_path = str(saved)
                st.success(f"Uploaded: {uploaded_cv.name}")

    with col2:
        st.session_state.applicant_name = st.text_input(
            "Your full name (for cover letter)",
            value=st.session_state.applicant_name,
        )

    if st.session_state.cv_path:
        st.caption(f"CV ready: `{Path(st.session_state.cv_path).name}`")

    st.divider()

    # ── Step 2: Job Description ───────────────────────────────────────────────
    st.header("Step 2 — Job Description")
    jd_tab1, jd_tab2, jd_tab3 = st.tabs(["Upload file", "Paste text", "From URL"])

    with jd_tab1:
        uploaded_jd = st.file_uploader("Upload job description", type=["txt", "pdf"], key="jd_upload")
        if uploaded_jd:
            saved_jd = save_upload(uploaded_jd, JOB_DESCRIPTIONS_DIR)
            st.session_state.job_path = str(saved_jd)
            st.success(f"Uploaded: {uploaded_jd.name}")

    with jd_tab2:
        pasted = st.text_area(
            "Paste job description here",
            height=220,
            placeholder="Copy and paste the full job posting...",
        )
        if st.button("Use this text"):
            if pasted.strip():
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                jd_path = JOB_DESCRIPTIONS_DIR / f"job_{ts}.txt"
                JOB_DESCRIPTIONS_DIR.mkdir(parents=True, exist_ok=True)
                jd_path.write_text(pasted, encoding="utf-8")
                st.session_state.job_path = str(jd_path)
                st.success("Job description saved.")
            else:
                st.warning("Paste some text first.")

    with jd_tab3:
        job_url = st.text_input(
            "Job posting URL",
            placeholder="https://careers.company.com/job/123",
        )
        if st.button("Fetch job from URL"):
            if job_url.strip():
                from scripts.scraper import scrape_job_url
                with st.spinner("Fetching page..."):
                    try:
                        scraped = scrape_job_url(job_url.strip())
                        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                        jd_path = JOB_DESCRIPTIONS_DIR / f"job_url_{ts}.txt"
                        JOB_DESCRIPTIONS_DIR.mkdir(parents=True, exist_ok=True)
                        jd_path.write_text(scraped, encoding="utf-8")
                        st.session_state.job_path = str(jd_path)
                        st.success(f"Fetched {len(scraped.split())} words.")
                        with st.expander("Preview"):
                            st.text(scraped[:1500] + ("..." if len(scraped) > 1500 else ""))
                    except ValueError as e:
                        st.error(str(e))
            else:
                st.warning("Enter a URL first.")

    if st.session_state.job_path:
        st.caption(f"Job description ready: `{Path(st.session_state.job_path).name}`")

    st.divider()

    # ── Step 3: Analyze ───────────────────────────────────────────────────────
    st.header("Step 3 — Analyze Job")

    missing = []
    if not st.session_state.cv_path:
        missing.append("CV (Step 1)")
    if not st.session_state.job_path:
        missing.append("Job description (Step 2)")
    if not ANTHROPIC_API_KEY:
        missing.append("API key (sidebar)")

    if missing:
        st.info(f"Still needed: {', '.join(missing)}")

    if st.button("Analyze Job Requirements", type="primary", disabled=bool(missing)):
        from scripts.extract import extract_text
        from scripts.analyzer import analyze_job

        with st.spinner("Extracting text from CV and job description..."):
            try:
                st.session_state.cv_text = extract_text(st.session_state.cv_path)
                st.session_state.job_text = extract_text(st.session_state.job_path)
            except Exception as e:
                st.error(f"Extraction failed: {e}")
                st.stop()

        with st.spinner("Analyzing job requirements with Claude..."):
            try:
                st.session_state.job_analysis = analyze_job(
                    st.session_state.job_text, ANTHROPIC_API_KEY
                )
                st.session_state.job_title = st.session_state.job_analysis.get("title", "")
                st.session_state.company = st.session_state.job_analysis.get("company") or ""
                st.session_state.generated = False
                st.success("Analysis complete!")
            except Exception as e:
                st.error(f"Analysis failed: {e}")
                st.stop()

    if st.session_state.job_analysis:
        a = st.session_state.job_analysis
        with st.expander("Analysis Results", expanded=True):
            c1, c2, c3 = st.columns(3)
            c1.metric("Job Title", a.get("title") or "—")
            c2.metric("Company", a.get("company") or "—")
            c3.metric("Seniority", a.get("seniority_level") or "—")

            col_a, col_b = st.columns(2)
            with col_a:
                st.write("**Required Skills**")
                for s in a.get("required_skills", []):
                    st.markdown(f"- {s}")
            with col_b:
                st.write("**ATS Keywords**")
                kws = a.get("keywords", [])
                st.write("  ".join(f"`{k}`" for k in kws))

    st.divider()

    # ── Step 4: Generate ──────────────────────────────────────────────────────
    st.header("Step 4 — Tailor CV & Cover Letter")

    col1, col2 = st.columns(2)
    with col1:
        st.session_state.job_title = st.text_input(
            "Job Title", value=st.session_state.job_title
        )
    with col2:
        st.session_state.company = st.text_input(
            "Company", value=st.session_state.company
        )

    if not st.session_state.job_analysis:
        st.info("Complete Step 3 first.")

    if st.button(
        "Generate Tailored CV + Cover Letter",
        type="primary",
        disabled=not st.session_state.job_analysis or not ANTHROPIC_API_KEY,
    ):
        from scripts.tailor_cv import tailor_cv, save_tailored_cv
        from scripts.cover_letter import generate_cover_letter, save_cover_letter
        from scripts.tracker import add_application

        confirmed = {
            **st.session_state.job_analysis,
            "title": st.session_state.job_title,
            "company": st.session_state.company,
        }

        with st.spinner("Tailoring CV with Claude..."):
            try:
                tailored_text = tailor_cv(st.session_state.cv_text, confirmed, ANTHROPIC_API_KEY)
                cv_out = save_tailored_cv(
                    tailored_text, st.session_state.job_title, st.session_state.company
                )
                st.session_state.tailored_cv_path = str(cv_out)
            except Exception as e:
                st.error(f"CV tailoring failed: {e}")
                st.stop()

        with st.spinner("Writing cover letter with Claude..."):
            try:
                letter_text = generate_cover_letter(
                    st.session_state.cv_text, confirmed, ANTHROPIC_API_KEY
                )
                cl_out = save_cover_letter(
                    letter_text,
                    st.session_state.job_title,
                    st.session_state.company,
                    st.session_state.applicant_name,
                )
                st.session_state.cover_letter_path = str(cl_out)
            except Exception as e:
                st.error(f"Cover letter failed: {e}")
                st.stop()

        add_application({
            "company": st.session_state.company,
            "job_title": st.session_state.job_title,
            "seniority_level": confirmed.get("seniority_level", ""),
            "cv_path": st.session_state.tailored_cv_path,
            "cover_letter_path": st.session_state.cover_letter_path,
            "job_description_path": st.session_state.job_path or "",
        })

        st.session_state.generated = True
        st.success("Done! Documents are ready to download.")

    # ── Downloads ─────────────────────────────────────────────────────────────
    if st.session_state.generated:
        st.divider()
        st.subheader("Download Your Documents")
        dl1, dl2 = st.columns(2)

        with dl1:
            cv_p = st.session_state.tailored_cv_path
            if cv_p and Path(cv_p).exists():
                st.download_button(
                    label="⬇ Download Tailored CV",
                    data=Path(cv_p).read_bytes(),
                    file_name=Path(cv_p).name,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                )

        with dl2:
            cl_p = st.session_state.cover_letter_path
            if cl_p and Path(cl_p).exists():
                st.download_button(
                    label="⬇ Download Cover Letter",
                    data=Path(cl_p).read_bytes(),
                    file_name=Path(cl_p).name,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                )


# ── Page: Applications Tracker ────────────────────────────────────────────────
elif page == "Applications Tracker":
    import pandas as pd
    from scripts.tracker import load_tracker, export_to_excel, STATUS_OPTIONS
    from config import TRACKER_EXCEL, TRACKER_JSON

    st.title("Applications Tracker")

    records = load_tracker()

    if not records:
        st.info("No applications tracked yet. Complete a New Application to get started.")
    else:
        st.write(f"**{len(records)} application(s)**")

        df = pd.DataFrame(records)
        for col in ["date_applied", "company", "job_title", "seniority_level", "status", "notes"]:
            if col not in df.columns:
                df[col] = ""

        edited = st.data_editor(
            df[["date_applied", "company", "job_title", "seniority_level", "status", "notes"]],
            column_config={
                "status": st.column_config.SelectboxColumn("Status", options=STATUS_OPTIONS, required=True),
                "date_applied": st.column_config.TextColumn("Date Applied", disabled=True),
                "company": st.column_config.TextColumn("Company", disabled=True),
                "job_title": st.column_config.TextColumn("Job Title", disabled=True),
                "seniority_level": st.column_config.TextColumn("Level", disabled=True),
                "notes": st.column_config.TextColumn("Notes"),
            },
            hide_index=True,
            use_container_width=True,
        )

        if st.button("Save Changes"):
            for i, row in edited.iterrows():
                if i < len(records):
                    records[i]["status"] = row["status"]
                    records[i]["notes"] = row["notes"]
            with open(TRACKER_JSON, "w", encoding="utf-8") as f:
                json.dump(records, f, indent=2, default=str)
            export_to_excel(records)
            st.success("Saved.")

        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Refresh Excel"):
                export_to_excel(records)
                st.success("Excel updated.")
        with c2:
            if TRACKER_EXCEL.exists():
                st.download_button(
                    label="⬇ Download Excel",
                    data=TRACKER_EXCEL.read_bytes(),
                    file_name="applications.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
