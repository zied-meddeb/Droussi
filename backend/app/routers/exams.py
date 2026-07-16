import asyncio
import logging
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool

from ..auth import CurrentUser, get_current_user
from ..config import Settings, get_settings
from ..db import get_supabase
from ..rate_limit import limiter
from ..models.schemas import (
    ExamContent,
    ExamOut,
    GenerateExamRequest,
    UpdateExamContentRequest,
)
from ..services import exam_generator, exporter, jobs
from ..services import usage as usage_service
from ..models.schemas import ExamSpec


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/exams", tags=["exams"])


async def _mark_exam_error(sb, exam_id: str, user_id: str) -> None:
    """Set an exam to the error state, scoped to its owner, off the event loop."""
    await run_in_threadpool(
        lambda: sb.table("exams")
        .update({"status": "error"})
        .eq("id", exam_id)
        .eq("user_id", user_id)
        .execute()
    )


async def _run_generation_job(
    sb,
    settings: Settings,
    *,
    user_id: str,
    exam_id: str,
    spec: ExamSpec,
    course_text: str,
) -> None:
    """Background body for asynchronous generation: produce the exam, render the
    export, and persist a ready row. On any failure the exam is marked 'error'.
    Never raises — it runs detached from the request, so the outcome lives only
    in the exam row's status."""
    try:
        content = await asyncio.wait_for(
            exam_generator.generate_exam(
                user_id=user_id, spec=spec, course_text=course_text
            ),
            timeout=180,
        )
        export_path = await run_in_threadpool(
            _render_and_upload,
            sb,
            settings,
            user_id=user_id,
            exam_id=exam_id,
            content=content,
            export_format=spec.export_format,
        )
        await run_in_threadpool(
            lambda: sb.table("exams")
            .update(
                {
                    "title": content.title,
                    "content": content.model_dump(),
                    "export_format": spec.export_format,
                    "export_path": export_path,
                    "status": "ready",
                }
            )
            .eq("id", exam_id)
            .eq("user_id", user_id)
            .execute()
        )
    except Exception:
        logger.exception("Async exam generation failed for exam %s", exam_id)
        await _mark_exam_error(sb, exam_id, user_id)


def _render_and_upload(
    sb,
    settings: Settings,
    *,
    user_id: str,
    exam_id: str,
    content: ExamContent,
    export_format: str,
    stable: bool = False,
) -> str:
    """Render the exam to the requested format, upload it, return the storage path.

    When ``stable`` is set the file is stored at a fixed per-exam-per-format path
    (and upserted), so on-demand downloads of a format don't accumulate a new
    object on every click.
    """
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

    export_path = (
        f"{user_id}/{exam_id}.{ext}"
        if stable
        else f"{user_id}/{exam_id}-{uuid.uuid4().hex}.{ext}"
    )
    try:
        sb.storage.from_(settings.exports_bucket).upload(
            export_path,
            export_bytes,
            {"content-type": content_type, "x-upsert": "true"},
        )
    except Exception as e:
        logger.exception("Export upload failed for %s", export_path)
        raise HTTPException(status_code=500, detail="Export upload failed.") from e
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


async def _prepare_generation(
    sb, *, exam_id: str, body: GenerateExamRequest, user: CurrentUser
) -> str:
    """Validate ownership, quota, and documents, then mark the exam
    'generating'. Returns the concatenated course text. Raises HTTPException on
    any precondition failure. Shared by the sync and async generate endpoints.

    The Supabase client is synchronous, so every call is offloaded to a
    threadpool to keep the event loop free.
    """
    ids = list(dict.fromkeys(body.document_ids or [body.document_id]))
    if len(ids) > 5:
        raise HTTPException(status_code=400, detail="Maximum 5 documents per exam.")

    # Verify the exam belongs to the caller before doing any expensive work.
    # The service-role client bypasses RLS, so without this an attacker could
    # target another user's exam id and (via the failure paths below) flip its
    # status, as well as burn OpenRouter budget/quota on a foreign exam.
    owned = await run_in_threadpool(
        lambda: sb.table("exams")
        .select("id")
        .eq("id", exam_id)
        .eq("user_id", user.id)
        .maybe_single()
        .execute()
    )
    if not owned or not owned.data:
        raise HTTPException(status_code=404, detail="Exam not found")

    # Short-circuit on quota / global budget before loading documents or calling
    # the LLM, so a user who is already over the limit can't force expensive work.
    await run_in_threadpool(
        usage_service.ensure_can_generate_exam, user.id, user.email
    )

    docs = await run_in_threadpool(
        lambda: sb.table("documents")
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

    await run_in_threadpool(
        lambda: sb.table("exams")
        .update({"spec": body.spec.model_dump(), "status": "generating"})
        .eq("id", exam_id)
        .eq("user_id", user.id)
        .execute()
    )
    return "\n\n---\n\n".join(texts)


@router.post(
    "/{exam_id}/generate-async",
    status_code=202,
    responses={
        400: {"description": "Too many documents requested"},
        404: {"description": "Exam or documents not found"},
        422: {"description": "Documents have no extracted text"},
        429: {"description": "Daily quota reached"},
        503: {"description": "Shared daily budget exhausted"},
    },
)
@limiter.limit("10/minute")
async def generate_async(
    request: Request,
    exam_id: str,
    body: GenerateExamRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ExamOut:
    """Kick off generation in the background and return immediately with the
    exam in the 'generating' state. Clients poll ``GET /api/exams/{exam_id}``
    until the status becomes 'ready' or 'error'. This decouples the long LLM
    call from the HTTP request lifecycle (no multi-minute request holds)."""
    sb = get_supabase()
    course_text = await _prepare_generation(
        sb, exam_id=exam_id, body=body, user=user
    )

    jobs.spawn(
        _run_generation_job(
            sb,
            settings,
            user_id=user.id,
            exam_id=exam_id,
            spec=body.spec,
            course_text=course_text,
        )
    )

    row = await run_in_threadpool(
        lambda: sb.table("exams")
        .select("*")
        .eq("id", exam_id)
        .eq("user_id", user.id)
        .maybe_single()
        .execute()
    )
    if not row or not row.data:
        raise HTTPException(status_code=404, detail="Exam not found")
    return ExamOut.model_validate(row.data)


@router.get(
    "/{exam_id}",
    responses={404: {"description": "Exam not found"}},
)
async def get_exam(
    exam_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> ExamOut:
    """Return the current state of an exam (status + content once ready). Used
    to poll the progress of an asynchronous generation."""
    sb = get_supabase()
    row = await run_in_threadpool(
        lambda: sb.table("exams")
        .select("*")
        .eq("id", exam_id)
        .eq("user_id", user.id)
        .maybe_single()
        .execute()
    )
    if not row or not row.data:
        raise HTTPException(status_code=404, detail="Exam not found")
    return ExamOut.model_validate(row.data)


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
@limiter.limit("10/minute")
async def generate(
    request: Request,
    exam_id: str,
    body: GenerateExamRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ExamOut:
    sb = get_supabase()
    course_text = await _prepare_generation(
        sb, exam_id=exam_id, body=body, user=user
    )

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
        await _mark_exam_error(sb, exam_id, user.id)
        raise HTTPException(
            status_code=504,
            detail=(
                "Exam generation timed out after 3 minutes. "
                "Try again with fewer exercises or a shorter document."
            ),
        ) from e
    except Exception as e:
        await _mark_exam_error(sb, exam_id, user.id)
        logger.exception("Exam generation failed for exam %s", exam_id)
        raise HTTPException(
            status_code=502, detail="Exam generation failed."
        ) from e

    export_path = await run_in_threadpool(
        _render_and_upload,
        sb,
        settings,
        user_id=user.id,
        exam_id=exam_id,
        content=content,
        export_format=body.spec.export_format,
    )

    updated = await run_in_threadpool(
        lambda: sb.table("exams")
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
        404: {"description": "Export not ready / format unavailable"},
        500: {"description": "Could not sign the download URL"},
    },
)
def download_url(
    exam_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
    export_format: Annotated[Literal["pdf", "docx"] | None, Query(alias="format")] = None,
) -> dict[Literal["url"], str]:
    """Return a signed URL for the exam in the requested format.

    The format defaults to the one chosen at generation. Any other format is
    rendered on the fly from the exam's saved content, so both PDF and DOCX are
    always available without regenerating the exam.
    """
    sb = get_supabase()
    row = (
        sb.table("exams")
        .select("content, export_format, export_path")
        .eq("id", exam_id)
        .eq("user_id", user.id)
        .maybe_single()
        .execute()
    )
    if not row.data:
        raise HTTPException(status_code=404, detail="Exam not found")

    data = row.data
    stored_format = data.get("export_format") or "pdf"
    fmt = export_format or stored_format

    if fmt == stored_format and data.get("export_path"):
        # The format rendered at generation — reuse the stored file.
        export_path = data["export_path"]
    elif data.get("content"):
        # A different format — render it now from the saved exam content.
        content = ExamContent.model_validate(data["content"])
        export_path = _render_and_upload(
            sb,
            settings,
            user_id=user.id,
            exam_id=exam_id,
            content=content,
            export_format=fmt,
            stable=True,
        )
    else:
        raise HTTPException(
            status_code=404,
            detail=f"{fmt.upper()} export isn't available for this exam.",
        )

    signed = sb.storage.from_(settings.exports_bucket).create_signed_url(
        export_path, 3600
    )
    url = signed.get("signedURL") or signed.get("signed_url")
    if not url:
        raise HTTPException(status_code=500, detail="Could not sign URL")
    return {"url": url}
