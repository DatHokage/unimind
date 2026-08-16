from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_db_url(url: str) -> str:
    """Chuẩn hóa scheme của connection string về dạng SQLAlchemy hiểu được.

    - `postgres://...` (kiểu cũ, SQLAlchemy >=1.4 từ chối) → `postgresql://...`
    - `postgresql://...` (chỉ dialect, chưa có driver) → `postgresql+psycopg2://...`
      để chắc chắn dùng đúng driver psycopg2-binary đã cài trong requirements.
    Các scheme khác (sqlite://...) được giữ nguyên.

    Lỗi `NoSuchModuleError: sqlalchemy.dialects:postgresql.postgresql` xảy ra khi
    SQLAlchemy nhận một URL có driver lạ (vd `postgresql+postgresql://...` do gõ
    nhầm) hoặc URL bị hỏng; hàm này chặn các dạng sai phổ biến ngay từ đầu.
    """
    url = url.strip()
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg2://" + url[len("postgresql://"):]
    elif url.startswith("postgresql+postgresql://"):
        # Dạng gõ nhầm `dialect+dialect` — chính là nguyên nhân của
        # NoSuchModuleError: postgresql.postgresql
        url = "postgresql+psycopg2://" + url[len("postgresql+postgresql://"):]
    return url


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

    # CORS: danh sách origin được phép gọi API, phân tách bằng dấu phẩy.
    # Khi deploy: thêm domain Vercel của frontend, VD
    # CORS_ORIGINS=http://localhost:5173,https://unimind.vercel.app
    CORS_ORIGINS: str = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    def model_post_init(self, __context) -> None:
        # Chuẩn hóa scheme một chỗ duy nhất: cả app (database.py) lẫn alembic
        # (env.py) đều đọc SUPABASE_DB_URL từ settings — KHÔNG nơi nào trong
        # code ghép chuỗi URL thủ công.
        self.SUPABASE_DB_URL = normalize_db_url(self.SUPABASE_DB_URL)
        # Debug khi deploy: chỉ in scheme — KHÔNG bao giờ in full URL/password.
        # Xóa 2 dòng này khi migration trên Render đã chạy ổn định.
        scheme = self.SUPABASE_DB_URL.split("://", 1)[0]
        print(f"[config] DB URL scheme = {scheme!r}", flush=True)


settings = Settings()
