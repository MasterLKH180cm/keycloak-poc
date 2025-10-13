import os
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from pydantic import field_validator
from pydantic_settings import BaseSettings

env_path = Path(__file__).parent.parent / ".env"

load_dotenv(dotenv_path=env_path)


class Settings(BaseSettings):
    # Database settings
    keycloak_database_url: str = os.getenv("KEYCLOAK_DATABASE_URL")
    session_database_url: str = os.getenv("SESSION_DATABASE_URL")
    # Redis settings
    redis_url: str = os.getenv("REDIS_URL")
    redis_stream_name: str = os.getenv("REDIS_STREAM_NAME", "dictation_stream")

    # Keycloak settings
    keycloak_server_url: str = os.getenv("KEYCLOAK_SERVER_URL")
    keycloak_realm: str = os.getenv("KEYCLOAK_REALM")
    keycloak_client_id: str = os.getenv("KEYCLOAK_CLIENT_ID")
    keycloak_client_secret: str = os.getenv("KEYCLOAK_CLIENT_SECRET")
    keycloak_admin_username: str = os.getenv("KEYCLOAK_ADMIN_USERNAME")
    keycloak_admin_password: str = os.getenv("KEYCLOAK_ADMIN_PASSWORD")
    keycloak_registration_access_token: str = os.getenv(
        "KEYCLOAK_REGISTRATION_ACCESS_TOKEN"
    )
    keycloak_verify_ssl: bool = os.getenv("KEYCLOAK_VERIFY_SSL", "false")

    # JWT settings
    jwt_secret_key: str = os.getenv("JWT_SECRET_KEY")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    access_token_expire_minutes: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15")
    )
    refresh_token_expire_days: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30"))

    # Application settings
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    cors_origins: str = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,https://localhost:3000,http://localhost:8000,https://localhost:8000,https://radiology-reporting-app.com,https://reporting-frontend-hvegfdd6b0h3e6bg.westus3-01.azurewebsites.net,https://reporting-service-gjcgb5a6czeecvcr.westus3-01.azurewebsites.net",
    )

    @field_validator("cors_origins")
    @classmethod
    def parse_cors_origins(cls, v) -> List[str]:
        if isinstance(v, str):
            return [origin.strip().strip('"') for origin in v.split(",")]
        return v

    # Security settings for healthcare compliance
    password_min_length: int = 12
    session_timeout_minutes: int = 30
    max_login_attempts: int = 5
    account_lockout_duration_minutes: int = 30

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
