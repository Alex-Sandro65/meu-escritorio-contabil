from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings
import re


def _build_db_url(url: str) -> tuple[str, dict]:
    # Remove parâmetros incompatíveis com asyncpg e retorna connect_args separados
    clean = re.sub(r'[?&](sslmode|channel_binding)=[^&]*', '', url)
    clean = re.sub(r'\?&', '?', clean).rstrip('?').rstrip('&')
    connect_args = {}
    if 'neon.tech' in url or 'sslmode=require' in url:
        connect_args['ssl'] = 'require'
    return clean, connect_args


_db_url, _connect_args = _build_db_url(settings.DATABASE_URL)

engine = create_async_engine(
    _db_url,
    echo=settings.DEBUG,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    connect_args=_connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
