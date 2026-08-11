"""Version history — DB-backed (per user) index, flat-file content blobs."""
import sys
import uuid
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import VERSION_HISTORY_DIR, user_dir
from models import VersionHistoryEntry, db


def save_version(user_id: int, gen_type: str, content: str, metadata: dict) -> dict:
    """Save a generation to history. Returns the new record."""
    vid = str(uuid.uuid4())
    content_file = user_dir(VERSION_HISTORY_DIR, user_id) / f"{vid}.txt"
    content_file.write_text(content, encoding="utf-8")

    entry = VersionHistoryEntry(
        id=vid,
        user_id=user_id,
        timestamp=datetime.now().isoformat(timespec="seconds"),
        type=gen_type,
        company=metadata.get("company", ""),
        job_title=metadata.get("job_title", ""),
        file_path=metadata.get("file_path", ""),
        preview=content[:200].replace("\n", " "),
        tone=metadata.get("tone", ""),
    )
    db.session.add(entry)
    db.session.commit()
    return entry.to_dict()


def load_history(user_id: int, gen_type: str | None = None) -> list[dict]:
    q = VersionHistoryEntry.query.filter_by(user_id=user_id)
    if gen_type:
        q = q.filter_by(type=gen_type)
    rows = q.order_by(VersionHistoryEntry.timestamp.desc()).all()
    return [r.to_dict() for r in rows]


def get_version_content(user_id: int, vid: str) -> str | None:
    entry = VersionHistoryEntry.query.filter_by(id=vid, user_id=user_id).first()
    if not entry:
        return None
    f = user_dir(VERSION_HISTORY_DIR, user_id) / f"{vid}.txt"
    if not f.exists():
        return None
    return f.read_text(encoding="utf-8")


def delete_version(user_id: int, vid: str) -> bool:
    entry = VersionHistoryEntry.query.filter_by(id=vid, user_id=user_id).first()
    if not entry:
        return False
    db.session.delete(entry)
    db.session.commit()
    content_file = user_dir(VERSION_HISTORY_DIR, user_id) / f"{vid}.txt"
    if content_file.exists():
        content_file.unlink()
    return True
