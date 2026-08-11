# Job Application Assistant

A web app that tailors your CV and generates cover letters for each job
application using AI (Groq's `llama-3.3-70b-versatile`), with an application
tracker, ATS scoring, interview prep, and more.

## Quick Start

### 1. Install dependencies
```bash
cd C:\Users\kmaje\Documents\job_application_assistant
pip install -r requirements.txt
```

### 2. Configure environment
```bash
copy .env.example .env
```
Open `.env` and set a `FLASK_SECRET` (a long random string — keep it stable,
changing it logs everyone out). `GROQ_API_KEY` is optional: users can supply
their own key in the browser instead.

### 3. Run
```bash
python server.py
```
Then open http://localhost:8080, sign up for an account, and use the app —
upload a CV, add a job description, analyze, and generate a tailored CV +
cover letter.

On Windows, the desktop shortcut created by `setup_shortcut.ps1` launches the
same server silently via `launch_app.pyw`.

---

## Accounts & data

Every user's CVs, job descriptions, generated documents, tracker entries, and
version history are isolated per account (see `models.py` for the `User`,
`Application`, and `VersionHistoryEntry` tables). Uploaded/generated files
live under per-user subfolders of `master_cv/`, `job_descriptions/`,
`tailored_cvs/`, and `cover_letters/`.

If you have data from an older single-user version of this app (a flat
`applications_tracker/applications.json` with no owner), run:
```bash
python migrate_legacy_data.py you@example.com
```
after creating your account, to import it under that account.

---

## Project Structure

```
job_application_assistant/
├── master_cv/            ← per-user uploaded CVs
├── job_descriptions/     ← per-user job postings
├── tailored_cvs/         ← per-user generated output
├── cover_letters/        ← per-user generated output
├── version_history/      ← per-user generation history blobs
├── scripts/
│   ├── extract.py            ← PDF/DOCX text extraction
│   ├── analyzer.py           ← job analysis
│   ├── tailor_cv.py          ← CV rewriting
│   ├── cover_letter.py       ← cover letter generation
│   ├── tracker.py            ← application tracking (DB-backed)
│   ├── version_history.py    ← generation history (DB-backed)
│   └── ...                   ← ATS score, match score, interview prep, etc.
├── legacy/                ← retired Streamlit UI + old CLI, kept for reference
├── models.py               ← SQLAlchemy models (User, Application, VersionHistoryEntry)
├── auth.py                 ← signup/login/logout routes
├── config.py
├── server.py                ← Flask app (the actual web server)
├── migrate_legacy_data.py   ← one-off import of old single-user tracker data
├── requirements.txt
└── .env                     ← FLASK_SECRET / GROQ_API_KEY (never commit this)
```
