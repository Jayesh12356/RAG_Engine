import asyncio
import structlog
from app.config import get_settings
from app.db.vector_store import get_vector_store

logger = structlog.get_logger(__name__)
settings = get_settings()

async def init_vector_db():
    vs = get_vector_store()
    await vs.ensure_collection(settings.vector_collection, settings.EMBEDDING_DIM)
    logger.info(
        "vectordb.init.complete",
        provider=settings.VECTOR_DB,
        collection=settings.vector_collection,
        dim=settings.EMBEDDING_DIM
    )

if __name__ == "__main__":
    asyncio.run(init_vector_db())
