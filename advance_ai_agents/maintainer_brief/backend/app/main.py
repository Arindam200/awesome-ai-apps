import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.db import Base, SessionLocal, engine
from app.models import PipelineRun, Project  # noqa: F401 — register models
from app.projects_loader import load_projects
from app.scheduler import scheduler, schedule_all

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        load_projects(db)
    finally:
        db.close()
    scheduler.start()
    schedule_all()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="Maintainer Intelligence Brief", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3005"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.get("/health")
def health():
    return {"ok": True}
