import asyncio
import sys
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings

logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    
    provider = settings.LLM_PROVIDER
    if provider == "groq":
        model = settings.GROQ_MODEL
    elif provider == "openrouter":
        model = settings.OPENROUTER_MODEL
    else:
        model = settings.OPENAI_MODEL
        
    logger.info(
        "llm.provider.active",
        provider=provider,
        model=model,
        embed_provider=settings.EMBEDDING_PROVIDER
    )
    yield

def create_app() -> FastAPI:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    app = FastAPI(title="IT-HELPDESK-RAG", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from app.api.routes import router as api_router
    app.include_router(api_router)

    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

