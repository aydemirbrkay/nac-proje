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

    # ── 1. MAB kontrolü ──
    if request.calling_station_id:
        mac = normalize_mac(request.calling_station_id)
        stmt = select(MacDevice).where(
            MacDevice.mac_address == mac,
            MacDevice.is_active == True,
        )
        result = await db.execute(stmt)
        device = result.scalar_one_or_none()

        if device:
            return JSONResponse(content=await _build_authorize_response(device.groupname, db))

        # Bilinmeyen cihaz → guest VLAN 30
        logger.info(f"Bilinmeyen MAC, guest VLAN atanıyor: {mac}")
        return JSONResponse(content={
            "result": "accept",
            "group": "guest",
            "vlan_id": "30",
            # rlm_rest uyumlu düz RADIUS atribütleri:
            "Tunnel-Type": "13",
            "Tunnel-Medium-Type": "6",
            "Tunnel-Private-Group-Id": "30",
            "Filter-Id": "guest-acl",
        })

    # ── 2. Normal kullanıcı ──
    stmt = select(RadUserGroup).where(
        RadUserGroup.username == username
    ).order_by(RadUserGroup.priority)
    result = await db.execute(stmt)
    user_group = result.scalar_one_or_none()

    if user_group is None:
        logger.warning(f"Kullanıcı grubunda değil: {username}")
        return JSONResponse(
            status_code=404,
            content={"result": "reject", "message": "Kullanıcı herhangi bir gruba atanmamış."},
        )

    group = user_group.groupname
    response_data = await _build_authorize_response(group, db)

    # Kullanıcıya özel reply atribütlerini de ekle (radreply tablosu)
    stmt = select(RadReply).where(RadReply.username == username)
    result = await db.execute(stmt)
    user_replies = result.scalars().all()
    for reply in user_replies:
        response_data[reply.attribute] = reply.value

    return JSONResponse(content=response_data)


async def _build_authorize_response(group: str, db: AsyncSession) -> dict:
    """
    Grup bazlı atribütleri toplayıp rlm_rest uyumlu düz dict döner.

    RADIUS atribütleri (Tunnel-Type vb.) top-level key olarak eklenir.
    FreeRADIUS rlm_rest post-auth aşamasında bunları Access-Accept'e yazar.
    """
    stmt = select(RadGroupReply).where(RadGroupReply.groupname == group)
    result = await db.execute(stmt)
    group_replies = result.scalars().all()

    vlan_id = None
    # Temel yanıt yapısı (sunum ve loglama için)
    response: dict = {
        "result": "accept",
        "group": group,
    }

    # radgroupreply atribütlerini düz (flat) olarak ekle — rlm_rest okur
    for attr in group_replies:
        response[attr.attribute] = attr.value
        if attr.attribute == "Tunnel-Private-Group-Id":
            vlan_id = attr.value

    response["vlan_id"] = vlan_id
    logger.info(f"Authorize sonucu: grup={group}, VLAN={vlan_id}")
    return response
