from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or a .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    github_token: str
    openai_api_key: str
    chroma_persist_dir: str = "./data/chroma"
    chroma_collection_name: str = "pr_warden"
    openai_max_retries: int = 3


settings: Settings = Settings()
