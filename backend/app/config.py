from typing import List, Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://postgres:postgres@db:5432/legacycrm"
    jwt_secret: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440  # 24 hours
    cors_origins: List[str] = ["http://localhost:5173"]
    upload_dir: str = "/app/uploads"
    # Days before a public portal link expires. Unset = links never expire.
    portal_link_days: Optional[int] = None

    # Sprint 16b — AI provider configuration
    llm_provider: str = "none"  # "claude" | "ollama" | "none" | "mock"
    llm_model: str = "claude-sonnet-4-20250514"
    claude_api_key: Optional[str] = None
    ollama_base_url: str = "http://localhost:11434"
    ai_enabled: bool = True
    ai_request_timeout_seconds: float = 30.0
    ai_company_name: str = "Legacy Roofing & Exteriors"
    ai_company_phone: str = "(765) 555-0101"

    # Sprint 17 — SMS / Twilio configuration
    sms_enabled: bool = False
    twilio_account_sid: Optional[str] = None
    twilio_auth_token: Optional[str] = None
    twilio_phone_number: Optional[str] = None

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
