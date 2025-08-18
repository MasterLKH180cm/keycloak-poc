import logging
from contextlib import asynccontextmanager

import uvicorn
from app.api import auth, users
from app.core.config import settings
from app.db.database import init_db
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
        await init_db()
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

# Security middleware
app.add_middleware(
    TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "*.hospital.local"]
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")


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
        from app.db.database import engine

        async with engine.begin() as conn:
            await conn.execute("SELECT 1")
        status_info["database"] = "healthy"
    except Exception as e:
        status_info["database"] = f"unhealthy: {e}"

    try:
        # Check Redis
        await redis_manager.redis_client.ping()
        status_info["redis"] = "healthy"
    except Exception as e:
        status_info["redis"] = f"unhealthy: {e}"

    try:
        # Check Keycloak
        keycloak_service.admin_client.get_realms()
        status_info["keycloak"] = "healthy"
    except Exception as e:
        status_info["keycloak"] = f"unhealthy: {e}"

    return status_info


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
