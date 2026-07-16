"""Account-level data operations, notably GDPR/CCPA "delete my data".

The backend uses the Supabase service role, so it can remove every trace of a
user across storage and the database in one call.
"""
import logging

from ..config import Settings

logger = logging.getLogger(__name__)

# Rows are deleted children-first so foreign keys never block the delete.
_USER_TABLES = ("chat_messages", "exams", "documents", "user_daily_usage", "app_users")


def delete_all_user_data(sb, settings: Settings, user_id: str) -> None:
    """Remove all of a user's storage objects and database rows.

    Best-effort on storage (a missing object shouldn't block the DB cleanup),
    strict on the database rows.
    """
    # 1. Uploaded documents in the documents bucket.
    docs = (
        sb.table("documents")
        .select("storage_path")
        .eq("user_id", user_id)
        .execute()
    )
    doc_paths = [d["storage_path"] for d in (docs.data or []) if d.get("storage_path")]
    if doc_paths:
        try:
            sb.storage.from_(settings.documents_bucket).remove(doc_paths)
        except Exception:
            logger.warning("Failed to remove some document objects for %s", user_id)

    # 2. Rendered exports in the exports bucket.
    exams = (
        sb.table("exams").select("export_path").eq("user_id", user_id).execute()
    )
    export_paths = [
        e["export_path"] for e in (exams.data or []) if e.get("export_path")
    ]
    if export_paths:
        try:
            sb.storage.from_(settings.exports_bucket).remove(export_paths)
        except Exception:
            logger.warning("Failed to remove some export objects for %s", user_id)

    # 3. Database rows.
    for table in _USER_TABLES:
        sb.table(table).delete().eq("user_id", user_id).execute()
