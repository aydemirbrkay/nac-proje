"""
SQLAlchemy ORM modelleri.
FreeRADIUS şemasıyla uyumlu tablo tanımları.
"""
from sqlalchemy import Column, Integer, BigInteger, String, Boolean, DateTime, func
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class RadCheck(Base):
    """Kullanıcı kimlik bilgileri (username + password hash)."""
    __tablename__ = "radcheck"

    id = Column(Integer, primary_key=True)
    username = Column(String(64), nullable=False, index=True)
    attribute = Column(String(64), nullable=False)
    op = Column(String(2), nullable=False, default=":=")
    value = Column(String(253), nullable=False)


class RadReply(Base):
    """Kullanıcıya dönülecek RADIUS atribütleri."""
    __tablename__ = "radreply"

    id = Column(Integer, primary_key=True)
    username = Column(String(64), nullable=False, index=True)
    attribute = Column(String(64), nullable=False)
    op = Column(String(2), nullable=False, default=":=")
    value = Column(String(253), nullable=False)


class RadUserGroup(Base):
    """Kullanıcı ↔ grup ilişkileri."""
    __tablename__ = "radusergroup"

    id = Column(Integer, primary_key=True)
    username = Column(String(64), nullable=False, index=True)
    groupname = Column(String(64), nullable=False)
    priority = Column(Integer, nullable=False, default=1)


class RadGroupReply(Base):
    """Grup bazlı RADIUS atribütleri (VLAN atamaları vb.)."""
    __tablename__ = "radgroupreply"

    id = Column(Integer, primary_key=True)
    groupname = Column(String(64), nullable=False, index=True)
    attribute = Column(String(64), nullable=False)
    op = Column(String(2), nullable=False, default=":=")
    value = Column(String(253), nullable=False)


class RadAcct(Base):
    """RADIUS accounting kayıtları — oturum bilgileri."""
    __tablename__ = "radacct"

    id = Column(BigInteger, primary_key=True)
    acctsessionid = Column(String(64), nullable=False)
    acctuniqueid = Column(String(32), nullable=False, unique=True)
    username = Column(String(64), nullable=False, index=True)
    nasipaddress = Column(String(15), nullable=False)
    nasportid = Column(String(32))
    acctstarttime = Column(DateTime)
    acctupdatetime = Column(DateTime)
    acctstoptime = Column(DateTime)
    acctsessiontime = Column(BigInteger, default=0)
    acctinputoctets = Column(BigInteger, default=0)
    acctoutputoctets = Column(BigInteger, default=0)
    acctterminatecause = Column(String(32))
    framedipaddress = Column(String(15))
    callingstation = Column(String(50))
    acctstatustype = Column(String(25))


class MacDevice(Base):
    """MAB için kayıtlı MAC adresleri."""
    __tablename__ = "mac_devices"

    id = Column(Integer, primary_key=True)
    mac_address = Column(String(17), nullable=False, unique=True)
    device_name = Column(String(128))
    device_type = Column(String(64))
    groupname = Column(String(64), nullable=False, default="guest")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, server_default=func.now())
