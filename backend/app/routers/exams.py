import asyncio
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth import CurrentUser, get_current_user
from ..config import Settings, get_settings
from ..db import get_supabase
from ..models.schemas import (
    ExamContent,
    ExamOut,
    GenerateExamRequest,
    UpdateExamContentRequest,
)
from ..services import exam_generator, exporter
from ..services import usage as usage_service


router = APIRouter(prefix="/api/exams", tags=["exams"])


def _render_and_upload(
    sb,
    settings: Settings,
    *,
    user_id: str,
    exam_id: str,
    content: ExamContent,
    export_format: str,
) -> str:
    """Render the exam to the requested format, upload it, return the storage path."""
    if export_format == "docx":
        export_bytes = exporter.to_docx(content)
        ext = "docx"
        content_type = (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
    else:
        export_bytes = exporter.to_pdf(content)
        ext = "pdf"
        content_type = "application/pdf"

    export_path = f"{user_id}/{exam_id}-{uuid.uuid4().hex}.{ext}"
    try:
        sb.storage.from_(settings.exports_bucket).upload(
            export_path,
            export_bytes,
            {"content-type": content_type, "x-upsert": "true"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export upload failed: {e}") from e
    return export_path


@router.post(
    "/draft",
    responses={
        404: {"description": "Document not found"},
        500: {"description": "Could not create draft"},
    },
)
def create_draft(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    document_id: Annotated[str, Query()],
) -> ExamOut:
    """Create an empty draft exam row that the generate step then fills in."""
    sb = get_supabase()
    doc = (
        sb.table("documents")
        .select("id")
        .eq("id", document_id)
        .eq("user_id", user.id)
        .maybe_single()
        .execute()
    )
    if not doc or not doc.data:
        raise HTTPException(status_code=404, detail="Document not found")

    existing = (
        sb.table("exams")
        .select("*")
        .eq("user_id", user.id)
        .eq("document_id", document_id)
        .eq("status", "pending")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if existing.data:
        return ExamOut.model_validate(existing.data[0])

    inserted = (
        sb.table("exams")
        .insert(
            {
                "user_id": user.id,
                "document_id": document_id,
                "spec": {},
                "status": "pending",
            }
        )
        .execute()
    )
    if not inserted.data:
        raise HTTPException(status_code=500, detail="Could not create draft")
    return ExamOut.model_validate(inserted.data[0])


@router.post(
    "/{exam_id}/generate",
    responses={
        400: {"description": "Too many documents requested"},
        404: {"description": "Documents not found"},
        422: {"description": "Documents have no extracted text"},
        500: {"description": "Export upload or database update failed"},
        502: {"description": "Exam generation failed"},
        504: {"description": "Exam generation timed out"},
    },
)
async def generate(
    exam_id: str,
    body: GenerateExamRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ExamOut:
    sb = get_supabase()

    ids = list(dict.fromkeys(body.document_ids or [body.document_id]))
    if len(ids) > 5:
        raise HTTPException(status_code=400, detail="Maximum 5 documents per exam.")

    docs = (
        sb.table("documents")
        .select("id, extracted_text")
        .in_("id", ids)
        .eq("user_id", user.id)
        .execute()
    )
    if not docs or not docs.data:
        raise HTTPException(status_code=404, detail="Documents not found")

    texts = [
        (d.get("extracted_text") or "").strip()
        for d in docs.data
        if (d.get("extracted_text") or "").strip()
    ]
    if not texts:
        raise HTTPException(
            status_code=422,
            detail="Documents have no extracted text — cannot generate exam.",
        )
    course_text = "\n\n---\n\n".join(texts)

    sb.table("exams").update(
        {"spec": body.spec.model_dump(), "status": "generating"}
    ).eq("id", exam_id).eq("user_id", user.id).execute()

    usage_service.ensure_can_generate_exam(user.id, user.email)

    try:
        content = await asyncio.wait_for(
            exam_generator.generate_exam(
                user_id=user.id,
                spec=body.spec,
                course_text=course_text,
            ),
            timeout=180,
        )
    except TimeoutError as e:
        sb.table("exams").update({"status": "error"}).eq("id", exam_id).execute()
        raise HTTPException(
            status_code=504,
            detail=(
                "Exam generation timed out after 3 minutes. "
                "Try again with fewer exercises or a shorter document."
            ),
        ) from e
    except Exception as e:
        sb.table("exams").update({"status": "error"}).eq("id", exam_id).execute()
        raise HTTPException(status_code=502, detail=f"Generation failed: {e}") from e

    export_path = _render_and_upload(
        sb,
        settings,
        user_id=user.id,
        exam_id=exam_id,
        content=content,
        export_format=body.spec.export_format,
    )

    updated = (
        sb.table("exams")
        .update(
            {
                "title": content.title,
                "content": content.model_dump(),
                "export_format": body.spec.export_format,
                "export_path": export_path,
                "status": "ready",
            }
        )
        .eq("id", exam_id)
        .eq("user_id", user.id)
        .execute()
    )
    if not updated.data:
        raise HTTPException(status_code=500, detail="Update failed")
    return ExamOut.model_validate(updated.data[0])


@router.put(
    "/{exam_id}/content",
    responses={
        404: {"description": "Exam not found"},
        500: {"description": "Export upload or database update failed"},
    },
)
def update_content(
    exam_id: str,
    body: UpdateExamContentRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ExamOut:
    """Save user edits to a generated exam (title, questions, per-exercise
    grading) and re-render the downloadable export. Does not consume an exam
    credit — editing is free."""
    sb = get_supabase()
    existing = (
        sb.table("exams")
        .select("export_format")
        .eq("id", exam_id)
        .eq("user_id", user.id)
        .maybe_single()
        .execute()
    )
    if not existing or not existing.data:
        raise HTTPException(status_code=404, detail="Exam not found")

    content: ExamContent = body.to_content()
    export_format = (
        body.export_format
        or existing.data.get("export_format")
        or "pdf"
    )

    export_path = _render_and_upload(
        sb,
        settings,
        user_id=user.id,
        exam_id=exam_id,
        content=content,
        export_format=export_format,
    )

    updated = (
        sb.table("exams")
        .update(
            {
                "title": content.title,
                "content": content.model_dump(),
                "export_format": export_format,
                "export_path": export_path,
                "status": "ready",
            }
        )
        .eq("id", exam_id)
        .eq("user_id", user.id)
        .execute()
    )
    if not updated.data:
        raise HTTPException(status_code=500, detail="Update failed")
    return ExamOut.model_validate(updated.data[0])


@router.get(
    "/{exam_id}/download",
    responses={
        404: {"description": "Export not ready"},
        500: {"description": "Could not sign the download URL"},
    },
)
def download_url(
    exam_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[Literal["url"], str]:
    sb = get_supabase()
    row = (
        sb.table("exams")
        .select("export_path")
        .eq("id", exam_id)
        .eq("user_id", user.id)
        .maybe_single()
        .execute()
    )
    if not row.data or not row.data.get("export_path"):
        raise HTTPException(status_code=404, detail="Export not ready")
    signed = sb.storage.from_(settings.exports_bucket).create_signed_url(
        row.data["export_path"], 3600
    )
    url = signed.get("signedURL") or signed.get("signed_url")
    if not url:
        raise HTTPException(status_code=500, detail="Could not sign URL")
    return {"url": url}
