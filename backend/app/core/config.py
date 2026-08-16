from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Biến môi trường của ứng dụng, đọc từ backend/.env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database (Supabase Postgres)
    SUPABASE_DB_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/postgres"

    # JWT
    SECRET_KEY: str = "dev-secret-key-change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # LLM — ưu tiên OpenRouter; không có key OpenRouter thì tự fallback sang Gemini.
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "nvidia/nemotron-3-super-120b-a12b:free"
    # Gemini: chấp nhận cả 2 tên biến trong .env — GOOGLE_API_KEY (chuẩn của
    # SDK Google, pipeline RAG trong src/rag đọc tên này) hoặc GEMINI_API_KEY
    # (tên cũ của dự án). Đặt biến nào cũng được.
    GOOGLE_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"

    @property
    def gemini_api_key(self) -> str:
        """Key Gemini: ưu tiên GOOGLE_API_KEY, sau đó đến GEMINI_API_KEY."""
        return self.GOOGLE_API_KEY or self.GEMINI_API_KEY

    # Nghiệp vụ: ngưỡng total_score được coi là qua môn (thỏa mãn điều kiện tiên quyết)
    PASS_THRESHOLD: float = 5.0


settings = Settings()
