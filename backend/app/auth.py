from fastapi import Cookie, Depends, HTTPException

from app.config import settings
from app.security import CurrentUser, current_user_from_token


def _unauthorized() -> HTTPException:
    return HTTPException(status_code=401, detail="Authentication required")


async def get_current_user(
    session_token: str | None = Cookie(None, alias=settings.AUTH_COOKIE_NAME),
) -> CurrentUser:
    if not session_token:
        raise _unauthorized()
    try:
        return current_user_from_token(session_token)
    except ValueError as exc:
        raise _unauthorized() from exc


async def require_active_user(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    if not current_user.is_active:
        raise HTTPException(status_code=403, detail="User is disabled")
    return current_user


async def require_admin_user(
    current_user: CurrentUser = Depends(require_active_user),
) -> CurrentUser:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin permission required")
    return current_user
