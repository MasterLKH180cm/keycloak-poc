import logging
from contextlib import asynccontextmanager

import uvicorn
from app.api import session
from app.core.config import settings
from app.db.database import init_session_db
from app.db.redis import redis_manager
from app.services.keycloak_service import keycloak_service
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown"""
    # Startup
    try:
        logger.info("Starting Hospital Authentication System...")

        # Initialize database
        # await init_keycloak_db()
        await init_session_db()
        logger.info("Database initialized")

        # Initialize Redis
        await redis_manager.init_redis()
        logger.info("Redis initialized")

        # Initialize Keycloak
        await keycloak_service.init_keycloak()
        logger.info("Keycloak initialized")

        logger.info("All services initialized successfully")

    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise

    yield

    # Shutdown
    try:
        await redis_manager.close_redis()
        logger.info("Services shut down successfully")
    except Exception as e:
        logger.error(f"Shutdown error: {e}")


# Initialize FastAPI app
app = FastAPI(
    title="Hospital Authentication System",
    description="HIPAA-compliant authentication system with Keycloak integration",
    version="1.0.0",
    docs_url="/api/docs" if settings.debug else None,
    redoc_url="/api/redoc" if settings.debug else None,
    lifespan=lifespan,
)

# ===== CRITICAL: Trusted Host Middleware =====
# This allows requests from Nginx reverse proxy
# Set to ["*"] for development, specify exact hosts for production
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=[
        "*",  # Allow all hosts (development)
        # For production, specify exact hosts:
        # "20.168.120.11",
        # "localhost",
        # "yourdomain.com",
    ],
)

# ===== CORS Middleware =====
# Configure CORS for browser-based clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Include API routes
# app.include_router(auth.router, prefix="/api/v1")
# app.include_router(users.router, prefix="/api/v1")
app.include_router(session.router, prefix="/api/session")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Hospital Authentication System API",
        "status": "running",
        "version": "1.0.0",
    }


@app.get("/health")
async def health_check_simple():
    """Simple health check endpoint for Docker/Kubernetes"""
    return {"status": "healthy"}


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Hospital Authentication System",
        "version": "1.0.0",
    }


@app.get("/api/v1/system/status")
async def system_status():
    """System status endpoint with service checks"""
    status_info = {"database": "unknown", "redis": "unknown", "keycloak": "unknown"}

    try:
        # Check database
        from app.db.database import session_db_engine
        from sqlalchemy import text

        # async with keycloak_db_engine.begin() as conn:
        #     await conn.execute(text("SELECT 1"))
        async with session_db_engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        status_info["database"] = "healthy"
    except Exception as e:
        status_info["database"] = f"unhealthy: {str(e)}"
        logger.error(f"Database health check failed: {e}")

    try:
        # Check Redis
        await redis_manager.redis_client.ping()
        status_info["redis"] = "healthy"
    except Exception as e:
        status_info["redis"] = f"unhealthy: {str(e)}"
        logger.error(f"Redis health check failed: {e}")

    try:
        # Check Keycloak
        keycloak_service.admin_client.get_realms()
        status_info["keycloak"] = "healthy"
    except Exception as e:
        status_info["keycloak"] = f"unhealthy: {str(e)}"
        logger.error(f"Keycloak health check failed: {e}")

    # Overall status
    all_healthy = all(status == "healthy" for status in status_info.values())

    return {
        "status": "healthy" if all_healthy else "degraded",
        "services": status_info,
        "version": "1.0.0",
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
        # Enable proxy headers support for Nginx
        proxy_headers=True,
        forwarded_allow_ips="*",
    )
