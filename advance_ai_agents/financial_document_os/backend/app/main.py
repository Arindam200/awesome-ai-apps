import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.api.routes import router
from app.config import settings
from app.db import Base, SessionLocal, engine
from app.models import Project  # noqa: F401 — register all models

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _ensure_project():
    db = SessionLocal()
    try:
        if not db.scalar(select(Project).limit(1)):
            db.add(Project(slug="workspace", name="Financial Document OS", config={}))
            db.commit()
            logger.info("created default workspace project")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # register every model on Base before create_all
    import app.models  # noqa: F401

    Base.metadata.create_all(engine)
    _ensure_project()
    yield


app = FastAPI(title="Financial Document OS", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.app_url, "http://localhost:3006", "http://localhost:3005"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.get("/health")
def health():
    return {"ok": True, "editing_enabled": settings.editing_enabled}
