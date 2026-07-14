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
    ingest_history_path: str = "./data/ingest_history.json"
    review_history_path: str = "./data/review_history.json"
    openai_max_retries: int = 3
    github_max_retries: int = 3

    langsmith_tracing: bool = False
    langsmith_endpoint: str = "https://api.smith.langchain.com"
    langsmith_api_key: str | None = None
    langsmith_project: str = "pr-warden"

    supabase_url: str | None = None
    supabase_key: str | None = None

    api_shared_key: str | None = None


settings: Settings = Settings()
