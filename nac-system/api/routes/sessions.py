"""
Sessions endpoint — aktif oturumları Redis cache'inden sorgular.
Redis'teki "session:*" key'leri üzerinden hızlı sorgulama yapar.
"""
import json
import logging
from fastapi import APIRouter
from schemas import ActiveSession
from services.redis_service import redis_client

logger = logging.getLogger(__name__)
router = APIRouter()

ACTIVE_SESSION_PREFIX = "session:"


@router.get("/sessions/active", response_model=list[ActiveSession])
async def get_active_sessions():
    """
    Redis'teki tüm aktif oturumları döndürür.

    SCAN komutu kullanılıyor — KEYS * yerine tercih edilmeli çünkü:
    - KEYS tüm key'leri tek seferde tarar, büyük veri setlerinde Redis'i bloklar
    - SCAN cursor-based iterasyon yapar, non-blocking'dir
    """
    sessions = []

    # SCAN ile "session:" prefix'li tüm key'leri tara
    cursor = 0
    while True:
        cursor, keys = await redis_client.scan(
            cursor=cursor,
            match=f"{ACTIVE_SESSION_PREFIX}*",
            count=100,  # her iterasyonda ~100 key kontrol et
        )


# Redis'ten her bir session key'ini al ve ActiveSession objesine dönüştür bu şekilde hızlıca aktif 
# oturum bilgisi dönebiliriz
# yani nac-system'in PostgreSQL'e gitmeden Redis'teki cache'den anlık oturum bilgisi döndürmesini sağlar
# Neden redis çünkü çok hızlı cache mantığı var ve aktif oturum bilgisi genellikle sık güncellenir, bu yüzden Redis gibi bir in-memory veri deposu ideal olur
# postgreSQL'e gitmeden anlık oturum bilgisi döner, bu da performansı artırır ve kullanıcı deneyimini iyileştirir
        for key in keys:
            raw = await redis_client.get(key)
            if raw:
                try:
                    data = json.loads(raw) # Redis'teki JSON string'i Python dict'e çevirir
                    sessions.append(ActiveSession(
                        username=data.get("username", ""),
                        session_id=data.get("session_id", ""),
                        nas_ip=data.get("nas_ip", ""),
                        nas_port=data.get("nas_port"),
                        start_time=data.get("start_time", ""),
                        group=data.get("group"),
                        vlan_id=data.get("vlan_id"),
                        department=data.get("department"),
                        session_duration=data.get("session_duration", 0),
                        input_octets=data.get("input_octets", 0),
                        output_octets=data.get("output_octets", 0),
                    ))
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"Bozuk session verisi: key={key}, hata={e}")

        # cursor 0'a dönünce tarama bitti
        if cursor == 0:
            break

    logger.info(f"Aktif oturum sayısı: {len(sessions)}")
    return sessions
