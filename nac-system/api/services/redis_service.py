"""
Redis bağlantı yönetimi.
Bu dosya Redis'e bağlantıyı kurar ve tek bir redis_client nesnesi oluşturur. 
Projedeki Redis kullanan her dosya bunu import eder ve aynı client'ı kullanır.
"""
import redis.asyncio as redis
from config import settings

"""""
ccounting.py	Oturum verilerini Redis'e yaz/güncelle/sil
sessions.py	Aktif oturumları Redis'ten oku
users.py	Kullanıcı online mı kontrol et
rate_limiter.py	Yanlış giriş sayacını tut
main.py	Interim-update simülasyonunda oturumları güncelle

"""""

# Async Redis client — connection pool otomatik yönetilir
redis_client = redis.from_url(
    settings.REDIS_URL,
    decode_responses=True,  # bytes yerine str döndür
)


async def get_redis() -> redis.Redis:
    """Redis client'ı döndürür."""
    return redis_client
