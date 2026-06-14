-- =============================================================================
-- Identity seed (runs at DB init)
-- =============================================================================
-- Three identities matching the Keycloak realm (auth/keycloak/realm-grocery.json):
--   alice — regular customer (will have an OPEN cart after catalog bootstrap)
--   bob   — regular customer (will have a PLACED order)  <-- cross-user demo target
--   carol — admin (is_admin = TRUE)
--
-- Toolbox binds the authenticated `username` parameter from the token's
-- `preferred_username` claim (alice/bob/carol), so these usernames are the
-- deterministic join between identity and data.
--
-- The product CATALOG and alice's cart / bob's order are loaded AFTER the stack
-- is healthy, by scripts/build_catalog.py (it derives an aligned catalog from
-- grocery_store.inventory.json into BOTH Postgres and MongoDB, then runs
-- db/postgres/90_demo_cart_order.sql). Catalog data can't live in an init script
-- because it depends on Mongo and the 70MB embeddings file being available.
-- =============================================================================

INSERT INTO users (oidc_sub, username, email, is_admin) VALUES
  ('alice-sub-0001', 'alice', 'alice@example.com', FALSE),
  ('bob-sub-0002',   'bob',   'bob@example.com',   FALSE),
  ('carol-sub-0003', 'carol', 'carol@example.com', TRUE);
