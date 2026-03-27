"""
Pydantic şemaları — API request/response modelleri.
FreeRADIUS rlm_rest modülünün beklediği formata uygun.
"""
from datetime import datetime
from typing import Annotated, Literal
from pydantic import BaseModel, Field


# ── FreeRADIUS rlm_rest modülünden gelen istek formatı ──

class RadiusAuthRequest(BaseModel):
    """FreeRADIUS'un /auth endpoint'ine POST ettiği veri."""
    username: str
    password: str | None = None
    # MAB durumunda Calling-Station-Id (MAC adresi) gelir
    calling_station_id: str | None = None


class RadiusAuthorizeRequest(BaseModel):
    """FreeRADIUS'un /authorize endpoint'ine POST ettiği veri."""
    username: str
    calling_station_id: str | None = None


class RadiusAccountingRequest(BaseModel):
    """FreeRADIUS'un /accounting endpoint'ine POST ettiği veri."""
    username: str
    acct_status_type: str              # Start, Interim-Update, Stop
    acct_session_id: str
    acct_unique_session_id: str | None = None
    nas_ip_address: str = "0.0.0.0"
    nas_port_id: str | None = None
    acct_session_time: int = 0
    acct_input_octets: int = 0
    acct_output_octets: int = 0
    acct_terminate_cause: str | None = None
    framed_ip_address: str | None = None
    calling_station_id: str | None = None


# ── API Yanıt Modelleri ──

class AuthResponse(BaseModel):
    """Authentication yanıtı. FreeRADIUS bu yanıta göre Access-Accept/Reject döner."""
    result: str            # accept veya reject
    reply_attributes: dict = {}
    message: str = ""


class AuthorizeResponse(BaseModel):
    """Authorization yanıtı. VLAN ve policy atribütleri içerir."""
    result: str
    group: str | None = None
    vlan_id: str | None = None
    reply_attributes: dict = {}


class AccountingResponse(BaseModel):
    """Accounting yanıtı."""
    result: str
    message: str = ""


class UserInfo(BaseModel):
    """Kullanıcı bilgisi — /users endpoint'i için."""
    username: str
    group: str | None = None
    is_online: bool = False
    vlan_id: str | None = None


class ActiveSession(BaseModel):
    """Aktif oturum bilgisi — /sessions/active endpoint'i için."""
    username: str
    session_id: str
    nas_ip: str
    nas_port: str | None = None
    start_time: str
    group: str | None = None
    vlan_id: str | None = None
    department: str | None = None
    session_duration: int = 0
    input_octets: int = 0
    output_octets: int = 0


# ── User Management Schemas ──

class AdminLoginRequest(BaseModel):
    """Admin JWT token almak için giriş isteği."""
    username: str
    password: str


class TokenResponse(BaseModel):
    """JWT token yanıtı."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 28800  # 8 saat (saniye)


class UserCreate(BaseModel):
    """Yeni kullanıcı oluşturma isteği."""
    username: str
    password: Annotated[str, Field(min_length=8)]
    group: Literal["admin", "employee", "guest"]


class UserUpdate(BaseModel):
    """Kullanıcı grup güncelleme isteği."""
    group: Literal["admin", "employee", "guest"]


class PasswordChange(BaseModel):
    """Şifre değiştirme isteği."""
    new_password: Annotated[str, Field(min_length=8)]


class UserDetail(BaseModel):
    """Tek kullanıcı detay yanıtı (oluşturma/güncelleme/detay endpoint'leri için)."""
    username: str
    group: str | None = None
    vlan_id: str | None = None
    is_online: bool = False
