from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.api_key import ApiKey
from app.security.api_key import generate_api_key, hash_api_key
from app.services.auth_service import hash_password


async def get_user_by_id(db: AsyncSession, user_id: str) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


async def update_user(db: AsyncSession, user: User, email: str | None, password: str | None) -> User:
    if email is not None:
        result = await db.execute(select(User).where(User.email == email, User.id != user.id))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use")
        user.email = email
    if password is not None:
        user.hashed_password = hash_password(password)
    await db.flush()
    return user


async def list_user_keys(db: AsyncSession, user_id: str) -> list[ApiKey]:
    result = await db.execute(
        select(ApiKey).where(ApiKey.user_id == user_id, ApiKey.is_active == True).order_by(ApiKey.created_at.desc())
    )
    return list(result.scalars().all())


async def create_user_key(db: AsyncSession, user_id: str, name: str) -> dict:
    count_result = await db.execute(
        select(func.count(ApiKey.id)).where(ApiKey.user_id == user_id, ApiKey.is_active == True)
    )
    active_count = count_result.scalar()
    if active_count >= 10:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Maximum 10 active API keys")

    full_key, key_prefix, key_hash = generate_api_key()
    api_key = ApiKey(
        user_id=user_id,
        key_prefix=key_prefix,
        key_hash=key_hash,
        name=name,
    )
    db.add(api_key)
    await db.flush()
    return {
        "id": api_key.id,
        "key_prefix": key_prefix,
        "full_key": full_key,
        "name": name,
        "created_at": api_key.created_at,
    }


async def delete_user_key(db: AsyncSession, user_id: str, key_id: str) -> None:
    result = await db.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user_id)
    )
    key = result.scalar_one_or_none()
    if key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    key.is_active = False
    await db.flush()
