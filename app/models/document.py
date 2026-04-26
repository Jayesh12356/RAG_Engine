from typing import Any

from pydantic import BaseModel, Field


class Chunk(BaseModel):
    id: str
    document_id: str
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    
class Document(BaseModel):
    id: str
    filename: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    chunks: list[Chunk] = Field(default_factory=list)
