from pydantic_settings import BaseSettings, SettingsConfigDict


def _normalize_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    if url.startswith("postgresql://") and not url.startswith("postgresql+psycopg://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://story:story@postgres:5432/story_engine"
    llm_provider: str = "mock"
    llm_model_character: str = "gpt-4o-mini"
    llm_model_opposition: str = "gpt-4o-mini"
    llm_model_summary: str = "gpt-4o-mini"
    llm_model_narrative: str = "gpt-4o"
    llm_model_tts: str = "gpt-4o-mini-tts"
    llm_external_enabled: bool = False
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    chunk_size_prompts: int = 7

    model_config = SettingsConfigDict(env_file=".env")

    def model_post_init(self, __context) -> None:
        self.database_url = _normalize_database_url(self.database_url)


settings = Settings()
