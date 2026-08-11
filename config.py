import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Project root
ROOT = Path(__file__).parent

# Base directory for all uploaded/generated data. Defaults to ROOT for local
# dev; set DATA_DIR to a mounted persistent disk path in production (e.g.
# Render), since ROOT itself may live on ephemeral storage there.
DATA_DIR = Path(os.environ.get("DATA_DIR", str(ROOT)))

# Directories
MASTER_CV_DIR = DATA_DIR / "master_cv"
JOB_DESCRIPTIONS_DIR = DATA_DIR / "job_descriptions"
TAILORED_CVS_DIR = DATA_DIR / "tailored_cvs"
COVER_LETTERS_DIR = DATA_DIR / "cover_letters"
TRACKER_DIR = DATA_DIR / "applications_tracker"
TEMPLATES_DIR = ROOT / "templates"
VERSION_HISTORY_DIR = DATA_DIR / "version_history"
PDF_OUTPUT_DIR = DATA_DIR / "pdf_exports"

TRACKER_JSON = TRACKER_DIR / "applications.json"
TRACKER_EXCEL = TRACKER_DIR / "applications.xlsx"

# Database — defaults to a local SQLite file; set DATABASE_URL to a Postgres
# connection string in production (e.g. Render's managed Postgres).
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{ROOT / 'app.db'}")

# Groq model (free)
MODEL = "llama-3.3-70b-versatile"

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

# Free-plan monthly generation limit (a "generation" = one tailored CV +
# cover letter pair). Bulk Apply is a Pro-only feature regardless of count.
FREE_MONTHLY_GENERATIONS = 3


def user_dir(base: Path, user_id: int) -> Path:
    """Per-user subfolder of a shared base directory, e.g. master_cv/<user_id>/."""
    d = base / str(user_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_client(api_key: str = ""):
    """Return a configured Groq client."""
    from groq import Groq
    key = api_key or GROQ_API_KEY
    if not key:
        raise EnvironmentError("GROQ_API_KEY not set.")
    return Groq(api_key=key)
