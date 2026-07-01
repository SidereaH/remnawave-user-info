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
    panel_version: str = "2.7.4"

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

    @property
    def panel_version_tuple(self) -> tuple[int, ...]:
        parts: list[int] = []
        for x in self.panel_version.split("."):
            if x.isdigit():
                parts.append(int(x))
            else:
                break
        return tuple(parts) or (2, 8)

    @property
    def revoke_needs_body(self) -> bool:
        # Remnawave 2.8.0+ требует тело у POST .../actions/revoke; 2.7.x — нет.
        return self.panel_version_tuple >= (2, 8)


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
