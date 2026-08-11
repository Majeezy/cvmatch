"""Application tracker — DB-backed (per user), with Excel export."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import TRACKER_DIR, user_dir
from models import Application, db

COLUMNS = [
    "date_applied",
    "company",
    "job_title",
    "seniority_level",
    "status",
    "deadline",
    "cv_path",
    "cover_letter_path",
    "job_description_path",
    "notes",
    "post_interview_notes",
    "ats_score",
    "match_score",
    "source_url",
]

STATUS_OPTIONS = ["Applied", "Interview Scheduled", "Interviewed", "Offer", "Rejected", "Withdrawn"]


def load_tracker(user_id: int) -> list[dict]:
    """Load all of a user's application records, oldest first (stable index order)."""
    rows = Application.query.filter_by(user_id=user_id).order_by(Application.id.asc()).all()
    return [r.to_dict() for r in rows]


def get_application(user_id: int, index: int) -> Application | None:
    """Look up the Nth (0-based, insertion-order) application row for a user."""
    rows = Application.query.filter_by(user_id=user_id).order_by(Application.id.asc()).all()
    if 0 <= index < len(rows):
        return rows[index]
    return None


def add_application(user_id: int, entry: dict) -> Application:
    """Add a new application record and auto-export to Excel."""
    app = Application(
        user_id=user_id,
        company=entry.get("company", ""),
        job_title=entry.get("job_title", ""),
        seniority_level=entry.get("seniority_level", ""),
        status=entry.get("status", "Applied"),
        deadline=entry.get("deadline", ""),
        cv_path=entry.get("cv_path", ""),
        cover_letter_path=entry.get("cover_letter_path", ""),
        job_description_path=entry.get("job_description_path", ""),
        notes=entry.get("notes", ""),
        post_interview_notes=entry.get("post_interview_notes", ""),
        ats_score=entry.get("ats_score"),
        match_score=entry.get("match_score"),
        source_url=entry.get("source_url", ""),
    )
    if entry.get("date_applied"):
        app.date_applied = entry["date_applied"]
    db.session.add(app)
    db.session.commit()
    export_to_excel(user_id)
    return app


def export_to_excel(user_id: int, records: list[dict] | None = None) -> Path:
    """Write this user's applications.xlsx from current DB data."""
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment

    if records is None:
        records = load_tracker(user_id)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Applications"

    header_fill = PatternFill("solid", fgColor="1F497D")
    header_font = Font(bold=True, color="FFFFFF")
    headers = [c.replace("_", " ").title() for c in COLUMNS]

    for col_idx, header in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    for row_idx, record in enumerate(records, start=2):
        for col_idx, key in enumerate(COLUMNS, start=1):
            ws.cell(row=row_idx, column=col_idx, value=str(record.get(key, "")))

    for col in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 50)

    out_path = user_dir(TRACKER_DIR, user_id) / "applications.xlsx"
    wb.save(out_path)
    return out_path


def get_analytics_data(user_id: int) -> dict:
    """Compute analytics from a user's tracker records."""
    from collections import defaultdict
    from datetime import date, timedelta

    records = load_tracker(user_id)
    total = len(records)

    counts = {s: 0 for s in STATUS_OPTIONS}
    for r in records:
        s = r.get("status", "Applied")
        if s in counts:
            counts[s] += 1

    interviews = counts.get("Interview Scheduled", 0) + counts.get("Interviewed", 0)
    offers = counts.get("Offer", 0)
    active = total - counts.get("Rejected", 0) - counts.get("Withdrawn", 0)

    today = date.today()
    day_counts: dict[str, int] = defaultdict(int)
    for r in records:
        d = r.get("date_applied", "")
        if d:
            day_counts[d] += 1
    heatmap = []
    for i in range(365):
        d = (today - timedelta(days=364 - i)).isoformat()
        heatmap.append({"date": d, "count": day_counts.get(d, 0)})

    week_counts: dict[str, int] = defaultdict(int)
    for r in records:
        d = r.get("date_applied", "")
        if d:
            try:
                dt = date.fromisoformat(d)
                iso = dt.isocalendar()
                week_key = f"{iso.year}-W{iso.week:02d}"
                week_counts[week_key] += 1
            except ValueError:
                pass
    by_week = []
    for i in range(26):
        dt = today - timedelta(weeks=25 - i)
        iso = dt.isocalendar()
        wk = f"{iso.year}-W{iso.week:02d}"
        by_week.append({"week": wk, "count": week_counts.get(wk, 0)})

    funnel_order = ["Applied", "Interview Scheduled", "Interviewed", "Offer"]
    funnel = []
    for s in funnel_order:
        reached = sum(1 for r in records if _status_rank(r.get("status", "")) >= _status_rank(s))
        funnel.append({"status": s, "count": reached})

    return {
        "total": total,
        "active": active,
        "by_status": counts,
        "interview_rate": round(interviews / total * 100) if total else 0,
        "offer_rate": round(offers / total * 100) if total else 0,
        "heatmap": heatmap,
        "by_week": by_week,
        "funnel": funnel,
        "recent": records[-5:][::-1],
    }


_STATUS_RANK = {
    "Applied": 1,
    "Interview Scheduled": 2,
    "Interviewed": 3,
    "Offer": 4,
    "Rejected": 0,
    "Withdrawn": 0,
}


def _status_rank(status: str) -> int:
    return _STATUS_RANK.get(status, 0)
