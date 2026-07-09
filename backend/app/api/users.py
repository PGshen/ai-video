from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin_user
from app.db import get_async_session
from app.models.user import User
from app.schemas.user import (
    ResetPasswordRequest,
    USER_ROLES,
    UserCreate,
    UserListResponse,
    UserResponse,
    UserUpdate,
)
from app.security import CurrentUser, hash_password

router = APIRouter(prefix="/api/users", tags=["users"])


def _now():
    return datetime.now(timezone.utc)


def _validate_role(role: str) -> None:
    if role not in USER_ROLES:
        raise HTTPException(status_code=422, detail="role must be admin or user")


async def _get_user_or_404(db: AsyncSession, user_id: UUID) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("", response_model=UserListResponse)
async def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_async_session),
    _: CurrentUser = Depends(require_admin_user),
):
    count_stmt = select(func.count()).select_from(User)
    total = (await db.execute(count_stmt)).scalar_one()
    result = await db.execute(
        select(User)
        .order_by(User.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return {"items": result.scalars().all(), "total": total}


@router.post("", response_model=UserResponse, status_code=201)
async def create_user(
    body: UserCreate,
    db: AsyncSession = Depends(get_async_session),
    _: CurrentUser = Depends(require_admin_user),
):
    username = body.username.strip()
    if not username:
        raise HTTPException(status_code=422, detail="username is required")
    _validate_role(body.role)

    existing = await db.execute(select(User.id).where(User.username == username))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="用户名已存在")

    user = User(
        username=username,
        password_hash=hash_password(body.password),
        display_name=body.display_name.strip() if body.display_name else None,
        role=body.role,
        is_active=body.is_active,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    body: UserUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: CurrentUser = Depends(require_admin_user),
):
    user = await _get_user_or_404(db, user_id)
    update_data = body.model_dump(exclude_unset=True)
    if "role" in update_data and update_data["role"] is not None:
        _validate_role(update_data["role"])
    if (
        str(user.id) == current_user.id
        and update_data.get("is_active") is False
    ):
        raise HTTPException(status_code=409, detail="不能禁用当前登录用户")

    for field, value in update_data.items():
        if field == "display_name":
            value = value.strip() if isinstance(value, str) and value.strip() else None
        setattr(user, field, value)
    user.updated_at = _now()
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/{user_id}/reset-password", response_model=UserResponse)
async def reset_password(
    user_id: UUID,
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_async_session),
    _: CurrentUser = Depends(require_admin_user),
):
    user = await _get_user_or_404(db, user_id)
    user.password_hash = hash_password(body.password)
    user.updated_at = _now()
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/{user_id}/disable", response_model=UserResponse)
async def disable_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: CurrentUser = Depends(require_admin_user),
):
    user = await _get_user_or_404(db, user_id)
    if str(user.id) == current_user.id:
        raise HTTPException(status_code=409, detail="不能禁用当前登录用户")
    user.is_active = False
    user.updated_at = _now()
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/{user_id}/enable", response_model=UserResponse)
async def enable_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_async_session),
    _: CurrentUser = Depends(require_admin_user),
):
    user = await _get_user_or_404(db, user_id)
    user.is_active = True
    user.updated_at = _now()
    await db.commit()
    await db.refresh(user)
    return user
