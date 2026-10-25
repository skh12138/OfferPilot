from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+psycopg://offerpilot:offerpilot@localhost:55432/offerpilot"
    app_mode: Literal["live", "demo", "test"] = "live"
    environment: Literal["development", "production"] = "development"
    public_origin: str = "http://localhost:5173"
    allow_registration: bool = False
    deepseek_api_key: SecretStr = SecretStr("")
    tavily_api_key: SecretStr = SecretStr("")
    llm_model: str = "deepseek-flash"
    run_max_calls: int = 50
    run_input_tokens: int = 80000
    run_output_tokens: int = 24000
    run_timeout_seconds: int = 600
    global_run_concurrency: int = 2
    user_run_concurrency: int = 1
    export_retention_hours: int = 24

    @model_validator(mode="after")
    def production_safety(self) -> "Settings":
        if self.environment == "production":
            if self.app_mode != "live" or not self.public_origin.startswith("https://"):
                raise ValueError("production requires live mode and an HTTPS origin")
        if not self.database_url.startswith("postgresql+psycopg://"):
            raise ValueError("PostgreSQL with psycopg is required")
        return self


@lru_cache
def settings() -> Settings:
    return Settings()
