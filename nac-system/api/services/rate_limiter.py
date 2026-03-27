"""
Rate limiter — başarısız giriş denemelerini Redis ile sayar.

Mantık:
  1. Her başarısız denemede "{key_prefix}:{username}" key'inin değeri +1 artırılır
  2. Key'e TTL olarak lockout süresi atanır
  3. Değer MAX_AUTH_ATTEMPTS'e ulaşırsa kullanıcı kilitlenir
  4. Başarılı girişte key silinir (sayaç sıfırlanır)

key_prefix: "auth_fail" (varsayılan) veya "admin_fail" (admin login için).
"""
from services.redis_service import redis_client
from config import settings


async def is_rate_limited(username: str, key_prefix: str = "auth_fail") -> bool:
    """Kullanıcının kilitli olup olmadığını kontrol eder."""
    key = f"{key_prefix}:{username}"
    attempts = await redis_client.get(key)
    if attempts is None:
        return False
    return int(attempts) >= settings.MAX_AUTH_ATTEMPTS


async def record_failed_attempt(username: str, key_prefix: str = "auth_fail") -> int:
    """Başarısız girişi kaydeder, güncel deneme sayısını döndürür."""
    key = f"{key_prefix}:{username}"
    current = await redis_client.incr(key)
    if current == 1:
        await redis_client.expire(key, settings.AUTH_LOCKOUT_SECONDS)
    return current


async def reset_attempts(username: str, key_prefix: str = "auth_fail") -> None:
    """Başarılı giriş sonrası sayacı sıfırlar."""
    key = f"{key_prefix}:{username}"
    await redis_client.delete(key)


async def get_remaining_lockout(username: str, key_prefix: str = "auth_fail") -> int:
    """Kilitli kullanıcının kalan bekleme süresini döndürür (saniye)."""
    key = f"{key_prefix}:{username}"
    ttl = await redis_client.ttl(key)
    return max(0, ttl)
