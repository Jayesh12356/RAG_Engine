from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

class Chunk(BaseModel):
    id: str
    document_id: str
    text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
class Document(BaseModel):
    id: str
    filename: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    chunks: List[Chunk] = Field(default_factory=list)
