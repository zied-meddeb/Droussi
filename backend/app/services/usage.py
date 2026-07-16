from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException

from ..config import get_settings
from ..db import get_supabase


@dataclass(frozen=True)
class UsageSnapshot:
    """Per-user view for the daily exam quota."""
    exams_used: int
    exams_limit: int
    cost_usd_today: float
    usage_date: date
    resets_at: datetime

    @property
    def remaining(self) -> int:
        return max(0, self.exams_limit - self.exams_used)

    @property
    def percent(self) -> float:
        if self.exams_limit <= 0:
            return 100.0
        return min(100.0, (self.exams_used / self.exams_limit) * 100.0)


def _today_utc() -> date:
    return datetime.now(timezone.utc).date()


def _resets_at_utc(usage_date: date) -> datetime:
    return datetime.combine(
        usage_date + timedelta(days=1),
        datetime.min.time(),
        tzinfo=timezone.utc,
    )


def register_user(user_id: str, email: str | None = None) -> None:
    sb = get_supabase()
    record: dict = {"user_id": user_id}
    if email:
        record["email"] = email
    sb.table("app_users").upsert(record, on_conflict="user_id").execute()


def per_user_limit() -> int:
    """Fixed daily exam quota — the same for every user regardless of how many
    users exist. Adding users no longer shrinks anyone's allowance."""
    return max(get_settings().per_user_exam_limit, 0)


def _get_or_create_daily_row(user_id: str, usage_date: date) -> dict:
    sb = get_supabase()
    date_str = usage_date.isoformat()
    existing = (
        sb.table("user_daily_usage")
        .select("*")
        .eq("user_id", user_id)
        .eq("usage_date", date_str)
        .maybe_single()
        .execute()
    )
    if existing and existing.data:
        return existing.data

    inserted = (
        sb.table("user_daily_usage")
        .insert(
            {
                "user_id": user_id,
                "usage_date": date_str,
                "tokens_used": 0,
                "exam_count": 0,
                "cost_usd": 0,
            }
        )
        .execute()
    )
    if inserted.data:
        return inserted.data[0]

    retry = (
        sb.table("user_daily_usage")
        .select("*")
        .eq("user_id", user_id)
        .eq("usage_date", date_str)
        .maybe_single()
        .execute()
    )
    if not retry or not retry.data:
        raise RuntimeError("Could not initialize daily usage row")
    return retry.data


def get_usage(user_id: str, email: str | None = None) -> UsageSnapshot:
    register_user(user_id, email)
    usage_date = _today_utc()
    row = _get_or_create_daily_row(user_id, usage_date)
    return UsageSnapshot(
        exams_used=int(row.get("exam_count") or 0),
        exams_limit=per_user_limit(),
        cost_usd_today=float(row.get("cost_usd") or 0.0),
        usage_date=usage_date,
        resets_at=_resets_at_utc(usage_date),
    )


def global_cost_today() -> float:
    """Total USD spent across all users for the current UTC day."""
    sb = get_supabase()
    rows = (
        sb.table("user_daily_usage")
        .select("cost_usd")
        .eq("usage_date", _today_utc().isoformat())
        .execute()
    )
    return float(sum(float(r.get("cost_usd") or 0.0) for r in (rows.data or [])))


def ensure_global_capacity() -> None:
    """Account-wide circuit breaker. Raises 503 once the shared daily budget is
    exhausted, so the OpenRouter credit pool can't be drained to zero."""
    cap = get_settings().global_daily_cost_limit_usd
    if cap > 0 and global_cost_today() >= cap:
        raise HTTPException(
            status_code=503,
            detail=(
                "The service has reached its shared daily usage budget. "
                "Please try again after midnight UTC."
            ),
        )


def ensure_can_generate_exam(user_id: str, email: str | None = None) -> UsageSnapshot:
    """Enforce both the per-user exam quota and the global cost breaker."""
    ensure_global_capacity()
    usage = get_usage(user_id, email)
    if usage.exams_used >= usage.exams_limit:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Daily exam limit reached ({usage.exams_used}/"
                f"{usage.exams_limit}). Your quota resets at midnight UTC."
            ),
        )
    return usage


def _increment_daily(user_id: str, *, exams: int, cost_usd: float) -> None:
    # Single atomic upsert (see migration 0006). Folding the read and write into
    # one statement prevents the lost-update race where concurrent generations
    # both read the same count and each write back +1.
    sb = get_supabase()
    sb.rpc(
        "increment_daily_usage",
        {
            "p_user_id": user_id,
            "p_exams": int(exams),
            "p_cost": max(float(cost_usd), 0.0),
        },
    ).execute()


def record_exam(user_id: str, cost_usd: float) -> None:
    """One successful exam: consume a quota credit and bill its USD cost."""
    register_user(user_id)
    _increment_daily(user_id, exams=1, cost_usd=cost_usd)


def record_cost(user_id: str, cost_usd: float) -> None:
    """Bill USD cost without consuming an exam credit (e.g. chat, or the cost of
    a failed generation attempt). Still counts toward the global breaker."""
    if cost_usd <= 0:
        return
    register_user(user_id)
    _increment_daily(user_id, exams=0, cost_usd=cost_usd)


# --- Super-admin aggregation -------------------------------------------------


def admin_user_rankings() -> list[dict]:
    """Per-user usage aggregated across all days, ranked by total USD spent."""
    sb = get_supabase()
    usage_rows = (
        sb.table("user_daily_usage")
        .select("user_id, usage_date, exam_count, cost_usd")
        .execute()
    ).data or []
    users = (
        sb.table("app_users").select("user_id, email").execute()
    ).data or []
    email_by_id = {u["user_id"]: u.get("email") for u in users}

    today = _today_utc().isoformat()
    agg: dict[str, dict] = {}
    for r in usage_rows:
        uid = r["user_id"]
        a = agg.setdefault(
            uid,
            {
                "user_id": uid,
                "email": email_by_id.get(uid),
                "exams_total": 0,
                "exams_today": 0,
                "cost_usd_total": 0.0,
                "cost_usd_today": 0.0,
            },
        )
        exams = int(r.get("exam_count") or 0)
        cost = float(r.get("cost_usd") or 0.0)
        a["exams_total"] += exams
        a["cost_usd_total"] += cost
        if r.get("usage_date") == today:
            a["exams_today"] += exams
            a["cost_usd_today"] += cost

    # Include users who registered but never generated anything yet.
    for uid, email in email_by_id.items():
        agg.setdefault(
            uid,
            {
                "user_id": uid,
                "email": email,
                "exams_total": 0,
                "exams_today": 0,
                "cost_usd_total": 0.0,
                "cost_usd_today": 0.0,
            },
        )

    ranked = sorted(agg.values(), key=lambda a: a["cost_usd_total"], reverse=True)
    return ranked


def admin_totals() -> dict:
    """Account-wide rollups for the super-admin dashboard."""
    rankings = admin_user_rankings()
    return {
        "user_count": len(rankings),
        "exams_total": sum(r["exams_total"] for r in rankings),
        "exams_today": sum(r["exams_today"] for r in rankings),
        "cost_usd_total": sum(r["cost_usd_total"] for r in rankings),
        "cost_usd_today": sum(r["cost_usd_today"] for r in rankings),
    }
