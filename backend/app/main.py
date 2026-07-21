import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from temporalio.client import Client as TemporalClient
from sqlalchemy import func, select
from app.api import (
    auth,
    topics,
    projects,
    reviews,
    worker_tasks,
    ai_call_records,
    ai_model_settings,
    users,
    tts_settings,
)
from app.api.prompt_components import router as prompt_components_router
from app.api.style_templates import router as style_templates_router
from app.config import settings
from app.db import AsyncSessionLocal
from app.deps import set_temporal_client, get_temporal_client  # re-export for compat
from app.models.user import User
from app.security import hash_password

logging.basicConfig(level=logging.INFO)


async def bootstrap_admin_user() -> None:
    username = settings.AUTH_BOOTSTRAP_ADMIN_USERNAME.strip()
    password = settings.AUTH_BOOTSTRAP_ADMIN_PASSWORD
    if not username or not password:
        return

    async with AsyncSessionLocal() as db:
        total = (await db.execute(select(func.count()).select_from(User))).scalar_one()
        if total:
            return
        db.add(
            User(
                username=username,
                password_hash=hash_password(password),
                display_name="管理员",
                role="admin",
                is_active=True,
            )
        )
        await db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = await TemporalClient.connect(settings.TEMPORAL_ADDRESS)
    set_temporal_client(client)
    await bootstrap_admin_user()
    yield


app = FastAPI(title="AI Video Workflow Platform", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


app.include_router(topics.router)
app.include_router(projects.router)
app.include_router(reviews.router)
app.include_router(worker_tasks.router)
app.include_router(prompt_components_router)
app.include_router(style_templates_router)
app.include_router(ai_call_records.router)
app.include_router(ai_model_settings.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(tts_settings.router)
