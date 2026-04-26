from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str = Field(default="", alias="BOT_TOKEN")
    admin_ids: str = Field(default="", alias="ADMIN_IDS")
    api_id: int = Field(default=0, alias="API_ID")
    api_hash: str = Field(default="", alias="API_HASH")

    database_url: str = Field(default="sqlite+aiosqlite:///./data/app.db", alias="DATABASE_URL")
    sessions_dir: Path = Field(default=Path("./sessions"), alias="SESSIONS_DIR")
    log_dir: Path = Field(default=Path("./logs"), alias="LOG_DIR")

    min_send_delay: int = Field(default=30, alias="MIN_SEND_DELAY")
    max_send_delay: int = Field(default=120, alias="MAX_SEND_DELAY")
    cooldown_after_messages: int = Field(default=20, alias="COOLDOWN_AFTER_MESSAGES")
    cooldown_seconds: int = Field(default=900, alias="COOLDOWN_SECONDS")
    daily_account_limit: int = Field(default=80, alias="DAILY_ACCOUNT_LIMIT")
    max_retries: int = Field(default=3, alias="MAX_RETRIES")
    worker_idle_seconds: int = Field(default=5, alias="WORKER_IDLE_SECONDS")

    enable_bot_login: bool = Field(default=False, alias="ENABLE_BOT_LOGIN")

    ai_provider: str = Field(default="", alias="AI_PROVIDER")
    ai_api_key: str = Field(default="", alias="AI_API_KEY")
    ai_model: str = Field(default="gpt-4o-mini", alias="AI_MODEL")
    ai_api_base: str = Field(default="https://api.openai.com/v1", alias="AI_API_BASE")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("max_send_delay")
    @classmethod
    def validate_delays(cls, value: int, info) -> int:
        min_delay = info.data.get("min_send_delay", 30)
        if value < min_delay:
            raise ValueError("MAX_SEND_DELAY must be greater than or equal to MIN_SEND_DELAY")
        return value

    @field_validator("daily_account_limit", "cooldown_after_messages", "max_retries")
    @classmethod
    def validate_positive(cls, value: int) -> int:
        if value < 0:
            raise ValueError("numeric limits must be non-negative")
        return value

    @property
    def admin_id_set(self) -> set[int]:
        result: set[int] = set()
        for raw in self.admin_ids.replace(";", ",").split(","):
            raw = raw.strip()
            if raw:
                result.add(int(raw))
        return result

    def ensure_runtime_dirs(self) -> None:
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        if self.database_url.startswith("sqlite"):
            db_path = self.database_url.split(":///", 1)[-1]
            if db_path and db_path != ":memory:" and not db_path.startswith(":memory:"):
                Path(db_path).parent.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
