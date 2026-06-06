from fastapi import HTTPException, status
from sqlalchemy import select, func, desc, or_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.model_config import ModelConfig
from app.models.provider_key import ProviderKey
from app.models.system_setting import SystemSetting
from app.models.transaction import CreditTransaction, TransactionType
from app.models.user import User, UserRole
from app.security.encryption import encrypt


async def list_users(
    db: AsyncSession, search: str | None = None, is_active: bool | None = None,
    page: int = 1, size: int = 20,
) -> tuple[list[User], int]:
    query = select(User)
    count_q = select(func.count(User.id))
    if search:
        query = query.where(User.email.ilike(f"%{search}%"))
        count_q = count_q.where(User.email.ilike(f"%{search}%"))
    if is_active is not None:
        query = query.where(User.is_active == is_active)
        count_q = count_q.where(User.is_active == is_active)
    total = (await db.execute(count_q)).scalar()
    items = (await db.execute(
        query.order_by(desc(User.created_at)).offset((page - 1) * size).limit(size)
    )).scalars().all()
    return list(items), total


async def update_user_admin(db: AsyncSession, user_id: str, data: dict) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    for key, val in data.items():
        if val is not None:
            setattr(user, key, val)
    await db.flush()
    return user


async def add_credits(db: AsyncSession, user_id: str, amount: int, note: str = "") -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.credit_balance += amount
    txn = CreditTransaction(
        user_id=user.id,
        amount=amount,
        balance_after=user.credit_balance,
        type=TransactionType.ADMIN_ADJUST,
        note=note,
    )
    db.add(txn)
    await db.flush()
    return user


async def get_setting(db: AsyncSession, key: str) -> SystemSetting | None:
    result = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
    return result.scalar_one_or_none()


async def set_setting(db: AsyncSession, key: str, value: str) -> SystemSetting:
    result = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = value
    else:
        setting = SystemSetting(key=key, value=value)
        db.add(setting)
    await db.flush()
    return setting


async def create_provider_key(db: AsyncSession, data: dict) -> ProviderKey:
    pk = ProviderKey(
        provider=data["provider"],
        label=data["label"],
        encrypted_key=encrypt(data["api_key"]),
        base_url=data["base_url"],
        proxy_url=data.get("proxy_url"),
        priority=data.get("priority", 10),
    )
    db.add(pk)
    await db.flush()
    return pk


async def list_provider_keys(db: AsyncSession) -> list[ProviderKey]:
    result = await db.execute(select(ProviderKey).order_by(ProviderKey.provider, ProviderKey.priority))
    return list(result.scalars().all())


async def delete_provider_key(db: AsyncSession, key_id: str) -> None:
    result = await db.execute(select(ProviderKey).where(ProviderKey.id == key_id))
    pk = result.scalar_one_or_none()
    if pk is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider key not found")
    pk.is_active = False
    await db.flush()


async def create_model_config(db: AsyncSession, data: dict) -> ModelConfig:
    existing = await db.execute(
        select(ModelConfig).where(
            ModelConfig.provider == data["provider"],
            ModelConfig.model_id == data["model_id"],
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Model config already exists")
    mc = ModelConfig(**data)
    db.add(mc)
    await db.flush()
    return mc


async def list_model_configs(db: AsyncSession) -> list[ModelConfig]:
    result = await db.execute(select(ModelConfig).order_by(ModelConfig.provider, ModelConfig.model_id))
    return list(result.scalars().all())


async def update_model_config(db: AsyncSession, model_id: str, data: dict) -> ModelConfig:
    result = await db.execute(
        select(ModelConfig).where(ModelConfig.id == model_id)
    )
    mc = result.scalar_one_or_none()
    if mc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model config not found")
    for key, val in data.items():
        if val is not None:
            setattr(mc, key, val)
    await db.flush()
    return mc
