# Security Fixes

This file tracks the vulnerability findings from the security review and the
fixes applied for each one. It is maintained alongside the code changes — see
the checklist at the bottom for current status.

All paths below are relative to `awesome-ai-apps/`.

---

## CRITICAL

### SEC-001 — Unvalidated LLM-generated SQL execution
**Project:** `simple_ai_agents/talk_to_db`
**Status:** ✅ Fixed

- Added `simple_ai_agents/talk_to_db/sql_validator.py`: parses generated SQL
  with `sqlglot`, rejects anything that isn't a single `SELECT`, rejects
  write/DDL keywords, restricts table access to a whitelist
  (`category`, `product`, `order`, `user`, `order_item`, `product_category`),
  and auto-appends `LIMIT 100` when missing.
- `database.py: execute_query()` now calls `validate_sql()` before the query
  ever reaches `cursor.execute()`. A rejected query never touches the
  database and returns a `"Query rejected: ..."` message instead.
- Added `sqlglot` to `pyproject.toml` dependencies.

### SEC-002 — Database credentials exposed via Streamlit UI
**Project:** `simple_ai_agents/talk_to_db`
**Status:** ✅ Fixed

- `app.py` no longer renders a `st.text_input` for the database connection
  string. The connection string is now read only from the
  `DATABASE_CONNECTION_STRING` environment variable (`.env`, never
  committed). If it's missing, the sidebar shows a setup instruction instead
  of a credential input box.
- `.env.example` updated with the new required variable.

### SEC-004 — Inconsistent SQL validation across projects
**Project:** `mcp_ai_agents/telemetry-mcp-okahu`
**Status:** ✅ Fixed (for the live code path)

- Added `mcp_ai_agents/telemetry-mcp-okahu/sql_validator.py`, the same
  validation pattern as SEC-001 adapted for SQLite and the `users`/`orders`
  schema used by `analyst.py`.
- `analyst.py: execute_query()` now validates before executing, and sets
  `PRAGMA busy_timeout = 5000` (see SEC-005c).
- `main.py` (`/query` endpoint) now returns HTTP 400 with a clear message
  when the LLM-generated SQL is rejected, instead of a generic 500.
- Added `sqlglot` to `requirements.txt`.
- **Deliberately not touched:** `reset_demo.py`'s `BUGGY_ANALYST` string.
  That file is a teaching artifact for a *separate* "self-healing agent"
  demo — it intentionally overwrites `analyst.py` with broken code (wrong
  model name, wrong schema, etc.) so a trace-analysis agent can find and fix
  the bugs. Hardening that injected template would defeat the demo's
  purpose. If `reset_demo.py` is ever run, it will restore `analyst.py`
  *without* the `sql_validator` import — that's expected; re-apply this fix
  after resetting if the demo is repurposed for anything beyond local
  teaching use.

### SEC-008 — Prompt injection in SQL-generation agents
**Project:** `simple_ai_agents/talk_to_db`
**Status:** ✅ Fixed

- `ai_services.py: translate_to_sql()`:
  - User question is capped at 500 characters and rejected if empty.
  - The question is now wrapped in explicit `[QUESTION]...[/QUESTION]`
    delimiters in the prompt, with an explicit system-prompt instruction
    that text inside those markers is untrusted input, never instructions.
  - System prompt explicitly forbids write/DDL statements and
    out-of-schema tables regardless of what the question asks.
  - Model can respond `UNABLE_TO_ANSWER`; the function surfaces that as an
    error instead of forwarding garbage SQL downstream.
  - Any response that doesn't start with `SELECT` is rejected before it's
    returned to the caller.
  - Note: prompt hardening is a mitigation, not the security boundary — the
    real boundary is SEC-001's `sql_validator.validate_sql()`, which runs
    independently of what the LLM produces.

---

## HIGH

### SEC-003 — Hardcoded demo credentials in frontend JS
**Project:** `mcp_ai_agents/mcp_toolbox_security_agent`
**Status:** ✅ Fixed

- `web/static/index.html`: `USERS` object no longer carries a `pw` field —
  only non-secret display metadata (`color`, `label`). `login(u)` now POSTs
  `{username: u}` only.
- `web/app.py`: shared login logic factored into `_login_with_password()`.
  Added a server-side `_DEMO_PASSWORDS` map (overridable via
  `DEMO_ALICE_PASSWORD` etc. env vars) and a new `POST /api/demo/login`
  endpoint that looks up the password server-side and runs the same
  Keycloak token-exchange/session-cookie flow as `/api/login`. The existing
  `/api/login`, `/api/logout`, `/api/me`, and session-cookie mechanism are
  unchanged.
- `auth/keycloak/realm-grocery.json` intentionally left untouched — it's
  server-side seed data, never shipped to the browser.
- **Follow-up fix (post-PR-scan):** GitGuardian flagged that the first pass
  of this fix still hardcoded the three demo users' literal seed passwords
  as `os.environ.get(..., "<password>")`-style *fallback defaults* in
  `web/app.py`. Even as a fallback, a literal password string committed to
  git is a real finding — removed the fallbacks (`_DEMO_PASSWORDS` now
  reads purely from `DEMO_ALICE_PASSWORD`/`DEMO_BOB_PASSWORD`/
  `DEMO_CAROL_PASSWORD`, defaulting to `""` and failing closed with 401 if
  unset). Added those three vars (left blank) to
  `deploy/compose/.env.example` (gitignored `.env`, not committed — set them
  locally to whatever `realm-grocery.json` seeds for each user) and wired
  them through to the `agent-web` service in
  `deploy/compose/docker-compose.yaml`, which was missing them entirely —
  without that, the container would never have seen the env vars and every
  demo login would have 401'd.

### SEC-005 — Missing CORS / security headers
**Project:** `rag_apps/advanced_rag_with_reranking`
**Status:** ✅ Fixed

- `boeing_rag/api.py: _asset_cors_headers()` no longer falls back to `"*"`
  for non-local origins — it now returns `{}` (no CORS header at all) so
  the PDF/page-image asset endpoints don't grant arbitrary cross-origin
  access. `Access-Control-Allow-Headers` tightened from `"*"` to
  `"Range, If-None-Match, If-Modified-Since"`.
- Added `SecurityHeadersMiddleware` setting `X-Content-Type-Options: nosniff`,
  `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`
  on every response. No CSP added (would risk breaking the existing
  frontend fetches).
- Main `CORSMiddleware` config (already scoped to localhost origins) left
  as-is.

### SEC-007 — Weak file upload validation
**Project:** `advance_ai_agents/maintainer_brief`
**Status:** ✅ Fixed

- `backend/app/api/routes.py: upload_document()`: added magic-byte content
  verification (`_UPLOAD_SIGNATURES`) for every allowed suffix (PDF, PNG,
  JPEG, ZIP-based Office formats, legacy OLE formats, TIFF) — a file whose
  bytes don't match its claimed extension is rejected with 422. No new
  dependency (no `python-magic`/libmagic) — implemented as inline signature
  checks so `pip install` alone still works.
- Added a per-user 24h upload rate limit (100 uploads/day) via a DB query
  joining `Document`→`Project` on `owner_id`, rejecting with 429 over the
  limit. This also covers SEC-005b for this endpoint.
- `_safe_name`/`register_document` in `connectors/documents.py` verified
  correct and left unchanged.

---

## MEDIUM

### SEC-006 — JWT stored in localStorage
**Project:** `advance_ai_agents/maintainer_brief`
**Status:** ✅ Fixed (minimal-risk option)

- `frontend/src/lib/api.ts`: `getToken`/`setToken`/`clearToken` now use
  `sessionStorage` instead of `localStorage` — the token is cleared when the
  tab/browser closes instead of persisting indefinitely, shrinking the
  window an XSS payload or shared machine could exploit.
- Full migration to httpOnly cookies was **not** done — it requires
  coordinated backend changes (cookie-setting in the OAuth callback,
  `allow_credentials`/SameSite coordination across the Next.js and FastAPI
  origins) that risk breaking the login flow and were out of scope here.
- Verified the OAuth callback (`frontend/src/app/auth/callback/page.tsx` +
  `backend/app/auth.py`) redirects same-tab (not a popup), so
  `sessionStorage`'s per-tab semantics are safe for this flow.

### SEC-005b — No rate limiting
**Status:** ✅ Fixed for `maintainer_brief` uploads (same change as SEC-007 —
100 uploads/user/24h, no new dependency needed).
Not applied to other projects' endpoints in this pass — see checklist.

### SEC-005c — No query timeout / resource limits
**Status:** ✅ Fixed for both SQL-agent projects.
- `talk_to_db/database.py`: `SET SESSION MAX_EXECUTION_TIME=5000` (5s) before
  each query.
- `telemetry-mcp-okahu/analyst.py`: `PRAGMA busy_timeout = 5000` on the
  sqlite connection.
- LLM call timeouts were **not** added — `ChatNebius`/`OpenAI` client
  construction in both projects doesn't currently set one, and adding it
  requires confirming the installed SDK versions support the `timeout=`
  kwarg. Flagged here as a follow-up rather than guessed at.

---

## LOW-MEDIUM

### SEC-011 — Streamlit debug/config hardening
**Project:** `simple_ai_agents/talk_to_db`
**Status:** ✅ Fixed — added `.streamlit/config.toml`
(`logger.level=error`, `client.showErrorDetails=false`,
`server.maxUploadSize=10`, `server.enableXsrfProtection=true`).

### SEC-012 — ALLOWED_HOSTS not configured
**Status:** ✅ Fixed for `telemetry-mcp-okahu/main.py` — added
`TrustedHostMiddleware` with hosts from an `ALLOWED_HOSTS` env var
(defaults to `localhost,127.0.0.1`).
**Not yet applied** to `boeing_rag/api.py` or `maintainer_brief`'s FastAPI
app — left to the SEC-005/SEC-007 background agents' scope; verify after
they report back.

### SEC-013 — No audit logging
**Status:** ✅ Fixed (lightweight) for both SQL-agent projects — `database.py`
and `analyst.py` now log rejected/succeeded/failed query executions via the
standard `logging` module (no PII/full-query-text logging — just outcome and
row counts, to avoid logging sensitive data generated from user questions).
Not applied to the other projects in this pass — this was scoped to the SQL
execution paths, the highest-risk logging gap.

### SEC-014 — No malware scanning on file upload
**Status:** ❌ Not implemented — documented here instead.
Adding real malware scanning (e.g. ClamAV via `pyclamav`) requires a running
ClamAV daemon and virus-definition updates, which isn't practical to bundle
into these demo repos (`pip install` alone won't provide it, and a stale/
missing daemon would either silently no-op or break uploads). Recommendation
if this is deployed beyond local/demo use: run uploads through a managed
scanning service (e.g. cloud storage's built-in malware scanning, or a
sidecar ClamAV container) rather than an in-process Python scan.

---

## Checklist

- [x] **SEC-001** — `sqlglot` validation added to `talk_to_db`
- [x] **SEC-002** — Connection string UI removed from Streamlit, loads from `.env`
- [x] **SEC-004** — Shared validation pattern applied to `telemetry-mcp-okahu`
- [x] **SEC-008** — Prompt injection safeguards added to `talk_to_db`'s SQL chain
- [x] **SEC-003** — Removed hardcoded credentials from `mcp_toolbox_security_agent` frontend
- [x] **SEC-005** — CORS + security headers fixed for `advanced_rag_with_reranking`
- [x] **SEC-007** — MIME/magic-byte validation added for `maintainer_brief` uploads
- [x] **SEC-006** — Migrated `maintainer_brief` JWT from `localStorage` to `sessionStorage`
- [x] **SEC-005b** — Rate limiting added for `maintainer_brief` uploads
- [x] **SEC-005c** — Query timeouts added to both SQL-agent projects
- [x] **SEC-011** — Streamlit security config for `talk_to_db`
- [x] **SEC-012** — `ALLOWED_HOSTS` added to `telemetry-mcp-okahu`; **not yet applied** to `boeing_rag`/`maintainer_brief` FastAPI apps (follow-up)
- [x] **SEC-013** — Structured logging added to both SQL execution paths (not extended to other projects)
- [ ] **SEC-014** — Malware scanning — intentionally not implemented, see rationale above

### Known follow-ups (not done in this pass)
- `TrustedHostMiddleware` / `ALLOWED_HOSTS` for `boeing_rag/api.py` and `maintainer_brief`'s FastAPI app.
- LLM API call timeouts for `ChatNebius`/`OpenAI` clients (needs SDK-version check first).
- Audit logging beyond the two SQL execution paths.
- Real malware scanning (SEC-014) — needs an external scanning service, not an in-process dependency.
- Full httpOnly-cookie migration for `maintainer_brief` auth (SEC-006's stronger option) — needs a coordinated backend/frontend auth redesign.
