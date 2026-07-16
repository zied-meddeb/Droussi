from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    supabase_url: str
    supabase_service_key: str
    supabase_jwt_secret: str
    # Expected JWT audience for Supabase user tokens (GoTrue uses "authenticated").
    supabase_jwt_aud: str = "authenticated"

    openrouter_api_key: str
    # Fixed daily exam quota PER USER (does not shrink as more users join).
    per_user_exam_limit: int = 30
    # Account-wide safety cap: stop all generation once total spend for the
    # current UTC day reaches this many USD. Protects the shared credit pool.
    global_daily_cost_limit_usd: float = 5.0
    # Comma-separated emails allowed to view the super-admin dashboard.
    super_admin_emails: str = ""
    openrouter_model: str = "deepseek/deepseek-chat-v3-0324:free"
    openrouter_fallback_models: str = (
        "qwen/qwen3-235b-a22b:free,"
        "mistralai/mistral-small-3.1-24b-instruct:free,"
        "google/gemma-3-27b-it:free,"
        "openrouter/free"
    )
    openrouter_request_timeout: int = 60
    openrouter_max_model_attempts: int = 3
    openrouter_referer: str = "http://localhost:5173"
    openrouter_title: str = "Exam Generator"

    allowed_origins: str = "http://localhost:5173"
    documents_bucket: str = "documents"
    exports_bucket: str = "exports"
    # Reject documents whose downloaded bytes exceed this, before parsing them
    # into memory. Defaults to 15 MiB.
    max_document_bytes: int = 15 * 1024 * 1024

    @property
    def supabase_jwt_issuer(self) -> str:
        """Expected `iss` claim — Supabase GoTrue issues tokens from
        ``{project_url}/auth/v1``."""
        return f"{self.supabase_url.rstrip('/')}/auth/v1"

    @property
    def cors_origins(self) -> list[str]:
        origins: list[str] = []
        for o in self.allowed_origins.split(","):
            origin = o.strip().rstrip("/")
            if origin and origin not in origins:
                origins.append(origin)
        return origins

    @property
    def super_admins(self) -> list[str]:
        return [
            e.strip().lower()
            for e in self.super_admin_emails.split(",")
            if e.strip()
        ]

    @property
    def openrouter_models(self) -> list[str]:
        models: list[str] = []
        for candidate in [self.openrouter_model, *self.openrouter_fallback_models.split(",")]:
            model = candidate.strip()
            if model and model not in models:
                models.append(model)
        return models


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
