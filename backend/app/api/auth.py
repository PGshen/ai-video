from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_active_user
from app.config import settings
from app.db import get_async_session
from app.models.user import User
from app.schemas.user import CurrentUserResponse, LoginRequest, LoginResponse
from app.security import CurrentUser, create_access_token, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _cookie_max_age() -> int:
    return settings.AUTH_ACCESS_TOKEN_EXPIRE_MINUTES * 60


def set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.AUTH_COOKIE_NAME,
        value=token,
        max_age=_cookie_max_age(),
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite="lax",
        path="/",
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.AUTH_COOKIE_NAME,
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite="lax",
        path="/",
    )


def _current_user_response(user: CurrentUser) -> CurrentUserResponse:
    return CurrentUserResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
        is_active=user.is_active,
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_async_session),
):
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="用户已禁用")

    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    token = create_access_token(user)
    set_auth_cookie(response, token)
    return LoginResponse(
        user=CurrentUserResponse(
            id=str(user.id),
            username=user.username,
            display_name=user.display_name,
            role=user.role,
            is_active=user.is_active,
        )
    )


@router.post("/logout")
async def logout(response: Response):
    clear_auth_cookie(response)
    return {"status": "ok"}


@router.get("/me", response_model=CurrentUserResponse)
async def me(user: CurrentUser = Depends(require_active_user)):
    return _current_user_response(user)
