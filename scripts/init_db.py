import asyncio
import structlog
from app.config import get_settings
from app.db.relational import Base, get_engine

logger = structlog.get_logger(__name__)
settings = get_settings()

async def init_db():
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info(
        "db.init.complete", 
        provider=settings.RELATIONAL_DB, 
        tables=["documents", "chunks", "conversation_history"]
    )

if __name__ == "__main__":
    asyncio.run(init_db())
