"""
Veritabanı bağlantı yönetimi.
SQLAlchemy async engine kullanılıyor — her istek kendi session'ını alır.
"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from config import settings

# async engine: connection pool otomatik yönetilir
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,          # SQL logları kapatık (debug için True yapılabilir)
    pool_size=10,        # max 10 eşzamanlı bağlantı
    max_overflow=5,      # pool dolduğunda +5 ek bağlantı
)

# Session factory — her endpoint çağrısında yeni bir session üretir
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    """FastAPI dependency — request başına bir session açar ve kapatır."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
