from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from ..auth import CurrentUser, get_current_user
from ..config import Settings, get_settings
from ..models.schemas import AdminOverviewOut, AdminUserUsage
from ..services import llm
from ..services import usage as usage_service


router = APIRouter(prefix="/api/admin", tags=["admin"])


def is_super_admin(email: str | None, settings: Settings) -> bool:
    return bool(email) and email.lower() in settings.super_admins


def require_admin(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CurrentUser:
    if not is_super_admin(user.email, settings):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super-admin access required.",
        )
    return user


@router.get(
    "/overview",
    responses={403: {"description": "Super-admin access required"}},
)
async def overview(
    _: Annotated[CurrentUser, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AdminOverviewOut:
    totals = usage_service.admin_totals()
    rankings = usage_service.admin_user_rankings()
    key = await llm.get_key_status()

    return AdminOverviewOut(
        user_count=totals["user_count"],
        exams_today=totals["exams_today"],
        exams_total=totals["exams_total"],
        cost_usd_today=round(totals["cost_usd_today"], 6),
        cost_usd_total=round(totals["cost_usd_total"], 6),
        per_user_exam_limit=settings.per_user_exam_limit,
        global_daily_cost_limit_usd=settings.global_daily_cost_limit_usd,
        account_usage_usd=None if key is None else round(key.usage_usd, 6),
        account_limit_usd=key.limit_usd if key else None,
        account_remaining_usd=key.limit_remaining_usd if key else None,
        account_is_free_tier=key.is_free_tier if key else None,
        rankings=[
            AdminUserUsage(
                user_id=r["user_id"],
                email=r["email"],
                exams_today=r["exams_today"],
                exams_total=r["exams_total"],
                cost_usd_today=round(r["cost_usd_today"], 6),
                cost_usd_total=round(r["cost_usd_total"], 6),
            )
            for r in rankings
        ],
    )
