from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import topics, projects, reviews, worker_tasks
from app.config import settings

app = FastAPI(title="AI Video Workflow Platform", version="0.1.0")

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
