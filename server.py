"""Flask web server — CVMatch, by ORBITAL (formerly Job Application Assistant).
Run: python server.py
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from flask import Flask, Response, jsonify, request, send_file, send_from_directory, session
from flask_login import current_user, login_required
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv()

from config import DATABASE_URL, user_dir
from models import db

app = Flask(__name__, static_folder=str(ROOT), static_url_path="")

# Render terminates TLS at its own edge and forwards plain HTTP internally
# -- without this, Flask has no way to know the original request was
# HTTPS, so request.url_root (and anything built from it, like the
# return_url/notify_url sent to PayFast in billing.py's _origin()) comes
# out as http://, not https://. x_proto=1 trusts exactly one hop's
# X-Forwarded-Proto, matching Render's own single reverse-proxy setup.
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

_secret = os.environ.get("FLASK_SECRET")
if not _secret:
    # No persisted secret — generate one and write it to .env so sessions
    # (and logins) survive a server restart instead of being invalidated.
    import secrets
    _secret = secrets.token_hex(32)
    env_path = ROOT / ".env"
    with open(env_path, "a", encoding="utf-8") as f:
        f.write(f"\nFLASK_SECRET={_secret}\n")
    print(f"  No FLASK_SECRET set — generated one and saved it to {env_path}")
app.secret_key = _secret

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

from auth import init_auth
init_auth(app)

from billing import init_billing
init_billing(app)

with app.app_context():
    db.create_all()


# ── Helpers ────────────────────────────────────────────────────────────────

def _save_upload(file, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    filename = secure_filename(file.filename) or "upload"
    out = dest_dir / filename
    file.save(out)
    return out


def _safe_name(name: str) -> str:
    """Strip any path components from a client-supplied filename."""
    return Path(name or "").name


def _api_key() -> str:
    data = request.get_json(silent=True) or {}
    return data.get("api_key", "").strip()


def _parse_raw(raw: str) -> dict:
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    return json.loads(raw)


# ── Index & Static ─────────────────────────────────────────────────────────

@app.route("/")
def index():
    prefill = request.args.get("bookmarklet_url", "")
    html = (ROOT / "gui.html").read_text(encoding="utf-8")
    if prefill:
        inject = f'<script>window._bookmarkletUrl={json.dumps(prefill)};</script>'
        html = html.replace("</head>", inject + "\n</head>", 1)
    return html


# ── CV ─────────────────────────────────────────────────────────────────────

@app.route("/api/cvs")
@login_required
def list_cvs():
    from config import MASTER_CV_DIR
    d = user_dir(MASTER_CV_DIR, current_user.id)
    names = sorted([p.name for p in d.glob("*.pdf")] + [p.name for p in d.glob("*.docx")])
    return jsonify(names)


@app.route("/api/upload/cv", methods=["POST"])
@login_required
def upload_cv():
    from config import MASTER_CV_DIR
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    saved = _save_upload(request.files["file"], user_dir(MASTER_CV_DIR, current_user.id))
    session["cv_path"] = str(saved)
    return jsonify({"name": saved.name})


@app.route("/api/select/cv", methods=["POST"])
@login_required
def select_cv():
    from config import MASTER_CV_DIR
    name = _safe_name((request.get_json() or {}).get("name", ""))
    path = user_dir(MASTER_CV_DIR, current_user.id) / name
    if not path.exists():
        return jsonify({"error": "File not found"}), 404
    session["cv_path"] = str(path)
    return jsonify({"name": name})


# ── Job Description ────────────────────────────────────────────────────────

@app.route("/api/upload/jd", methods=["POST"])
@login_required
def upload_jd():
    from config import JOB_DESCRIPTIONS_DIR
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    saved = _save_upload(request.files["file"], user_dir(JOB_DESCRIPTIONS_DIR, current_user.id))
    session["jd_path"] = str(saved)
    return jsonify({"name": saved.name})


@app.route("/api/paste/jd", methods=["POST"])
@login_required
def paste_jd():
    from config import JOB_DESCRIPTIONS_DIR
    data = request.get_json() or {}
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "No text provided"}), 400
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    d = user_dir(JOB_DESCRIPTIONS_DIR, current_user.id)
    path = d / f"job_{ts}.txt"
    path.write_text(text, encoding="utf-8")
    session["jd_path"] = str(path)
    return jsonify({"name": path.name, "words": len(text.split())})


@app.route("/api/fetch-url", methods=["POST"])
@login_required
def fetch_url_endpoint():
    from config import JOB_DESCRIPTIONS_DIR
    from scripts.scraper import scrape_job_url
    data = request.get_json() or {}
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"error": "No URL provided"}), 400
    try:
        text = scrape_job_url(url)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    d = user_dir(JOB_DESCRIPTIONS_DIR, current_user.id)
    path = d / f"job_url_{ts}.txt"
    path.write_text(text, encoding="utf-8")
    session["jd_path"] = str(path)
    session["source_url"] = url
    return jsonify({"name": path.name, "words": len(text.split()), "preview": text[:1200]})


# ── Analyze ────────────────────────────────────────────────────────────────

@app.route("/api/analyze", methods=["POST"])
@login_required
def analyze():
    from scripts.extract import extract_text
    from scripts.analyzer import analyze_job
    data = request.get_json() or {}
    api_key = data.get("api_key", "").strip()
    cv_path = session.get("cv_path")
    jd_path = session.get("jd_path")
    if not cv_path: return jsonify({"error": "No CV selected"}), 400
    if not jd_path: return jsonify({"error": "No job description"}), 400
    if not api_key: return jsonify({"error": "No API key"}), 400
    try:
        cv_text = extract_text(cv_path)
        jd_text = extract_text(jd_path)
    except Exception as e:
        return jsonify({"error": f"Extraction failed: {e}"}), 500
    try:
        result = analyze_job(jd_text, api_key)
    except Exception as e:
        return jsonify({"error": f"Analysis failed: {e}"}), 500
    session["analysis"] = result
    session["jd_text_cache"] = jd_text[:6000]
    return jsonify(result)


# ── Match Score ────────────────────────────────────────────────────────────

@app.route("/api/match-score", methods=["POST"])
@login_required
def match_score():
    from scripts.extract import extract_text
    from scripts.match_score import calculate_match_score
    data = request.get_json() or {}
    api_key = data.get("api_key", "").strip()
    cv_path = session.get("cv_path")
    analysis = session.get("analysis")
    if not cv_path or not analysis: return jsonify({"error": "Run Analyze first"}), 400
    if not api_key: return jsonify({"error": "No API key"}), 400
    try:
        cv_text = extract_text(cv_path)
        result = calculate_match_score(cv_text, analysis, api_key)
        session["match_score_result"] = result
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── ATS Score ──────────────────────────────────────────────────────────────

@app.route("/api/ats-score", methods=["POST"])
@login_required
def ats_score():
    from scripts.extract import extract_text
    from scripts.ats_score import simulate_ats_score
    data = request.get_json() or {}
    api_key = data.get("api_key", "").strip()
    cv_path = session.get("cv_path")
    analysis = session.get("analysis")
    if not cv_path: return jsonify({"error": "No CV in session"}), 400
    if not api_key: return jsonify({"error": "No API key"}), 400
    try:
        cv_text = extract_text(cv_path)
        result = simulate_ats_score(cv_text, analysis or {}, api_key)
        session["ats_score_result"] = result
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Red Flags ──────────────────────────────────────────────────────────────

@app.route("/api/red-flags", methods=["POST"])
@login_required
def red_flags():
    from scripts.extract import extract_text
    from scripts.red_flag_detector import detect_red_flags
    data = request.get_json() or {}
    api_key = data.get("api_key", "").strip()
    jd_text = data.get("jd_text", "")
    if not jd_text:
        jd_path = session.get("jd_path")
        if not jd_path: return jsonify({"error": "No job description"}), 400
        try:
            jd_text = extract_text(jd_path)
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    if not api_key: return jsonify({"error": "No API key"}), 400
    try:
        result = detect_red_flags(jd_text, session.get("analysis") or {}, api_key)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Company Research ───────────────────────────────────────────────────────

@app.route("/api/company-research", methods=["POST"])
@login_required
def company_research():
    from scripts.company_research import research_company
    data = request.get_json() or {}
    api_key = data.get("api_key", "").strip()
    if not api_key: return jsonify({"error": "No API key"}), 400
    analysis = session.get("analysis") or {}
    company = data.get("company") or analysis.get("company", "")
    job_title = data.get("job_title") or analysis.get("title", "")
    if not company: return jsonify({"error": "No company name"}), 400
    try:
        result = research_company(
            company=company,
            job_title=job_title,
            industry=analysis.get("industry", ""),
            seniority=analysis.get("seniority_level", ""),
            api_key=api_key,
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Skills Roadmap ─────────────────────────────────────────────────────────

@app.route("/api/skills-roadmap", methods=["POST"])
@login_required
def skills_roadmap():
    from scripts.skills_gap import generate_skills_roadmap
    data = request.get_json() or {}
    api_key = data.get("api_key", "").strip()
    if not api_key: return jsonify({"error": "No API key"}), 400
    missing = data.get("missing_skills") or []
    matched = data.get("matched_skills") or []
    analysis = session.get("analysis") or {}
    try:
        result = generate_skills_roadmap(missing, matched, analysis, api_key)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Rejection Analyzer ─────────────────────────────────────────────────────

@app.route("/api/rejection-analysis", methods=["POST"])
@login_required
def rejection_analysis():
    from scripts.extract import extract_text
    from scripts.rejection_analyzer import analyze_rejection
    data = request.get_json() or {}
    api_key = data.get("api_key", "").strip()
    if not api_key: return jsonify({"error": "No API key"}), 400
    cv_context = ""
    cv_path = session.get("cv_path")
    if cv_path:
        try:
            cv_context = extract_text(cv_path)[:2000]
        except Exception:
            pass
    try:
        result = analyze_rejection(
            job_title=data.get("job_title", ""),
            company=data.get("company", ""),
            feedback=data.get("feedback", ""),
            stage=data.get("stage", "initial screening"),
            date_applied=data.get("date_applied", ""),
            cv_context=cv_context,
            api_key=api_key,
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Salary Negotiation ─────────────────────────────────────────────────────

@app.route("/api/salary-negotiation", methods=["POST"])
@login_required
def salary_negotiation():
    from scripts.salary_negotiation import generate_negotiation_scripts
    data = request.get_json() or {}
    api_key = data.get("api_key", "").strip()
    if not api_key: return jsonify({"error": "No API key"}), 400
    analysis = session.get("confirmed_analysis") or session.get("analysis") or {}
    try:
        text = generate_negotiation_scripts(
            job_title=data.get("job_title") or analysis.get("title", ""),
            company=data.get("company") or analysis.get("company", ""),
            offered_salary=data.get("offered_salary", "not disclosed"),
            target_salary=data.get("target_salary", "market rate"),
            currency=data.get("currency", "USD"),
            benefits=data.get("benefits", "standard"),
            location=data.get("location", "on-site"),
            deadline=data.get("deadline", "not specified"),
            seniority=analysis.get("seniority_level", ""),
            strengths=data.get("strengths", ""),
            api_key=api_key,
        )
        return jsonify({"script": text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── LinkedIn Optimizer ─────────────────────────────────────────────────────

@app.route("/api/linkedin-optimize", methods=["POST"])
@login_required
def linkedin_optimize():
    from scripts.linkedin_optimizer import optimize_linkedin_profile
    data = request.get_json() or {}
    api_key = data.get("api_key", "").strip()
    if not api_key: return jsonify({"error": "No API key"}), 400
    analysis = session.get("analysis") or {}
    try:
        result = optimize_linkedin_profile(
            headline=data.get("headline", ""),
            about=data.get("about", ""),
            job_analysis=analysis,
            api_key=api_key,
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Generate ───────────────────────────────────────────────────────────────

@app.route("/api/generate", methods=["POST"])
@login_required
def generate():
    from config import TAILORED_CVS_DIR, COVER_LETTERS_DIR
    from scripts.extract import extract_text
    from scripts.tailor_cv import tailor_cv, save_tailored_cv
    from scripts.cover_letter import generate_cover_letter, save_cover_letter
    from scripts.tracker import add_application
    from scripts.version_history import save_version
    from billing import check_generation_quota

    data = request.get_json() or {}
    api_key = data.get("api_key", "").strip()
    job_title = data.get("job_title", "").strip()
    company = data.get("company", "").strip()
    applicant_name = data.get("applicant_name", "").strip()
    tone = data.get("tone", "formal")

    cv_path = session.get("cv_path")
    analysis = session.get("analysis")
    jd_path = session.get("jd_path")
    if not cv_path or not analysis: return jsonify({"error": "Run Analyze first"}), 400
    if not api_key: return jsonify({"error": "No API key"}), 400

    quota_error = check_generation_quota(current_user)
    if quota_error:
        return jsonify({"error": quota_error, "upgrade_required": True}), 402

    try:
        cv_text = extract_text(cv_path)
    except Exception as e:
        return jsonify({"error": f"Could not read CV: {e}"}), 500

    confirmed = {**analysis, "title": job_title, "company": company}

    try:
        tailored = tailor_cv(cv_text, confirmed, api_key)
        cv_out = save_tailored_cv(tailored, job_title, company, output_dir=user_dir(TAILORED_CVS_DIR, current_user.id))
    except Exception as e:
        return jsonify({"error": f"CV tailoring failed: {e}"}), 500

    try:
        letter = generate_cover_letter(cv_text, confirmed, api_key, tone=tone)
        cl_out = save_cover_letter(letter, job_title, company, applicant_name, output_dir=user_dir(COVER_LETTERS_DIR, current_user.id))
    except Exception as e:
        return jsonify({"error": f"Cover letter failed: {e}"}), 500

    # Save to version history
    meta = {"company": company, "job_title": job_title, "file_path": str(cv_out)}
    save_version(current_user.id, "tailored_cv", tailored, meta)
    save_version(current_user.id, "cover_letter", letter, {**meta, "file_path": str(cl_out)})

    match_result = session.get("match_score_result") or {}
    ats_result = session.get("ats_score_result") or {}

    add_application(current_user.id, {
        "company": company,
        "job_title": job_title,
        "seniority_level": confirmed.get("seniority_level", ""),
        "cv_path": str(cv_out),
        "cover_letter_path": str(cl_out),
        "job_description_path": jd_path or "",
        "source_url": session.get("source_url", ""),
        "match_score": match_result.get("overall_score"),
        "ats_score": ats_result.get("ats_score"),
    })

    session["tailored_cv_path"] = str(cv_out)
    session["cover_letter_path"] = str(cl_out)
    session["cv_text_cache"] = cv_text
    session["confirmed_analysis"] = confirmed
    session["tailored_text_cache"] = tailored
    session["letter_text_cache"] = letter

    return jsonify({"cv_filename": cv_out.name, "cl_filename": cl_out.name})


# ── Cover Letter Tone Regeneration ─────────────────────────────────────────

@app.route("/api/cover-letter/regenerate", methods=["POST"])
@login_required
def regenerate_cover_letter():
    from config import COVER_LETTERS_DIR
    from scripts.extract import extract_text
    from scripts.cover_letter import generate_cover_letter, save_cover_letter
    from scripts.version_history import save_version
    data = request.get_json() or {}
    api_key = data.get("api_key", "").strip()
    tone = data.get("tone", "formal")
    if not api_key: return jsonify({"error": "No API key"}), 400
    cv_path = session.get("cv_path")
    analysis = session.get("confirmed_analysis") or session.get("analysis")
    if not cv_path or not analysis: return jsonify({"error": "Generate documents first"}), 400
    try:
        cv_text = extract_text(cv_path)
        letter = generate_cover_letter(cv_text, analysis, api_key, tone=tone)
        cl_out = save_cover_letter(letter, analysis.get("title", ""), analysis.get("company", ""), output_dir=user_dir(COVER_LETTERS_DIR, current_user.id))
        save_version(current_user.id, "cover_letter", letter, {"company": analysis.get("company",""), "job_title": analysis.get("title",""), "file_path": str(cl_out), "tone": tone})
        session["cover_letter_path"] = str(cl_out)
        session["letter_text_cache"] = letter
        return jsonify({"text": letter, "filename": cl_out.name})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Interview Prep ─────────────────────────────────────────────────────────

@app.route("/api/interview-questions", methods=["POST"])
@login_required
def interview_questions():
    from scripts.interview_prep import generate_interview_questions
    from scripts.version_history import save_version
    data = request.get_json() or {}
    api_key = data.get("api_key", "").strip()
    cv_text = session.get("cv_text_cache", "")
    analysis = session.get("confirmed_analysis") or session.get("analysis")
    if not cv_text or not analysis: return jsonify({"error": "Generate documents first"}), 400
    if not api_key: return jsonify({"error": "No API key"}), 400
    try:
        result = generate_interview_questions(cv_text, analysis, api_key)
        save_version(current_user.id, "interview_questions", json.dumps(result, indent=2),
                     {"company": analysis.get("company",""), "job_title": analysis.get("title","")})
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Follow-up Email ────────────────────────────────────────────────────────

@app.route("/api/followup-email", methods=["POST"])
@login_required
def followup_email():
    from scripts.followup import generate_followup_email
    data = request.get_json() or {}
    api_key = data.get("api_key", "").strip()
    if not api_key: return jsonify({"error": "No API key"}), 400
    try:
        result = generate_followup_email(
            job_title=data.get("job_title", ""),
            company=data.get("company", ""),
            applicant_name=data.get("applicant_name", ""),
            days_since=int(data.get("days_since", 7)),
            status=data.get("status", "Applied"),
            context=data.get("context", ""),
            api_key=api_key,
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Document Preview ───────────────────────────────────────────────────────

@app.route("/api/preview/cv")
@login_required
def preview_cv_text():
    from scripts.extract import extract_text
    path = session.get("tailored_cv_path")
    if not path or not Path(path).exists(): return jsonify({"error": "No CV generated"}), 404
    try:
        return jsonify({"text": extract_text(path), "filename": Path(path).name})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/preview/cl")
@login_required
def preview_cl_text():
    from scripts.extract import extract_text
    path = session.get("cover_letter_path")
    if not path or not Path(path).exists(): return jsonify({"error": "No cover letter generated"}), 404
    try:
        return jsonify({"text": extract_text(path), "filename": Path(path).name})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── PDF Downloads ──────────────────────────────────────────────────────────

@app.route("/api/download/cv")
@login_required
def download_cv():
    path = session.get("tailored_cv_path")
    if not path or not Path(path).exists(): return "File not found", 404
    return send_file(path, as_attachment=True)


@app.route("/api/download/cl")
@login_required
def download_cl():
    path = session.get("cover_letter_path")
    if not path or not Path(path).exists(): return "File not found", 404
    return send_file(path, as_attachment=True)


@app.route("/api/download/cv-pdf")
@login_required
def download_cv_pdf():
    from config import TAILORED_CVS_DIR
    from scripts.extract import extract_text
    from scripts.pdf_exporter import export_cv_pdf
    path = session.get("tailored_cv_path")
    if not path or not Path(path).exists(): return "No CV generated yet", 404
    try:
        analysis = session.get("confirmed_analysis") or {}
        cv_text = extract_text(path)
        pdf_path = export_cv_pdf(cv_text, analysis.get("title", "CV"), analysis.get("company", ""), output_dir=user_dir(TAILORED_CVS_DIR, current_user.id))
        return send_file(str(pdf_path), as_attachment=True)
    except Exception as e:
        return f"PDF generation failed: {e}", 500


@app.route("/api/download/cl-pdf")
@login_required
def download_cl_pdf():
    from config import COVER_LETTERS_DIR
    from scripts.extract import extract_text
    from scripts.pdf_exporter import export_cl_pdf
    path = session.get("cover_letter_path")
    if not path or not Path(path).exists(): return "No cover letter generated yet", 404
    try:
        analysis = session.get("confirmed_analysis") or {}
        cl_text = extract_text(path)
        pdf_path = export_cl_pdf(cl_text, analysis.get("title", "Role"), analysis.get("company", ""), output_dir=user_dir(COVER_LETTERS_DIR, current_user.id))
        return send_file(str(pdf_path), as_attachment=True)
    except Exception as e:
        return f"PDF generation failed: {e}", 500


# ── Bulk Apply (SSE) ───────────────────────────────────────────────────────

@app.route("/api/bulk-apply", methods=["POST"])
@login_required
def bulk_apply():
    from config import JOB_DESCRIPTIONS_DIR, TAILORED_CVS_DIR, COVER_LETTERS_DIR
    from scripts.scraper import scrape_job_url
    from scripts.extract import extract_text
    from scripts.analyzer import analyze_job
    from scripts.tailor_cv import tailor_cv, save_tailored_cv
    from scripts.cover_letter import generate_cover_letter, save_cover_letter
    from scripts.tracker import add_application
    from billing import check_bulk_apply_allowed

    data = request.get_json() or {}
    api_key = data.get("api_key", "").strip()
    urls = data.get("urls", [])
    applicant_name = data.get("applicant_name", "")
    cv_path = session.get("cv_path")
    user_id = current_user.id  # capture now — current_user isn't available once the request context ends

    if not cv_path: return jsonify({"error": "No CV selected"}), 400
    if not api_key: return jsonify({"error": "No API key"}), 400
    if not urls: return jsonify({"error": "No URLs provided"}), 400

    bulk_error = check_bulk_apply_allowed(current_user)
    if bulk_error:
        return jsonify({"error": bulk_error, "upgrade_required": True}), 402

    def _stream():
        try:
            cv_text = extract_text(cv_path)
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e), 'done': True})}\n\n"
            return

        results = []
        for i, url in enumerate(urls[:10]):  # cap at 10
            prog = {"index": i, "total": len(urls), "url": url, "status": "fetching"}
            yield f"data: {json.dumps(prog)}\n\n"
            try:
                jd_text = scrape_job_url(url)
                prog["status"] = "analyzing"
                yield f"data: {json.dumps(prog)}\n\n"

                analysis = analyze_job(jd_text, api_key)
                prog["company"] = analysis.get("company", "Unknown")
                prog["title"] = analysis.get("title", "Role")
                prog["status"] = "generating"
                yield f"data: {json.dumps(prog)}\n\n"

                tailored = tailor_cv(cv_text, analysis, api_key)
                cv_out = save_tailored_cv(tailored, analysis.get("title",""), analysis.get("company",""), output_dir=user_dir(TAILORED_CVS_DIR, user_id))
                letter = generate_cover_letter(cv_text, analysis, api_key)
                cl_out = save_cover_letter(letter, analysis.get("title",""), analysis.get("company",""), applicant_name, output_dir=user_dir(COVER_LETTERS_DIR, user_id))

                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                jd_path = user_dir(JOB_DESCRIPTIONS_DIR, user_id) / f"bulk_{ts}.txt"
                jd_path.write_text(jd_text, encoding="utf-8")

                add_application(user_id, {
                    "company": analysis.get("company", ""),
                    "job_title": analysis.get("title", ""),
                    "seniority_level": analysis.get("seniority_level", ""),
                    "cv_path": str(cv_out), "cover_letter_path": str(cl_out),
                    "job_description_path": str(jd_path), "source_url": url,
                })
                prog["status"] = "done"
                prog["cv_filename"] = cv_out.name
                prog["cl_filename"] = cl_out.name
                results.append(prog)
                yield f"data: {json.dumps(prog)}\n\n"
            except Exception as e:
                prog["status"] = "error"
                prog["error"] = str(e)
                results.append(prog)
                yield f"data: {json.dumps(prog)}\n\n"

        yield f"data: {json.dumps({'done': True, 'results': results})}\n\n"

    return Response(_stream(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ── Tracker ────────────────────────────────────────────────────────────────

@app.route("/api/tracker")
@login_required
def get_tracker():
    from scripts.tracker import load_tracker
    return jsonify(load_tracker(current_user.id))


@app.route("/api/tracker/analytics")
@login_required
def tracker_analytics():
    from scripts.tracker import get_analytics_data
    return jsonify(get_analytics_data(current_user.id))


@app.route("/api/tracker/save", methods=["POST"])
@login_required
def save_tracker():
    from scripts.tracker import get_application, export_to_excel
    data = request.get_json() or {}
    updates = data.get("updates", [])
    for upd in updates:
        i = upd.get("index")
        if i is None:
            continue
        app_row = get_application(current_user.id, i)
        if not app_row:
            continue
        for field in ["status", "notes", "deadline", "post_interview_notes"]:
            if field in upd:
                setattr(app_row, field, upd[field])
    db.session.commit()
    export_to_excel(current_user.id)
    return jsonify({"ok": True})


@app.route("/api/tracker/update-field", methods=["POST"])
@login_required
def update_tracker_field():
    from scripts.tracker import get_application, export_to_excel
    data = request.get_json() or {}
    idx = data.get("index")
    field = data.get("field")
    value = data.get("value")
    if idx is None or field is None:
        return jsonify({"error": "Invalid request"}), 400
    app_row = get_application(current_user.id, idx)
    if not app_row:
        return jsonify({"error": "Invalid request"}), 400
    setattr(app_row, field, value)
    db.session.commit()
    export_to_excel(current_user.id)
    return jsonify({"ok": True})


@app.route("/api/tracker/delete/<int:idx>", methods=["DELETE"])
@login_required
def delete_application(idx):
    from scripts.tracker import get_application, export_to_excel
    app_row = get_application(current_user.id, idx)
    if not app_row:
        return jsonify({"error": "Invalid index"}), 400
    db.session.delete(app_row)
    db.session.commit()
    export_to_excel(current_user.id)
    return jsonify({"ok": True})


@app.route("/api/tracker/excel")
@login_required
def tracker_excel():
    from config import TRACKER_DIR
    from scripts.tracker import export_to_excel
    excel_path = export_to_excel(current_user.id)
    if not excel_path.exists(): return "No data yet.", 404
    return send_file(str(excel_path), as_attachment=True, download_name="applications.xlsx")


# ── Version History ────────────────────────────────────────────────────────

@app.route("/api/history")
@login_required
def get_history():
    from scripts.version_history import load_history
    gen_type = request.args.get("type")
    return jsonify(load_history(current_user.id, gen_type or None))


@app.route("/api/history/<vid>")
@login_required
def get_history_item(vid):
    from scripts.version_history import load_history, get_version_content
    records = load_history(current_user.id)
    meta = next((r for r in records if r["id"] == vid), None)
    if not meta: return jsonify({"error": "Not found"}), 404
    content = get_version_content(current_user.id, vid)
    return jsonify({**meta, "content": content})


@app.route("/api/history/<vid>", methods=["DELETE"])
@login_required
def delete_history_item(vid):
    from scripts.version_history import delete_version
    ok = delete_version(current_user.id, vid)
    return jsonify({"ok": ok})


# ── Entry Point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from waitress import serve

    port = int(os.environ.get("PORT", 8080))
    print("\n  ==========================================")
    print("   CVMatch, by ORBITAL")
    print(f"   Local: http://localhost:{port}")
    print("  ==========================================\n")
    serve(app, host="0.0.0.0", port=port)
