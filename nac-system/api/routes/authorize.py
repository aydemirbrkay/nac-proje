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
  6. API → FreeRADIUS'a VLAN atribütlerini döner
  7. FreeRADIUS → Switch'e söyler → port o VLAN'a atanır
  8. Kullanıcı sadece kendi VLAN'ındaki kaynaklara erişebilir
"""

import logging
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import RadUserGroup, RadGroupReply, MacDevice, RadReply
from schemas import RadiusAuthorizeRequest, AuthorizeResponse

logger = logging.getLogger(__name__)
router = APIRouter()


def normalize_mac(mac: str) -> str:
    """MAC adresini AA:BB:CC:DD:EE:FF formatına çevirir."""
    clean = mac.replace("-", "").replace(".", "").replace(":", "").upper()
    if len(clean) != 12:
        return mac.upper()
    return ":".join(clean[i:i+2] for i in range(0, 12, 2))


@router.post("/authorize", response_model=AuthorizeResponse)
async def authorize(
    request: RadiusAuthorizeRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Kullanıcının grubunu belirleyip ilgili VLAN ve policy atribütlerini döner.
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
            group = device.groupname
            return await _build_authorize_response(group, db)

        # Bilinmeyen cihaz → guest
        # FreeRADIUS be used for dynamic VLAN assignment
        # https://stackoverflow.com/questions/57990822/can-freeradius-be-used-for-dynamic-vlan-assignment-based-on-a-certificate-attrib

        return AuthorizeResponse(
            result="accept",
            group="guest",
            vlan_id="30",
            reply_attributes={
                "Tunnel-Type": "13",
                "Tunnel-Medium-Type": "6",
                "Tunnel-Private-Group-Id": "30",
            },
        )



# Normal kullanıcılar için grup ve VLAN ataması yapalım
# Burada grup bazlı attributelar eklenebilir,aynı zamanda kullanıcı bazlı da attributelar eklenebilir. Kullanıcı bazlı attributelar grup bazlı attributelardan önce gelir.
# Örneğin employee grubuna VLAN 20 atanması grup bazlı atama hepsi VLAN 20
# VLAN bazlı kısıtlama getirilebilmesini de sağlar


    # ── 2. Normal kullanıcı ──
    # radusergroup tablosundan kullanıcının grubunu bul
    stmt = select(RadUserGroup).where(
        RadUserGroup.username == username
    ).order_by(RadUserGroup.priority)
    result = await db.execute(stmt)
    user_group = result.scalar_one_or_none()

    if user_group is None:
        logger.warning(f"Kullanıcı grubunda değil: {username}")
        return AuthorizeResponse(
            result="reject",
            message="Kullanıcı herhangi bir gruba atanmamış.",
        )

    group = user_group.groupname

    # Kullanıcıya özel reply atribütlerini de ekle
    response = await _build_authorize_response(group, db)

    # radreply tablosundan kullanıcıya özel atribütler
    stmt = select(RadReply).where(RadReply.username == username)
    result = await db.execute(stmt)
    user_replies = result.scalars().all()
    for reply in user_replies:
        response.reply_attributes[reply.attribute] = reply.value

    return response


async def _build_authorize_response(
    group: str,
    db: AsyncSession,
) -> AuthorizeResponse:
    """Grup bazlı atribütleri toplayıp AuthorizeResponse oluşturur."""

    # radgroupreply tablosundan grup atribütlerini çek
    stmt = select(RadGroupReply).where(RadGroupReply.groupname == group)
    result = await db.execute(stmt)
    group_replies = result.scalars().all()

    reply_attrs = {}
    vlan_id = None

    for attr in group_replies:
        reply_attrs[attr.attribute] = attr.value
        if attr.attribute == "Tunnel-Private-Group-Id":
            vlan_id = attr.value

    logger.info(f"Authorize sonucu: grup={group}, VLAN={vlan_id}")

    return AuthorizeResponse(
        result="accept",
        group=group,
        vlan_id=vlan_id,
        reply_attributes=reply_attrs,
    )


