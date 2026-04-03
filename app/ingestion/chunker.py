import uuid
import structlog
from pydantic import BaseModel
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.ingestion.pdf_parser import ParsedPage
from app.config import get_settings

logger = structlog.get_logger()

class ChunkData(BaseModel):
    chunk_id: str
    text: str
    pdf_name: str
    service_name: str
    section_title: str
    page_number: int
    chunk_index: int
    total_pages: int

def chunk_pages(pages: list[ParsedPage]) -> list[ChunkData]:
    settings = get_settings()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP
    )
    
    chunks = []
    
    for page in pages:
        # We split the page text into logical blocks first (split by raw double newlines)
        page_blocks = page.text.split("\n\n")
        
        page_chunks = []
        for block in page_blocks:
            if not block.strip():
                continue
                
            lines = block.split('\n')
            
            # Table detection: >=2 lines containing >=2 pipe chars (|) or >=2 tab chars
            table_lines = 0
            for line in lines:
                if line.count('|') >= 2 or line.count('\t') >= 2:
                    table_lines += 1
                    
            # Ordered list detection: >= 3 lines starting with digit + period
            import re
            list_lines = 0
            for line in lines:
                if re.match(r'^\s*\d+\.\s', line):
                    list_lines += 1
            
            if table_lines >= 2 or list_lines >= 3:
                # Keep table or list whole (up to 2x chunk size max to prevent massive chunks)
                if len(block) <= settings.CHUNK_SIZE * 2:
                    page_chunks.append(block.strip())
                    continue
            
            # Split normal text
            split_texts = splitter.split_text(block)
            page_chunks.extend(split_texts)
                
        for i, text in enumerate(page_chunks):
            if not text.strip():
                continue
            chunks.append(ChunkData(
                chunk_id=str(uuid.uuid4()),
                text=text.strip(),
                pdf_name=page.pdf_name,
                service_name=page.service_name,
                section_title=page.section_title,
                page_number=page.page_number,
                chunk_index=i,
                total_pages=page.total_pages
            ))
            
    return chunks
