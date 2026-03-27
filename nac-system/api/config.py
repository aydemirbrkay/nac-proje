"""
Uygulama konfigürasyonu.
Tüm environment variable'lar burada merkezi olarak yönetilir.
pydantic-settings sayesinde .env dosyasından otomatik yüklenir.
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # PostgreSQL
    DATABASE_URL: str

    # Redis
    REDIS_URL: str

    # Güvenlik
    SECRET_KEY: str

    # Rate limiting
    MAX_AUTH_ATTEMPTS: int = 5
    AUTH_LOCKOUT_SECONDS: int = 300  # 5 dakika

    class Config:
        env_file = ".env"


settings = Settings()
