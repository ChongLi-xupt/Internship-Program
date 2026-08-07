"""Document upload / ingestion API routes."""

import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.rbac import Permission
from app.dependencies import get_db, get_current_active_user, require_permissions
from app.models.knowledge import Document, DocumentFileType, KnowledgeBase
from app.schemas.knowledge import DocumentUploadResponse, DocumentResponse, DocumentListParams
from app.services.ingestion_service import process_document_async

router = APIRouter()


def _ensure_storage_dir():
    """Ensure local file storage directory exists."""
    path = Path(settings.local_storage_path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _get_file_type(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    mapping = {
        "pdf": "pdf",
        "docx": "docx",
        "doc": "docx",
        "html": "html",
        "htm": "html",
        "md": "md",
        "markdown": "md",
        "xlsx": "xlsx",
        "xls": "xlsx",
        "txt": "txt",
    }
    return mapping.get(ext, "txt")


@router.post("/knowledge-bases/{kb_id}/documents/upload", response_model=list[DocumentUploadResponse])
async def upload_documents(
    kb_id: uuid.UUID,
    files: list[UploadFile] = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user=Depends(require_permissions(Permission.DOC_UPLOAD.value)),
    db: AsyncSession = Depends(get_db),
):
    """Upload one or more documents to a knowledge base. Processing happens async."""
    # Verify KB exists and belongs to tenant
    result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
    kb = result.scalar_one_or_none()
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")

    storage_dir = _ensure_storage_dir()
    responses = []

    for file in files:
        # Validate file
        if not file.filename:
            continue

        file_type = _get_file_type(file.filename)
        content = await file.read()
        file_size = len(content)

        # Save to storage
        doc_uuid = str(uuid.uuid4())
        safe_name = f"{doc_uuid}_{file.filename}"
        file_path = str(storage_dir / safe_name)

        with open(file_path, "wb") as f:
            f.write(content)

        # Create document record
        document = Document(
            kb_id=kb_id,
            tenant_id=kb.tenant_id,
            title=file.filename.rsplit(".", 1)[0] if "." in file.filename else file.filename,
            file_name=file.filename,
            file_type=file_type,
            file_size=file_size,
            file_path=file_path,
            parse_status="pending",
            created_by=current_user.id,
        )
        db.add(document)
        await db.flush()

        responses.append(DocumentUploadResponse(
            document_id=document.id,
            file_name=file.filename,
            status="parsing",
        ))

        # Trigger async processing
        background_tasks.add_task(process_document_async, str(document.id), str(kb_id), file_path, file_type)

    # Update KB doc count
    kb.doc_count += len(files)
    await db.commit()

    return responses


@router.get("/knowledge-bases/{kb_id}/documents", response_model=list[DocumentResponse])
async def list_documents(
    kb_id: uuid.UUID,
    params: DocumentListParams = Depends(),
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import func

    query = select(Document).where(Document.kb_id == kb_id)
    count_q = select(func.count()).select_from(query.subquery())

    if params.status:
        query = query.where(Document.parse_status == params.status)
    if params.search:
        query = query.where(Document.file_name.ilike(f"%{params.search}%"))

    total = (await db.execute(count_q)).scalar()
    result = await db.execute(
        query.order_by(Document.created_at.desc())
        .offset((params.page - 1) * params.page_size)
        .limit(params.page_size)
    )
    docs = result.scalars().all()

    return [DocumentResponse.model_validate(d) for d in docs]


@router.get("/documents/{doc_id}", response_model=DocumentResponse)
async def get_document(
    doc_id: uuid.UUID,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    return DocumentResponse.model_validate(doc)


@router.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: uuid.UUID,
    _=Depends(require_permissions(Permission.DOC_DELETE.value)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    # Clean up vectors
    try:
        from app.vector.base import get_vector_store
        store = get_vector_store()
        await store.delete(collection_name=f"kb_{doc.kb_id}", filter_dict={"document_id": str(doc_id)})
    except Exception:
        pass

    # Clean up file
    if doc.file_path and os.path.exists(doc.file_path):
        os.remove(doc.file_path)

    await db.delete(doc)
    await db.commit()
    return {"message": "文档已删除"}
