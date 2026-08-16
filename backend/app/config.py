"""Application configuration, read from environment / .env."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Empty means "use the mock client"; see services.youcam.get_client.
    youcam_api_key: str = ""
    youcam_secret_key: str = ""

    # Comma-separated list of origins allowed to call the API.
    cors_origins: str = "http://localhost:3000"

    # Reject uploads above this size before decoding them.
    max_upload_bytes: int = 10 * 1024 * 1024

    # Uploads live in memory only, keyed by id, and expire after this long.
    upload_ttl_seconds: int = 1800
    max_cached_uploads: int = 200

    # How long the mock VTO pretends to work, so polling UI is exercised.
    mock_vto_latency_seconds: float = 2.5

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def using_mock(self) -> bool:
        return not (self.youcam_api_key and self.youcam_secret_key)


settings = Settings()
