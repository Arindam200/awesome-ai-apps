-- =============================================================================
-- Least-privilege database roles  (SECURITY MECHANISM #6)
-- =============================================================================
-- MCP Toolbox connects to Postgres as one of these roles — NEVER as a superuser
-- and never as the schema owner. Each Toolbox `source` maps to exactly one role,
-- so the blast radius of any single tool is capped by SQL GRANTs *below* the tool
-- layer. Even if the LLM were tricked into emitting a destructive statement, the
-- role simply lacks the privilege.
--
-- DEMO PASSWORDS: these literals are for the local docker-compose demo only and
-- MUST match deploy/compose/.env.example. In the GKE reference architecture the
-- Postgres source is `cloud-sql-postgres` with NO user/password at all — Toolbox
-- authenticates via IAM / Workload Identity (mechanism #7), so no password like
-- these ever exists in production.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- toolbox_app — the customer-facing transactional role (read/write, scoped)
-- ---------------------------------------------------------------------------
-- Can read the catalog and users, fully manage carts, and APPEND orders.
-- Deliberately CANNOT: modify the product catalog, delete/modify orders, or
-- run any DDL. Customers cannot rewrite prices or erase order history.
CREATE ROLE toolbox_app LOGIN PASSWORD 'app_demo_pw_change_me';
GRANT CONNECT ON DATABASE grocery TO toolbox_app;
GRANT USAGE  ON SCHEMA public      TO toolbox_app;

GRANT SELECT                         ON users, products      TO toolbox_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON carts, cart_items    TO toolbox_app;
GRANT SELECT, INSERT                 ON orders, order_items  TO toolbox_app;
-- identity columns need sequence usage for INSERTs
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO toolbox_app;
-- NOTE: intentionally NO UPDATE/DELETE on products (catalog is read-only to customers)
-- NOTE: intentionally NO UPDATE/DELETE on orders   (orders are immutable to customers)

-- ---------------------------------------------------------------------------
-- toolbox_ro — read-only role (proves per-source role separation)
-- ---------------------------------------------------------------------------
CREATE ROLE toolbox_ro LOGIN PASSWORD 'ro_demo_pw_change_me';
GRANT CONNECT ON DATABASE grocery TO toolbox_ro;
GRANT USAGE  ON SCHEMA public      TO toolbox_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO toolbox_ro;

-- ---------------------------------------------------------------------------
-- toolbox_admin — privileged role used ONLY by the admin Toolbox source
-- ---------------------------------------------------------------------------
-- Backs the admin-only tools (update_inventory, view_all_orders) which are
-- themselves gated by authRequired (mechanism #3). Still NOT a superuser and
-- still cannot run DDL.
CREATE ROLE toolbox_admin LOGIN PASSWORD 'admin_demo_pw_change_me';
GRANT CONNECT ON DATABASE grocery TO toolbox_admin;
GRANT USAGE  ON SCHEMA public      TO toolbox_admin;
GRANT SELECT, UPDATE ON products TO toolbox_admin;
GRANT SELECT, UPDATE ON orders   TO toolbox_admin;
GRANT SELECT         ON users, order_items, carts, cart_items TO toolbox_admin;

-- ---------------------------------------------------------------------------
-- Pin search_path = public for every service role (robustness / explicitness).
-- These roles own no schema, so unqualified table names must resolve to public.
-- ---------------------------------------------------------------------------
ALTER ROLE toolbox_app   SET search_path = public;
ALTER ROLE toolbox_ro    SET search_path = public;
ALTER ROLE toolbox_admin SET search_path = public;
