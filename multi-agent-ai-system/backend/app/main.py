from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging

from app.config import settings
from app.database import init_db
from app.routers import workflows, runs, logs, auth, history

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic"""
    # Startup
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    init_db()
    
    # Start Shadow Agent
    from app.agents.shadow_agent import shadow_agent
    await shadow_agent.start()
    
    yield
    
    # Shutdown
    await shadow_agent.stop()
    from app.queue.producer import close_connection
    await close_connection()
    logger.info("Shutting down application")

app = FastAPI(
    title=settings.APP_NAME,
    description="Multi-agent AI workflow orchestration using LangGraph and Groq",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global error handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error": str(exc) if settings.DEBUG else "An error occurred"
        },
    )

# Health check
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT
    }

# Include API routers
app.include_router(
    workflows.router,
    prefix=f"{settings.API_V1_PREFIX}/workflows",
    tags=["workflows"],
)
app.include_router(
    runs.router,
    prefix=f"{settings.API_V1_PREFIX}/runs",
    tags=["runs"],
)
app.include_router(
    logs.router,
    prefix=f"{settings.API_V1_PREFIX}/logs",
    tags=["logs"],
)

app.include_router(
    history.router,
    prefix=f"{settings.API_V1_PREFIX}",
    tags=["history"],
)

app.include_router(
    auth.router,
    prefix=f"{settings.API_V1_PREFIX}/auth",
    tags=["auth"],
)

from app.hitl import api as hitl_api
app.include_router(
    hitl_api.router,
    prefix=f"{settings.API_V1_PREFIX}/hitl",
    tags=["hitl"],
)

from app.routers import uploads
app.include_router(
    uploads.router,
    prefix=f"{settings.API_V1_PREFIX}/uploads",
    tags=["uploads"],
)

# WebSocket for real-time streaming
from app.routers import ws
app.include_router(
    ws.router,
    prefix=f"{settings.API_V1_PREFIX}/ws",
    tags=["websocket"],
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )
