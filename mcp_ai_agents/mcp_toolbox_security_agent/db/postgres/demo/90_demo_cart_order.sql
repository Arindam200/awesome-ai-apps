-- =============================================================================
-- Demo cart + order seed  (runs AFTER scripts/build_catalog.py loads the catalog)
-- =============================================================================
-- References SKU-000001 / SKU-000002, which the catalog builder always creates.
-- Idempotent-ish: safe to re-run on a fresh DB. Gives the live demo concrete
-- state — alice has an open cart, bob has a placed order (the cross-user target).
-- =============================================================================

-- alice: OPEN cart with 2 units of the first catalog product.
WITH a AS (SELECT id FROM users WHERE username = 'alice'),
     c AS (
       INSERT INTO carts (user_id, status, store_region)
       SELECT id, 'open', 'us-west' FROM a
       ON CONFLICT (user_id) WHERE status = 'open' DO NOTHING
       RETURNING id
     ),
     cart AS (
       SELECT id FROM c
       UNION ALL
       SELECT carts.id FROM carts JOIN a ON a.id = carts.user_id WHERE carts.status = 'open'
       LIMIT 1
     )
INSERT INTO cart_items (cart_id, product_id, quantity, unit_price)
SELECT cart.id, p.id, 2, p.price
FROM cart, products p
WHERE p.sku = 'SKU-000001'
ON CONFLICT (cart_id, product_id) DO NOTHING;

-- bob: PLACED order with 2 units of the second catalog product.
WITH b AS (SELECT id FROM users WHERE username = 'bob'),
     o AS (
       INSERT INTO orders (user_id, total, store_region)
       SELECT b.id, 2 * p.price, 'us-west'
       FROM b, products p WHERE p.sku = 'SKU-000002'
       RETURNING id
     )
INSERT INTO order_items (order_id, product_id, name, quantity, unit_price)
SELECT o.id, p.id, p.name, 2, p.price
FROM o, products p
WHERE p.sku = 'SKU-000002';
