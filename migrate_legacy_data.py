"""One-off: import the old global applications_tracker/applications.json
(from the pre-accounts version of this app) into the new per-user Application
table. Run once, after creating your account:

    python migrate_legacy_data.py you@example.com
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from server import app
from config import TRACKER_JSON
from models import Application, User, db


def main():
    if len(sys.argv) != 2:
        print("Usage: python migrate_legacy_data.py <email>")
        sys.exit(1)
    email = sys.argv[1].strip().lower()

    with app.app_context():
        user = User.query.filter_by(email=email).first()
        if not user:
            print(f"No account found for {email}. Sign up in the app first, then re-run this.")
            sys.exit(1)

        if not TRACKER_JSON.exists():
            print(f"No legacy tracker file found at {TRACKER_JSON}. Nothing to migrate.")
            return

        with open(TRACKER_JSON, "r", encoding="utf-8") as f:
            records = json.load(f)

        if not records:
            print("Legacy tracker file is empty. Nothing to migrate.")
            return

        imported = 0
        for r in records:
            db.session.add(Application(
                user_id=user.id,
                date_applied=r.get("date_applied", ""),
                company=r.get("company", ""),
                job_title=r.get("job_title", ""),
                seniority_level=r.get("seniority_level", ""),
                status=r.get("status", "Applied"),
                deadline=r.get("deadline", ""),
                cv_path=r.get("cv_path", ""),
                cover_letter_path=r.get("cover_letter_path", ""),
                job_description_path=r.get("job_description_path", ""),
                notes=r.get("notes", ""),
                post_interview_notes=r.get("post_interview_notes", ""),
                ats_score=r.get("ats_score"),
                match_score=r.get("match_score"),
                source_url=r.get("source_url", ""),
            ))
            imported += 1

        db.session.commit()
        print(f"Imported {imported} application(s) from {TRACKER_JSON} into {email}'s account.")


if __name__ == "__main__":
    main()
