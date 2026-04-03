import asyncio
import structlog
from pathlib import Path
from app.ingestion.pipeline import IngestPipeline

async def ingest():
    pdf_path = Path("data/sample_pdfs/VirtualPrivateNetwork.pdf")
    pipeline = IngestPipeline(demo_mode=False)
    result = await pipeline.run(str(pdf_path), "VPN")
    print(result)

if __name__ == "__main__":
    asyncio.run(ingest())
