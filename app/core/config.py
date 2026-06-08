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
    # Supabase Storage (S3-compatible)
    # ------------------------------------------------------------------
    supabase_url: str                   # e.g. https://your-project-ref.supabase.co
    supabase_s3_access_key: str
    supabase_s3_secret_key: str
    supabase_bucket_name: str = "hospital-assets"

    # ------------------------------------------------------------------
    # Email — Resend
    # ------------------------------------------------------------------
    resend_api_key: str
    email_from: str

    # ------------------------------------------------------------------
    # Firebase Cloud Messaging
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
