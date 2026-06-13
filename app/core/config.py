from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ------------------------------------------------------------------
    # App
    # ------------------------------------------------------------------
    secret_key: str
    app_env: str = "development"

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------
    database_url: str

    # ------------------------------------------------------------------
    # JWT
    # ------------------------------------------------------------------
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # ------------------------------------------------------------------
    # Supabase Storage (S3-compatible) — optional until storage is wired
    # ------------------------------------------------------------------
    supabase_url: str | None = None
    supabase_s3_access_key: str | None = None
    supabase_s3_secret_key: str | None = None
    supabase_bucket_name: str = "hospital-assets"

    # ------------------------------------------------------------------
    # Email — Resend — optional until notifications are wired
    # ------------------------------------------------------------------
    resend_api_key: str | None = None
    email_from: str | None = None

    # ------------------------------------------------------------------
    # Firebase Cloud Messaging — optional until notifications are wired
    # ------------------------------------------------------------------
    firebase_credentials_path: str = "firebase-credentials.json"

    # ------------------------------------------------------------------
    # CORS
    # ------------------------------------------------------------------
    frontend_url: str = "http://localhost:3000"
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        """Split comma-separated CORS_ORIGINS into a list."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()