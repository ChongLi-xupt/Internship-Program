"""
Document Ingestion Service — async background processing pipeline.

Pipeline: Parse → Chunk → Embed → Store
Each step is modular and pluggable via the ingestors package.
"""

import uuid
import logging
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.ingestors.base import BaseParser
from app.ingestors.pdf_parser import PDFParser
from app.ingestors.docx_parser import DocxParser
from app.ingestors.html_parser import HTMLParser
from app.ingestors.markdown_parser import MarkdownParser
from app.ingestors.excel_parser import ExcelParser
from app.ingestors.chunker import TextChunker
from app.llm.base import get_embedding_provider

logger = logging.getLogger(__name__)

# File type → parser mapping
PARSER_MAP = {
    "pdf": PDFParser,
    "docx": DocxParser,
    "html": HTMLParser,
    "md": MarkdownParser,
    "xlsx": ExcelParser,
    "txt": MarkdownParser,  # Plain text uses markdown parser (it handles raw text fine)
}


async def process_document_async(
    document_id: str,
    kb_id: str,
    file_path: str,
    file_type: str,
):
    """
    Background task: process an uploaded document through the full ingestion pipeline.
    Called from FastAPI BackgroundTasks or Celery.
    """
    from app.database import get_async_session

    async with get_async_session() as db:
        try:
            doc_uuid = uuid.UUID(document_id)
            kb_uuid = uuid.UUID(kb_id)

            # Step 1: Update status to parsing
            await _update_doc_status(db, doc_uuid, "parsing")

            # Step 2: Parse document
            parser_cls = PARSER_MAP.get(file_type)
            if not parser_cls:
                raise ValueError(f"Unsupported file type: {file_type}")

            parser = parser_cls()
            parse_result = await parser.parse(file_path)

            # Step 3: Update status to chunking
            await _update_doc_status(db, doc_uuid, "chunking")

            # Step 4: Chunk the parsed text
            chunker = TextChunker(chunk_size=512, overlap=50)
            chunks = chunker.chunk(parse_result["text"], metadata=parse_result.get("metadata", {}))

            if not chunks:
                raise ValueError("Document produced no chunks after parsing")

            # Step 5: Update status to embedding
            await _update_doc_status(db, doc_uuid, "embedding")

            # Step 6: Generate embeddings
            embedder = get_embedding_provider()
            texts = [c["content"] for c in chunks]
            embedding_vectors = await embedder.embed_documents(texts)

            # Step 7: Store in vector DB + PostgreSQL
            from app.vector.base import get_vector_store
            from app.models.knowledge import Chunk as ChunkModel

            store = get_vector_store()
            collection_name = f"kb_{kb_id}"

            ids = []
            payloads = []
            chunk_records = []

            for i, (chunk, vector) in enumerate(zip(chunks, embedding_vectors)):
                chunk_id = f"{doc_uuid}_{i}"
                ids.append(chunk_id)
                payloads.append({
                    "content": chunk["content"],
                    "document_id": str(doc_uuid),
                    "kb_id": str(kb_uuid),
                    "tenant_id": "",  # Will be filled by middleware in production
                    "chunk_index": i,
                    "metadata": chunk.get("metadata", {}),
                    **chunk.get("metadata", {}),
                })

                chunk_records.append(ChunkModel(
                    document_id=doc_uuid,
                    kb_id=kb_uuid,
                    tenant_id=kb_uuid,  # Simplified — should use actual tenant
                    content=chunk["content"],
                    chunk_index=i,
                    token_count=chunk.get("token_count"),
                    metadata_json=chunk.get("metadata", {}),
                ))

            # Upsert vectors
            await store.upsert(collection_name, ids, embedding_vectors, payloads)

            # Save chunk records to Postgres
            db.add_all(chunk_records)

            # Step 8: Mark complete
            await _update_doc_status(db, doc_uuid, "completed", chunk_count=len(chunks))

            # Update KB stats
            from app.models.knowledge_base import KnowledgeBase
            kb_result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_uuid))
            kb = kb_result.scalar_one_or_none()
            if kb:
                kb.chunk_count += len(chunks)
                kb.status = "ready"

            await db.commit()
            logger.info(f"Document {document_id} processed successfully: {len(chunks)} chunks")

        except Exception as e:
            logger.error(f"Document {document_id} processing failed: {e}", exc_info=True)
            try:
                async with get_async_session() as db:
                    await _update_doc_status(
                        db, uuid.UUID(document_id), "failed",
                        parse_error=str(e)[:1000],
                    )
                    await db.commit()
            except Exception:
                pass


async def _update_doc_status(
    db: AsyncSession,
    doc_id: uuid.UUID,
    status: str,
    *,
    chunk_count: int | None = None,
    parse_error: str | None = None,
):
    """Update document processing status."""
    from app.models.knowledge import Document

    values: dict = {"parse_status": status}
    if chunk_count is not None:
        values["chunk_count"] = chunk_count
    if parse_error is not None:
        values["parse_error"] = parse_error

    await db.execute(
        update(Document).where(Document.id == doc_id).values(**values)
    )
    await db.flush()
