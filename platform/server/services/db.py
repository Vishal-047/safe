import os
import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, DateTime, Boolean

logger = logging.getLogger('safelane.platform')

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./safelane.db")

# Normalize database URL scheme for SQLAlchemy async engine
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql://") and not DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

engine_kwargs = {}
if DATABASE_URL.startswith("postgresql+asyncpg"):
    if os.environ.get("DB_SSL_INSECURE") == "true":
        logger.warning("DB_SSL_INSECURE is set to true. Bypassing SSL verification. DO NOT USE IN PRODUCTION.")
        import ssl
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        engine_kwargs["connect_args"] = {"ssl": ssl_ctx}
    else:
        # Proper SSL context
        import ssl
        ssl_ctx = ssl.create_default_context()
        engine_kwargs["connect_args"] = {"ssl": ssl_ctx}

engine = create_async_engine(DATABASE_URL, **engine_kwargs)
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    github_username: Mapped[str] = mapped_column(String, nullable=False)
    github_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Registration(Base):
    __tablename__ = "registrations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    owner: Mapped[str] = mapped_column(String, nullable=False)
    repo: Mapped[str] = mapped_column(String, nullable=False)
    encrypted_pat: Mapped[str] = mapped_column(String, nullable=False)
    orchestrator_url: Mapped[str] = mapped_column(String, nullable=False)
    azure_search_endpoint: Mapped[str] = mapped_column(String, nullable=True)
    azure_search_key: Mapped[str] = mapped_column(String, nullable=True)
    azure_tenant_id: Mapped[str] = mapped_column(String, nullable=True)
    azure_workspace_id: Mapped[str] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_registration(owner: str, repo: str) -> Registration | None:
    async with async_session() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(Registration)
            .where(Registration.owner == owner, Registration.repo == repo, Registration.is_active == True)
            .order_by(Registration.created_at.desc())
        )
        return result.scalars().first()

async def create_registration(**kwargs) -> Registration:
    async with async_session() as session:
        reg = Registration(**kwargs)
        session.add(reg)
        await session.commit()
        await session.refresh(reg)
        return reg

async def list_registrations(user_id: int) -> list[Registration]:
    async with async_session() as session:
        from sqlalchemy import select
        result = await session.execute(select(Registration).where(Registration.user_id == user_id))
        return list(result.scalars().all())
