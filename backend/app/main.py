from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.db.database import init_db
from app.exceptions import AppError
from app.routers import chat, conversations, memory, settings as settings_router
from app.utils.logger import setup_logging, get_logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger = get_logger("app")
    logger.info("starting_up", port=settings.port, llm_provider=settings.llm_provider.value)

    init_db()
    logger.info("database_initialized")

    yield

    logger.info("shutting_down")


app = FastAPI(
    title="Smart Memory Agent",
    description="AI agent with three-tier memory: short-term, long-term (vector), and entity memory",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.message},
    )


# Register routers
app.include_router(chat.router)
app.include_router(conversations.router)
app.include_router(memory.router)
app.include_router(settings_router.router)


@app.get("/")
def root():
    return {
        "name": "Smart Memory Agent",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {"status": "ok"}
