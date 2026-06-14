-- =============================================================================
-- Grocery retail platform — transactional schema (PostgreSQL)
-- =============================================================================
-- This is the system-of-record for users, the product catalog (price/stock),
-- carts, and orders. Vector/semantic search lives in MongoDB; the two are
-- joined by `products.sku`.
--
-- Security note: this DDL runs as the DB owner at init time. The AI agent NEVER
-- connects with this role — it reaches every table only through MCP Toolbox,
-- which uses the least-privilege roles defined in 01_roles.sql.
-- =============================================================================

CREATE TABLE users (
  id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  -- `oidc_sub` maps to the OIDC `sub` claim; `username` maps to
  -- `preferred_username`. Toolbox binds one of these from the verified token
  -- into the authenticated `username` parameter (see toolbox/tools.yaml).
  oidc_sub    TEXT UNIQUE NOT NULL,
  username    TEXT UNIQUE NOT NULL,
  email       TEXT UNIQUE NOT NULL,
  is_admin    BOOLEAN NOT NULL DEFAULT FALSE,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Transactional product catalog. Price and stock are authoritative HERE, never
-- supplied by the LLM. `store_region` powers the SDK bound-parameter demo.
CREATE TABLE products (
  id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  sku           TEXT UNIQUE NOT NULL,            -- shared join key with Mongo inventory
  name          TEXT NOT NULL,
  category      TEXT NOT NULL,
  sub_category  TEXT,
  brand         TEXT,
  price         NUMERIC(10,2) NOT NULL CHECK (price >= 0),
  stock_qty     INT NOT NULL DEFAULT 0 CHECK (stock_qty >= 0),
  store_region  TEXT NOT NULL DEFAULT 'us-west', -- tenant/region (bound param demo)
  active        BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE carts (
  id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id       BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  status        TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','checked_out')),
  store_region  TEXT NOT NULL DEFAULT 'us-west',
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
  -- "one open cart per user" is enforced by a partial unique index in 03_indexes.sql
);

CREATE TABLE cart_items (
  id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  cart_id     BIGINT NOT NULL REFERENCES carts(id) ON DELETE CASCADE,
  product_id  BIGINT NOT NULL REFERENCES products(id),
  quantity    INT NOT NULL CHECK (quantity > 0),
  unit_price  NUMERIC(10,2) NOT NULL,           -- snapshot of products.price at add time
  UNIQUE (cart_id, product_id)
);

CREATE TABLE orders (
  id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id       BIGINT NOT NULL REFERENCES users(id),
  total         NUMERIC(12,2) NOT NULL,
  status        TEXT NOT NULL DEFAULT 'placed'
                  CHECK (status IN ('placed','shipped','delivered','cancelled')),
  store_region  TEXT NOT NULL,
  placed_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE order_items (
  id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  order_id    BIGINT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  product_id  BIGINT NOT NULL REFERENCES products(id),
  name        TEXT NOT NULL,                    -- denormalized snapshot
  quantity    INT NOT NULL CHECK (quantity > 0),
  unit_price  NUMERIC(10,2) NOT NULL
);
