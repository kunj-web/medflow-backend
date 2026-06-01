from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Hospital Platform"
    APP_ENV: str = "development"
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Database
    DATABASE_URL: str
    TEST_DATABASE_URL: str = ""

    # Cloudflare R2
    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = ""
    R2_PUBLIC_URL: str = ""

    # Email
    RESEND_API_KEY: str = ""
    EMAIL_FROM: str = "noreply@hospital.com"

    # Firebase
    FIREBASE_CREDENTIALS_PATH: str = "firebase-credentials.json"

    # CORS
    FRONTEND_URL: str = "http://localhost:3000"

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def is_testing(self) -> bool:
        return self.APP_ENV == "testing"

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()