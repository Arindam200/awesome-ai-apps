import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.routes import router
from app.config import settings
from app.db import Base, SessionLocal, engine
from app.models import PipelineRun, Project  # noqa: F401 — register models
from app.projects_loader import load_projects
from app.scheduler import scheduler, schedule_all

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    if settings.feedback_secret == "dev-insecure-change-me":
        logger.warning("FEEDBACK_SECRET is the insecure default — set a random value in production")
    db = SessionLocal()
    try:
        load_projects(db)
    finally:
        db.close()
    scheduler.start()
    schedule_all()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="Maintainer Brief", lifespan=lifespan)

# Allow the configured frontend origin (prod) plus local dev ports.
_origins = sorted({settings.app_url.rstrip("/"), "http://localhost:3000", "http://localhost:3005"})
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.get("/health")
def health():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        logger.exception("health: db check failed")
        db_ok = False
    return {"ok": db_ok, "db": db_ok}
