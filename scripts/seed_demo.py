import asyncio
import structlog
from pathlib import Path
from app.ingestion.pipeline import IngestPipeline

logger = structlog.get_logger(__name__)

async def seed_demo():
    pdf_path = Path("data/sample_pdfs/VPN_Setup_Guide.pdf")
    if not pdf_path.exists():
        logger.error("demo.seed.failed", error=f"File not found: {pdf_path}")
        return
    
    try:
        logger.info("demo.seed.start", file=pdf_path.name)
        pipeline = IngestPipeline(demo_mode=False)
        result = await pipeline.run(str(pdf_path))
        logger.info("demo.seed.success", result=result.model_dump())
    except Exception as e:
        logger.warning("demo.seed.real_failed", error=str(e), fallback="demo_mode=True")
        pipeline = IngestPipeline(demo_mode=True)
        result = await pipeline.run(str(pdf_path))
        logger.info("demo.seed.success", result=result.model_dump(), mode="demo")

if __name__ == "__main__":
    asyncio.run(seed_demo())
