"""
Yetkilendirme (Authorization) endpoint.

Kimlik doğrulama (auth) başarılı olduktan sonra FreeRADIUS bu endpoint'i çağırarak
kullanıcının hangi ağ kaynaklarına erişebileceğini sorar.

Bu endpoint kullanıcının grubunu bulur ve o gruba ait VLAN atamasını döner.
Böylece switch, kullanıcıyı doğru VLAN'a yerleştirir.

Akış:
  1. Kullanıcı ağa bağlanır → Switch, FreeRADIUS'a sorar
  2. FreeRADIUS → POST /auth → kimlik doğrulama (şifre kontrol) → BAŞARILI
  3. FreeRADIUS → POST /authorize (kullanıcı adını gönderir)
  4. API → radusergroup tablosundan grubunu bulur (admin, employee, guest)
  5. API → radgroupreply tablosundan VLAN bilgisini çeker (VLAN 10, 20, 30)
  6. API → FreeRADIUS'a VLAN atribütlerini döner (düz JSON — rlm_rest uyumlu)
  7. FreeRADIUS → Switch'e söyler → port o VLAN'a atanır
  8. Kullanıcı sadece kendi VLAN'ındaki kaynaklara erişebilir

Yanıt formatı notu:
  FreeRADIUS rlm_rest modülü, post-auth aşamasında JSON response'daki
  top-level key'leri RADIUS attribute olarak okur ve reply paketine ekler.
  Bu nedenle Tunnel-Type, Tunnel-Medium-Type, Tunnel-Private-Group-Id
  düz (flat) JSON key olarak döndürülür.
"""

import logging
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import RadUserGroup, RadGroupReply, MacDevice, RadReply
from schemas import RadiusAuthorizeRequest

logger = logging.getLogger(__name__)
router = APIRouter()


def normalize_mac(mac: str) -> str:
    """MAC adresini AA:BB:CC:DD:EE:FF formatına çevirir."""
    clean = mac.replace("-", "").replace(".", "").replace(":", "").upper()
    if len(clean) != 12:
        return mac.upper()
    return ":".join(clean[i:i+2] for i in range(0, 12, 2))


@router.post("/authorize")
async def authorize(
    request: RadiusAuthorizeRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Kullanıcının grubunu belirleyip ilgili VLAN ve policy atribütlerini döner.

    Yanıt formatı: FreeRADIUS rlm_rest uyumlu düz JSON.
    Tunnel-Type, Tunnel-Medium-Type, Tunnel-Private-Group-Id top-level key
    olarak döner; rlm_rest bunları doğrudan Access-Accept paketine ekler.
    """
    username = request.username
    logger.info(f"Authorize isteği: username={username}")

    # ── 1. MAB (MAC Authentication Bypass) kontrolü ──
    # Bazı cihazların (yazıcı, IP kamera, IoT sensör vb.) kullanıcı adı/şifre
    # girme yeteneği yoktur. Bu cihazlar ağa bağlanırken kimlik bilgisi yerine
    # MAC adreslerini gönderir — buna MAB denir.
    # calling_station_id alanı MAC adresi taşır; doluysa bu bir MAB isteğidir.
    if request.calling_station_id:
        mac = normalize_mac(request.calling_station_id)

        # MAC adresi mac_devices tablosunda kayıtlı ve aktif mi?
        # Kayıtlı cihazlara önceden bir grup atanmıştır (örn: iot_devices → VLAN 40).
        stmt = select(MacDevice).where(
            MacDevice.mac_address == mac,
            MacDevice.is_active == True,
        )
        result = await db.execute(stmt)
        device = result.scalar_one_or_none()

        if device:
            # Kayıtlı cihaz: cihazın grubuna göre VLAN atribütlerini döndür.
            # Politika: Kayıtlı IoT/yazıcı cihazları kendi VLAN segmentine yerleşir.
            return JSONResponse(content=await _build_authorize_response(device.groupname, db))

        # Bilinmeyen MAC adresi → Güvenlik politikası gereği en kısıtlı VLAN'a al.
        # Politika: Tanınmayan cihazlar misafir ağına (VLAN 30) düşer, tam erişim engellenir.
        # Filter-Id: Switch'e uygulanacak ACL adı — misafir trafiğini kısıtlar.
        logger.info(f"Bilinmeyen MAC, guest VLAN atanıyor: {mac}")
        return JSONResponse(content={
            "Tunnel-Type": "13",           # 13 = VLAN (IEEE 802.1Q standardı)
            "Tunnel-Medium-Type": "6",     # 6  = IEEE 802 (Ethernet)
            "Tunnel-Private-Group-Id": "30",  # VLAN ID 30 → Misafir ağı
            "Filter-Id": "guest-acl",      # Switch ACL → internet dışı erişimi engeller
        })

    # ── 2. Normal kullanıcı yetkilendirmesi ──
    # MAB değilse kullanıcı adı/şifre ile kimliği doğrulanmış bir kullanıcıdır.
    # Kullanıcının hangi gruba atandığını radusergroup tablosundan öğren.
    # Grup, erişim politikasını belirler:
    #   admin    → VLAN 10 (Yönetim ağı   — tam erişim)
    #   employee → VLAN 20 (Şirket ağı    — iç kaynaklara erişim)
    #   guest    → VLAN 30 (Misafir ağı   — yalnızca internet)
    stmt = select(RadUserGroup).where(
        RadUserGroup.username == username
    ).order_by(RadUserGroup.priority)
    result = await db.execute(stmt)
    user_group = result.scalar_one_or_none()

    if user_group is None:
        # Gruba atanmamış kullanıcı → erişim reddedilir.
        # Politika: Grupsuz kullanıcıya hiçbir VLAN atanmaz, ağa giremez.
        logger.warning(f"Kullanıcı grubunda değil: {username}")
        return JSONResponse(
            status_code=404,
            content={"result": "reject", "message": "Kullanıcı herhangi bir gruba atanmamış."},
        )

    group = user_group.groupname

    # Gruba ait VLAN ve politika atribütlerini radgroupreply tablosundan çek.
    response_data = await _build_authorize_response(group, db)

    # Kullanıcıya özel override atribütleri varsa grup politikasının üzerine yaz.
    # radreply tablosu: belirli bir kullanıcıya özel VLAN veya ACL tanımlamak için kullanılır.
    # Örnek: emp_ali normalde VLAN 20'deyken, radreply'a VLAN 10 yazılırsa o kullanıcı
    # VLAN 10'a atanır — grup politikasından bağımsız bireysel istisna tanımlanmış olur.
    stmt = select(RadReply).where(RadReply.username == username)
    result = await db.execute(stmt)
    user_replies = result.scalars().all()
    for reply in user_replies:
        response_data[reply.attribute] = reply.value

    return JSONResponse(content=response_data)


async def _build_authorize_response(group: str, db: AsyncSession) -> dict:
    """
    Grup bazlı atribütleri toplayıp rlm_rest uyumlu flat dict döner.

    FreeRADIUS 3.2 rlm_rest JSON yanıt formatı:
      {"Attribute-Name": "value", ...}  — flat, top-level RADIUS attribute key'leri
    "reply" wrapper'ı FreeRADIUS 3.2'de liste adı değil attribute adı olarak
    işlendiğinden kabul görmez.

    VLAN atama politikası (radgroupreply tablosundan okunur):
      Grup        │ Tunnel-Private-Group-Id │ Erişim Seviyesi
      ────────────┼─────────────────────────┼──────────────────────────────
      admin       │ 10                      │ Tam erişim (yönetim ağı)
      employee    │ 20                      │ Şirket iç kaynakları
      guest       │ 30                      │ Yalnızca internet
      iot_devices │ 40                      │ Yalnızca IoT servisleri

    Tunnel-Type = 13        → IEEE 802.1Q VLAN tünelleme
    Tunnel-Medium-Type = 6  → Ethernet (IEEE 802) ortamı
    """
    # Gruba tanımlı tüm RADIUS reply atribütlerini çek.
    # radgroupreply tablosu: her grup için Tunnel-Type, Tunnel-Medium-Type,
    # Tunnel-Private-Group-Id ve varsa Filter-Id gibi politika atribütlerini tutar.
    stmt = select(RadGroupReply).where(RadGroupReply.groupname == group)
    result = await db.execute(stmt)
    group_replies = result.scalars().all()

    vlan_id = None
    response: dict = {}

    for attr in group_replies:
        # Her atribütü FreeRADIUS'un beklediği düz JSON formatına ekle.
        # FreeRADIUS bu key'leri Access-Accept paketine RADIUS atribütü olarak koyar,
        # switch de bu pakete bakarak portu ilgili VLAN'a atar.
        response[attr.attribute] = attr.value
        if attr.attribute == "Tunnel-Private-Group-Id":
            vlan_id = attr.value

    logger.info(f"Authorize sonucu: grup={group}, VLAN={vlan_id}")
    return response
