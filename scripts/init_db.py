import asyncio
import structlog
from app.config import get_settings
from app.db.relational import init_db as relational_init_db

logger = structlog.get_logger(__name__)
settings = get_settings()

async def init_db():
    await relational_init_db()
    logger.info(
        "db.init.complete", 
        provider=settings.RELATIONAL_DB, 
        schema=settings.db_schema,
        tables=["documents", "chunks", "conversation_history"]
    )

if __name__ == "__main__":
    asyncio.run(init_db())
