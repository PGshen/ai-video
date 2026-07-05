import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from temporalio.client import Client as TemporalClient
from app.api import topics, projects, reviews, worker_tasks, ai_call_records
from app.api.prompt_components import router as prompt_components_router
from app.config import settings
from app.deps import set_temporal_client, get_temporal_client  # re-export for compat

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = await TemporalClient.connect(settings.TEMPORAL_ADDRESS)
    set_temporal_client(client)
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
app.include_router(ai_call_records.router)
