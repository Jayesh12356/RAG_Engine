"""Recreate the Qdrant collection with hybrid (dense + sparse) named vectors.

Usage:
    python scripts/migrate_qdrant_hybrid.py --confirm

After this script runs, all existing points are dropped. Re-run ingestion
on every PDF to repopulate the hybrid collection.

The script intentionally requires ``--confirm`` so it cannot be run
inadvertently against a populated production collection. It does not
back up data; combine with your usual snapshot workflow if needed.
"""
from __future__ import annotations

import argparse
import asyncio
import sys

import structlog

from app.config import get_settings
from app.db.vector_store import (
    DENSE_VECTOR_NAME,
    SPARSE_VECTOR_NAME,
    QdrantVectorStore,
)

logger = structlog.get_logger(__name__)


async def migrate(confirm: bool) -> int:
    settings = get_settings()
    if settings.VECTOR_DB != "qdrant":
        logger.error("migrate.unsupported_backend", vector_db=settings.VECTOR_DB)
        return 2
    if not confirm:
        logger.error("migrate.confirm_required")
        return 1

    store = QdrantVectorStore()
    collection = settings.vector_collection
    logger.info("migrate.start", collection=collection)

    existing = await store.client.get_collections()
    has_collection = any(c.name == collection for c in existing.collections)
    if has_collection:
        logger.warning("migrate.dropping_collection", collection=collection)
        await store.client.delete_collection(collection_name=collection)

    from qdrant_client.http.models import Distance, SparseVectorParams, VectorParams

    await store.client.create_collection(
        collection_name=collection,
        vectors_config={DENSE_VECTOR_NAME: VectorParams(size=settings.EMBEDDING_DIM, distance=Distance.COSINE)},
        sparse_vectors_config={SPARSE_VECTOR_NAME: SparseVectorParams()},
    )
    logger.info("migrate.complete", collection=collection)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Required: confirms this is a destructive operation.",
    )
    args = parser.parse_args()
    return asyncio.run(migrate(confirm=args.confirm))


if __name__ == "__main__":
    sys.exit(main())
