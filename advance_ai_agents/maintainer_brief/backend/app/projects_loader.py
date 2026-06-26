"""Load projects/*.yaml into the projects table. YAML is the source of truth."""

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import PROJECTS_DIR
from app.models import Project


def load_projects(db: Session) -> list[Project]:
    loaded = []
    for path in sorted(PROJECTS_DIR.glob("*.yaml")):
        cfg = yaml.safe_load(path.read_text())
        if not cfg or "slug" not in cfg:
            continue
        project = db.scalar(select(Project).where(Project.slug == cfg["slug"]))
        if project is None:
            project = Project(slug=cfg["slug"], name=cfg.get("name", cfg["slug"]), config=cfg)
            db.add(project)
        else:
            project.name = cfg.get("name", cfg["slug"])
            project.config = cfg
        loaded.append(project)
    db.commit()
    return loaded
