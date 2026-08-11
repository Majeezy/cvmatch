"""SQLAlchemy models — users, tracked applications, generation history."""
from datetime import date, datetime

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(255), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    plan = db.Column(db.String(20), nullable=False, default="free")
    stripe_customer_id = db.Column(db.String(255), nullable=True, index=True)
    stripe_subscription_id = db.Column(db.String(255), nullable=True)
    subscription_status = db.Column(db.String(50), nullable=True)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Application(db.Model):
    """One tracked job application — replaces the old flat tracker JSON."""
    __tablename__ = "applications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    date_applied = db.Column(db.String(20), default=lambda: date.today().isoformat())
    company = db.Column(db.String(255), default="")
    job_title = db.Column(db.String(255), default="")
    seniority_level = db.Column(db.String(100), default="")
    status = db.Column(db.String(50), default="Applied")
    deadline = db.Column(db.String(20), default="")
    cv_path = db.Column(db.Text, default="")
    cover_letter_path = db.Column(db.Text, default="")
    job_description_path = db.Column(db.Text, default="")
    notes = db.Column(db.Text, default="")
    post_interview_notes = db.Column(db.Text, default="")
    ats_score = db.Column(db.Integer, nullable=True)
    match_score = db.Column(db.Integer, nullable=True)
    source_url = db.Column(db.Text, default="")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "date_applied": self.date_applied or "",
            "company": self.company or "",
            "job_title": self.job_title or "",
            "seniority_level": self.seniority_level or "",
            "status": self.status or "Applied",
            "deadline": self.deadline or "",
            "cv_path": self.cv_path or "",
            "cover_letter_path": self.cover_letter_path or "",
            "job_description_path": self.job_description_path or "",
            "notes": self.notes or "",
            "post_interview_notes": self.post_interview_notes or "",
            "ats_score": self.ats_score,
            "match_score": self.match_score,
            "source_url": self.source_url or "",
        }


class VersionHistoryEntry(db.Model):
    """One saved AI generation (tailored CV, cover letter, interview Qs, ...)."""
    __tablename__ = "version_history"

    id = db.Column(db.String(36), primary_key=True)  # uuid4 string
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    timestamp = db.Column(db.String(30), default=lambda: datetime.now().isoformat(timespec="seconds"))
    type = db.Column(db.String(50), default="")
    company = db.Column(db.String(255), default="")
    job_title = db.Column(db.String(255), default="")
    file_path = db.Column(db.Text, default="")
    preview = db.Column(db.Text, default="")
    tone = db.Column(db.String(50), default="")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp or "",
            "type": self.type or "",
            "company": self.company or "",
            "job_title": self.job_title or "",
            "file_path": self.file_path or "",
            "preview": self.preview or "",
            "tone": self.tone or "",
        }
