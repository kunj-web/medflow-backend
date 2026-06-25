from pydantic_settings import BaseSettings, SettingsConfigDict


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
    test_database_url: str | None = None

    @property
    def sqlalchemy_database_url(self) -> str:
        """
        Keep existing postgresql:// env values valid while using SQLAlchemy's
        modern psycopg driver instead of the old psycopg2 default.
        """
        if self.database_url.startswith("postgresql://"):
            return self.database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        return self.database_url

    @property
    def sqlalchemy_test_database_url(self) -> str:
        if self.test_database_url:
            if self.test_database_url.startswith("postgresql://"):
                return self.test_database_url.replace(
                    "postgresql://", "postgresql+psycopg://", 1
                )
            return self.test_database_url
        return "sqlite+pysqlite:///./.pytest_cache/medflow_test.db"

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

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)


settings = Settings()
