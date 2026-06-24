from fastapi import Header, HTTPException
from app.config import settings


async def verify_api_key(x_api_key: str | None = Header(None, alias="X-API-Key")) -> None:
    if x_api_key is None or x_api_key != settings.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")
