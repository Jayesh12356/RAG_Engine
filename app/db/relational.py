from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, String, Text, DateTime, JSON, Float, func, select, delete
from app.config import get_settings
import uuid

Base = declarative_base()

class DocumentModel(Base):
    __tablename__ = "documents"
    id = Column(String(255), primary_key=True)
    filename = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    metadata_ = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime, nullable=True)

class ChunkModel(Base):
    __tablename__ = "chunks"
    id = Column(String(255), primary_key=True)
    document_id = Column(String(255), nullable=False)
    text = Column(Text, nullable=False)
    metadata_ = Column("metadata", JSON, nullable=True)

class ConversationHistoryModel(Base):
    __tablename__ = "conversation_history"
    id = Column(String(36), primary_key=True)
    session_id = Column(String(36), nullable=False, index=True)
    role = Column(String(16), nullable=False)
    content = Column(Text, nullable=False)
    question = Column(Text, nullable=True)
    answer = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    sources = Column(JSON, nullable=True)
    service_category = Column(String(64), nullable=True)
    created_at = Column(DateTime, nullable=False, default=func.now())

async def insert_turn(session_id: str, role: str, content: str, question: str = None, answer: str = None, 
                      confidence: float = None, sources: list = None, service_category: str = None) -> str:
    turn_id = str(uuid.uuid4())
    async with get_session_maker()() as session:
        turn = ConversationHistoryModel(
            id=turn_id,
            session_id=session_id,
            role=role,
            content=content,
            question=question,
            answer=answer,
            confidence=confidence,
            sources=sources,
            service_category=service_category
        )
        session.add(turn)
        await session.commit()
    return turn_id

async def get_history(session_id: str, limit: int = 50) -> list[dict]:
    async with get_session_maker()() as session:
        stmt = select(ConversationHistoryModel)\
            .where(ConversationHistoryModel.session_id == session_id)\
            .order_by(ConversationHistoryModel.created_at.desc())\
            .limit(limit)
        result = await session.execute(stmt)
        turns = result.scalars().all()
        
        history = []
        for t in reversed(turns):
            history.append({
                "id": t.id,
                "session_id": t.session_id,
                "role": t.role,
                "content": t.content,
                "confidence": t.confidence,
                "service_category": t.service_category,
                "sources": t.sources or [],
                "created_at": t.created_at.isoformat() if t.created_at else ""
            })
        return history

async def get_sessions() -> list[dict]:
    async with get_session_maker()() as session:
        # Get count and latest activity per session
        stmt = select(
            ConversationHistoryModel.session_id,
            func.count(ConversationHistoryModel.id).label("turn_count"),
            func.max(ConversationHistoryModel.created_at).label("last_active")
        ).group_by(ConversationHistoryModel.session_id).order_by(func.max(ConversationHistoryModel.created_at).desc())
        
        result = await session.execute(stmt)
        sessions_aggs = result.all()
        
        sessions = []
        for s in sessions_aggs:
            # get the first question
            first_q_stmt = select(ConversationHistoryModel.content)\
                .where(ConversationHistoryModel.session_id == s.session_id, ConversationHistoryModel.role == "user")\
                .order_by(ConversationHistoryModel.created_at.asc())\
                .limit(1)
            first_q_res = await session.execute(first_q_stmt)
            first_q = first_q_res.scalar_one_or_none()
            
            sessions.append({
                "session_id": s.session_id,
                "turn_count": s.turn_count,
                "last_active": s.last_active.isoformat() if s.last_active else "",
                "first_question": first_q or ""
            })
        return sessions

async def delete_session(session_id: str) -> int:
    async with get_session_maker()() as session:
        stmt = delete(ConversationHistoryModel).where(ConversationHistoryModel.session_id == session_id)
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount

def get_engine():
    settings = get_settings()
    if settings.RELATIONAL_DB == "mysql":
        return create_async_engine(settings.MYSQL_URL, echo=False)
    else:
        return create_async_engine(settings.POSTGRES_URL, echo=False)

async def init_db():
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

def get_session_maker():
    engine = get_engine()
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
