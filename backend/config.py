from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    FT_CLIENT_ID: str
    FT_CLIENT_SECRET: str
    FT_REDIRECT_URI: str
    SESSION_SECRET: str
    ADMIN_LOGINS: str  # Comma-separated list
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    DATABASE_URL: str = ""
    REDIS_URL: str = "redis://redis:6379/0"
    BACKEND_PUBLIC_URL: str = "http://localhost:8080"

    @property
    def admin_list(self) -> List[str]:
        return [login.strip() for login in self.ADMIN_LOGINS.split(",") if login.strip()]

    class Config:
        env_file = ".env"

settings = Settings()
