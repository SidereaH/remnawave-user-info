from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    bot_token: str
    remnawave_url: str
    remnawave_token: str
    allowed_admin_ids: str = ""
    users_page_size: int = 250
    request_timeout: int = 20
    log_level: str = "INFO"

    @field_validator("remnawave_url")
    @classmethod
    def _strip_slash(cls, v: str) -> str:
        return v.rstrip("/")

    @property
    def admin_ids(self) -> set[int]:
        return {
            int(x.strip())
            for x in self.allowed_admin_ids.split(",")
            if x.strip()
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
