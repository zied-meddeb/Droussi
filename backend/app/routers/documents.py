from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from ..auth import CurrentUser, get_current_user
from ..config import Settings, get_settings
from ..db import get_supabase
from ..models.schemas import DocumentOut, RegisterDocumentRequest
from ..services.pdf_parser import extract_text


router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post(
    "/register",
    responses={
        403: {"description": "Storage path does not belong to the user"},
        400: {"description": "Could not read the uploaded file"},
        422: {"description": "Could not parse the document"},
        500: {"description": "Database insert failed"},
    },
)
def register_document(
    body: RegisterDocumentRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DocumentOut:
    sb = get_supabase()

    user_prefix = f"{user.id}/"
    if not body.storage_path.startswith(user_prefix):
        raise HTTPException(
            status_code=403,
            detail="Storage path must belong to the authenticated user.",
        )

    # Pull bytes from storage so we can extract text now.
    try:
        file_bytes = sb.storage.from_(settings.documents_bucket).download(
            body.storage_path
        )
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Could not read uploaded file: {e}"
        ) from e

    try:
        text = extract_text(file_bytes, body.mime_type)
    except Exception as e:
        raise HTTPException(
            status_code=422, detail=f"Could not parse document: {e}"
        ) from e

    inserted = (
        sb.table("documents")
        .insert(
            {
                "user_id": user.id,
                "filename": body.filename,
                "storage_path": body.storage_path,
                "mime_type": body.mime_type,
                "size_bytes": body.size_bytes,
                "extracted_text": text,
            }
        )
        .execute()
    )
    if not inserted.data:
        raise HTTPException(status_code=500, detail="Insert failed")
    return DocumentOut.model_validate(inserted.data[0])


@router.delete(
    "/{doc_id}",
    status_code=204,
    responses={404: {"description": "Document not found"}},
)
def delete_document(
    doc_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    sb = get_supabase()
    row = (
        sb.table("documents")
        .select("storage_path")
        .eq("id", doc_id)
        .eq("user_id", user.id)
        .single()
        .execute()
    )
    if not row.data:
        raise HTTPException(status_code=404, detail="Not found")
    try:
        sb.storage.from_(settings.documents_bucket).remove([row.data["storage_path"]])
    except Exception:
        pass
    sb.table("documents").delete().eq("id", doc_id).eq("user_id", user.id).execute()
