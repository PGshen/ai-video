from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from temporalio.client import Client as TemporalClient
from app.api import topics, projects, reviews, worker_tasks
from app.config import settings

_temporal_client: TemporalClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _temporal_client
    _temporal_client = await TemporalClient.connect(settings.TEMPORAL_ADDRESS)
    yield


def get_temporal_client() -> TemporalClient:
    if _temporal_client is None:
        raise RuntimeError("Temporal client not initialized")
    return _temporal_client


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
