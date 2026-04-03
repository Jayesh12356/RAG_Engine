import uuid
from typing import Dict, List, Optional
from pydantic import BaseModel
from datetime import datetime, timezone
from app.db import relational
from app.config import get_settings

class HistoryTurn(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    confidence: Optional[float] = None
    service_category: Optional[str] = None
    sources: List[dict] = []
    created_at: str

class SessionManager:
    _memory_store: Dict[str, List[dict]] = {}

    def __init__(self, demo_mode: bool = False):
        self.demo_mode = demo_mode
        
    async def create_session(self) -> str:
        session_id = str(uuid.uuid4())
        if self.demo_mode:
            self._memory_store[session_id] = []
        return session_id

    async def add_turn(self, session_id: str, role: str, content: str, 
                       question: Optional[str] = None, answer: Optional[str] = None, 
                       confidence: Optional[float] = None, sources: Optional[List[dict]] = None, 
                       service_category: Optional[str] = None) -> str:
        if self.demo_mode:
            turn_id = str(uuid.uuid4())
            if session_id not in self._memory_store:
                self._memory_store[session_id] = []
            turn = {
                "id": turn_id,
                "session_id": session_id,
                "role": role,
                "content": content,
                "question": question,
                "answer": answer,
                "confidence": confidence,
                "sources": sources or [],
                "service_category": service_category,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            self._memory_store[session_id].append(turn)
            return turn_id
        else:
            return await relational.insert_turn(
                session_id=session_id,
                role=role,
                content=content,
                question=question,
                answer=answer,
                confidence=confidence,
                sources=sources,
                service_category=service_category
            )

    async def get_history(self, session_id: str, limit: int = 5) -> List[HistoryTurn]:
        if self.demo_mode:
            turns = self._memory_store.get(session_id, [])
            sliced = turns[-limit:] if limit > 0 else turns
            history = []
            for t in sliced:
                history.append(HistoryTurn(
                    id=t["id"],
                    session_id=t["session_id"],
                    role=t["role"],
                    content=t["content"],
                    confidence=t.get("confidence"),
                    service_category=t.get("service_category"),
                    sources=t.get("sources") or [],
                    created_at=str(t.get("created_at", ""))
                ))
            return history
        else:
            turns = await relational.get_history(session_id, limit=limit)
            history = []
            for t in turns:
                history.append(HistoryTurn(
                    id=t["id"],
                    session_id=t["session_id"],
                    role=t["role"],
                    content=t["content"],
                    confidence=t.get("confidence"),
                    service_category=t.get("service_category"),
                    sources=t.get("sources") or [],
                    created_at=str(t.get("created_at", ""))
                ))
            return history
