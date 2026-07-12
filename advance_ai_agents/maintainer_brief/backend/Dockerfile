# Maintainer Brief — backend (FastAPI + APScheduler)
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install deps first (cached layer). hatchling needs the package present to
# build, so copy the app tree before installing.
COPY pyproject.toml README.md* ./
COPY app ./app
RUN pip install .

COPY scripts ./scripts

EXPOSE 8000

# One process runs both the API and the APScheduler cron — do NOT scale to
# multiple machines or the weekly job fires N times. Keep min_machines_running=1
# and auto_stop_machines off (see fly.toml).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
