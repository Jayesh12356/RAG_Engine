import asyncio
import os
import structlog
import uvicorn

from scripts.init_db import init_db
from scripts.init_vector_db import init_vector_db

logger = structlog.get_logger(__name__)


async def bootstrap() -> None:
    logger.info("bootstrap.start")
    await init_db()
    await init_vector_db()
    logger.info("bootstrap.complete")


def main() -> None:
    asyncio.run(bootstrap())
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
