# Deploying Maintainer Brief

Two ways to run it in production. The app is a FastAPI backend (with an in-process
APScheduler cron) + a Next.js frontend + Postgres.

> **One hard constraint:** the weekly/daily brief cron runs *inside* the backend
> process. Run **exactly one** backend instance (`min_machines_running = 1`,
> `auto_stop_machines = false`). Scaling the backend horizontally would send each
> brief multiple times.

---

## Option A — Self-host (Docker, one command)

```bash
cp .env.example .env         # fill in GITHUB_TOKEN + an LLM key (OPENAI_API_KEY)
docker compose -f docker-compose.selfhost.yml up --build
```

Open http://localhost:3005. Postgres, backend (:8000), and frontend (:3005) all
come up together. This is the path an HN reader will try — it works with zero
paid services beyond your own LLM key.

---

## Option B — Hosted (Neon + Fly + Vercel)

This is the setup for running it *as a service* for other maintainers. Each step
you must do by hand (creating accounts / apps) is called out.

### 1. Database — Neon
1. Create a project at https://neon.tech and copy the **pooled** connection string.
2. Convert it to the psycopg URL form:
   `postgresql+psycopg://USER:PASS@ep-xxx-pooler.REGION.aws.neon.tech/db?sslmode=require`
3. You'll set this as `DATABASE_URL` on the backend (step 3). Tables are created
   automatically on first boot.

### 2. Email — Resend
1. At https://resend.com, add and verify your sending domain (SPF/DKIM).
   **Start this on day 1** — DNS + warmup take time.
2. Grab an API key → `RESEND_API_KEY`. Set `NEWSLETTER_FROM="Maintainer Brief <brief@yourdomain.com>"`.

### 3. Backend — Fly.io
From `backend/`:
```bash
fly launch --no-deploy                      # uses fly.toml; pick an app name
fly secrets set \
  GITHUB_TOKEN=...  OPENAI_API_KEY=...  DATABASE_URL="postgresql+psycopg://..." \
  RESEND_API_KEY=...  FEEDBACK_SECRET="$(python -c 'import secrets;print(secrets.token_urlsafe(32))')" \
  APP_URL=https://YOUR-FRONTEND.vercel.app
fly deploy
```
- Update `API_PUBLIC_URL` in `fly.toml` (or as a secret) to your real Fly URL so
  the email feedback links resolve.
- `/health` returns `{"ok": true, "db": true}` when the DB is reachable.

### 4. Frontend — Vercel
1. Import the repo, set **Root Directory** to `frontend/`.
2. Env var: `NEXT_PUBLIC_API_URL=https://YOUR-BACKEND.fly.dev` (build-time).
3. Deploy. Then set the backend's `APP_URL` to this Vercel URL (CORS + email links).

### 5. Verify
- Create a project in the UI → **Run brief now** → the brief renders with your
  repo's live triage/ship-it/people sections.
- Send a test from **Compose** → it lands in your inbox; the 👍/👎 links record
  (check `GET /feedback/summary?brief_id=...`).

---

## What's built vs. what's next

**Production-ready now:** the v2 signal engine, quiet-week skip, one-click signed
feedback (the dogfood metric), health check, Docker/Fly/Vercel configs, CORS +
secrets wiring.

**Not yet (needs your accounts / a follow-up):**
- **Auth** (Better Auth + a GitHub OAuth app) so maintainers sign in and connect
  their own repo — the app currently manages projects without per-user accounts.
- **No-signin instant repo preview** on the landing page.
- **Alembic** migrations (today the schema is created via `create_all`, which is
  fine until the first schema change against a live DB).

See `REDESIGN_PLAN.md` / the office-hours design doc for the full roadmap.

---

## Environment variables

| Var | Required | Notes |
|---|---|---|
| `GITHUB_TOKEN` | ✅ | Reads repo state; raises API limit to 5k/hr. |
| `OPENAI_API_KEY` | ✅ (default provider) | Brief synthesis. |
| `LLM_PROVIDER` | – | `openai` (default) / `nebius` / `anthropic`. |
| `DATABASE_URL` | ✅ | Neon pooled URL in prod. |
| `RESEND_API_KEY` | for sending | Verify a domain in prod. |
| `APP_URL` | ✅ | Frontend origin (CORS + email links). |
| `API_PUBLIC_URL` | ✅ | This backend's public URL (feedback links). |
| `NEXT_PUBLIC_API_URL` | ✅ | Backend URL, baked into the frontend build. |
| `FEEDBACK_SECRET` | ✅ prod | Random 32+ char string; signs feedback links. |
| `UNSILOED_API_KEY` | optional | Only for PDF upload/extraction. |
