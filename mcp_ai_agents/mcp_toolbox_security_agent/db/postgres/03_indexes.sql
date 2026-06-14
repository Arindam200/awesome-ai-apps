-- =============================================================================
-- Indexes & constraints
-- =============================================================================

-- Enforce "at most one OPEN cart per user". Implemented as a partial unique
-- index (a table-level UNIQUE ... WHERE constraint is not valid SQL). The
-- add_to_cart tool relies on this as its ON CONFLICT arbiter.
CREATE UNIQUE INDEX one_open_cart_per_user
  ON carts (user_id)
  WHERE status = 'open';

-- Lookup helpers for the customer tools.
CREATE INDEX idx_cart_items_cart        ON cart_items (cart_id);
CREATE INDEX idx_order_items_order      ON order_items (order_id);
CREATE INDEX idx_orders_user            ON orders (user_id);
CREATE INDEX idx_products_active_region ON products (store_region, active);
