from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_TITLE: str = "Online Cinema API"
    DATABASE_URL: str = "sqlite+aiosqlite:///./cinema.db"
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ACTIVATION_TOKEN_EXPIRE_HOURS: int = 24
    PASSWORD_RESET_TOKEN_EXPIRE_HOURS: int = 1

    REDIS_URL: str = "redis://localhost:6379/0"

    MAIL_USERNAME: str = ""
    MAIL_PASSWORD: str = ""
    MAIL_FROM: str = "noreply@cinema.local"
    MAIL_SERVER: str = "localhost"
    MAIL_PORT: int = 587

    class Config:
        env_file = ".env"

settings = Settings()
