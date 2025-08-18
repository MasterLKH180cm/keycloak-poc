from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database settings
    database_url: str = Field(..., env="DATABASE_URL")

    # Redis settings
    redis_url: str = Field(..., env="REDIS_URL")

    # Keycloak settings
    keycloak_server_url: str = Field(..., env="KEYCLOAK_SERVER_URL")
    keycloak_realm: str = Field(..., env="KEYCLOAK_REALM")
    keycloak_client_id: str = Field(..., env="KEYCLOAK_CLIENT_ID")
    keycloak_client_secret: str = Field(..., env="KEYCLOAK_CLIENT_SECRET")
    keycloak_admin_username: str = Field(..., env="KEYCLOAK_ADMIN_USERNAME")
    keycloak_admin_password: str = Field(..., env="KEYCLOAK_ADMIN_PASSWORD")

    # JWT settings
    jwt_secret_key: str = Field(..., env="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(
        default=15, env="ACCESS_TOKEN_EXPIRE_MINUTES"
    )
    refresh_token_expire_days: int = Field(default=30, env="REFRESH_TOKEN_EXPIRE_DAYS")

    # Application settings
    debug: bool = Field(default=False, env="DEBUG")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    cors_origins: List[str] = Field(
        default=["http://localhost:3000"], env="CORS_ORIGINS"
    )

    # Security settings for healthcare compliance
    password_min_length: int = 12
    session_timeout_minutes: int = 30
    max_login_attempts: int = 5
    account_lockout_duration_minutes: int = 30

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
