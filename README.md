# CVMatch

By [ORBITAL](https://github.com/Majeezy), Technology Engineering & Digital
Solutions. *Connect. Secure. Build.*

A web app that tailors your CV and generates cover letters for each job
application using AI (Groq's `llama-3.3-70b-versatile`), with an application
tracker, ATS scoring, interview prep, and more. Formerly "Job Application
Assistant" — same backend, rebranded and hardened for real users.

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
their own key in the browser instead. `PAYFAST_*` and `RESEND_API_KEY` are
only needed to test billing/email verification locally — see `DEPLOY.md`.

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

Signup sends a verification email (Resend). Upgrading to Pro is gated on
`email_verified` — an account can use the free tier unverified, but can't
pay until it's confirmed.

If you have data from an older single-user version of this app (a flat
`applications_tracker/applications.json` with no owner), run:
```bash
python migrate_legacy_data.py you@example.com
```
after creating your account, to import it under that account.

---

## Billing

PayFast (South African, ZAR-native — Stripe doesn't support direct South
African merchant accounts, and Yoco doesn't support recurring billing; see
`DEPLOY.md` §1 for setup, and `payfast.py`'s module docstring for what's
been verified against PayFast's real sandbox vs. what's still unverified).
PayFast has no hosted customer portal like Stripe's, so subscription
cancellation is a direct API call from the app's own UI, not a redirect.

---

## Project Structure

```
job_application_assistant/        (directory name unchanged; app is CVMatch)
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
├── auth.py                 ← signup/login/logout/email-verification routes
├── billing.py               ← PayFast checkout + webhook (Flask blueprint layer)
├── payfast.py                ← PayFast signing/validation/API client (no Flask dependency)
├── email_sender.py           ← Resend transactional email (verification only, so far)
├── config.py
├── server.py                ← Flask app (the actual web server)
├── migrate_legacy_data.py   ← one-off import of old single-user tracker data
├── requirements.txt
└── .env                     ← secrets (never commit this)
```
