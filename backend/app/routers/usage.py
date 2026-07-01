from typing import Annotated

from fastapi import APIRouter, Depends

from ..auth import CurrentUser, get_current_user
from ..models.schemas import UsageOut
from ..services import usage as usage_service


router = APIRouter(prefix="/api/usage", tags=["usage"])


@router.get("")
def get_daily_usage(
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> UsageOut:
    snapshot = usage_service.get_usage(user.id, user.email)
    return UsageOut(
        exams_used=snapshot.exams_used,
        exams_limit=snapshot.exams_limit,
        remaining=snapshot.remaining,
        percent=round(snapshot.percent, 1),
        cost_usd_today=round(snapshot.cost_usd_today, 6),
        usage_date=snapshot.usage_date.isoformat(),
        resets_at=snapshot.resets_at.isoformat(),
    )
