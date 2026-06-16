#!/usr/bin/env python3
"""
Build an aligned product catalog in BOTH PostgreSQL and MongoDB from the existing
grocery_store.inventory.json embeddings file.

Why this exists
---------------
Vector/semantic search runs on MongoDB (it has the Gemini embeddings); price,
stock, carts and orders live in PostgreSQL. For the agent to add a *searched*
product to the cart, the SKU returned by Mongo must exist in Postgres. So both
stores are seeded from ONE source of truth here, with matching SKUs.

This runs at bootstrap time (after the stack is healthy), NOT as a DB init
script, because it needs Mongo and the 70MB embeddings file.

Idempotent: it truncates the catalog tables/collection and reloads.

Env:
  PG_DSN        postgresql://toolbox_owner:pw@host:5432/grocery   (a role that can write products)
  MONGO_URI     mongodb://host:27017
  INVENTORY     path to grocery_store.inventory.json (default: ./grocery_store.inventory.json)
  CATALOG_SIZE  number of products to load (default: 150)
  EMBED_DIM     expected embedding dimension (default: 3072)
"""
import json
import os
import sys

CATALOG_SIZE = int(os.environ.get("CATALOG_SIZE", "150"))
EMBED_DIM = int(os.environ.get("EMBED_DIM", "3072"))
INVENTORY = os.environ.get("INVENTORY", "grocery_store.inventory.json")
# The 67MB embeddings dataset is not committed everywhere; download it on demand.
INVENTORY_URL = os.environ.get(
    "INVENTORY_URL",
    "https://raw.githubusercontent.com/shivaylamba/"
    "mcp-toolbox-ecommerce-best-practices/main/grocery_store.inventory.json",
)


def ensure_inventory(path):
    """Download the embeddings dataset if it isn't present locally."""
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return
    import urllib.request
    print(f"[build_catalog] {path} not found — downloading ~67MB from {INVENTORY_URL}")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    urllib.request.urlretrieve(INVENTORY_URL, path)
    print(f"[build_catalog] download complete ({os.path.getsize(path) // (1024*1024)} MB)")


def stream_products(path, want, dim):
    """Yield up to `want` product dicts (with a valid `dim`-length embedding)
    from a large JSON array, without loading the whole file into memory."""
    decoder = json.JSONDecoder()
    with open(path, "r") as f:
        # find the opening bracket of the array
        chunk = f.read(1 << 16)
        i = chunk.find("[")
        chunk = chunk[i + 1:]
        yielded = 0
        while yielded < want:
            chunk = chunk.lstrip().lstrip(",").lstrip()
            if not chunk or chunk[0] == "]":
                more = f.read(1 << 16)
                if not more:
                    break
                chunk += more
                continue
            try:
                obj, end = decoder.raw_decode(chunk)
            except json.JSONDecodeError:
                more = f.read(1 << 16)
                if not more:
                    break
                chunk += more
                continue
            chunk = chunk[end:]
            emb = obj.get("gemini_embedding")
            if isinstance(emb, list) and len(emb) == dim:
                yield obj
                yielded += 1


def main():
    try:
        import psycopg
    except ImportError:
        sys.exit("psycopg (v3) is required: pip install 'psycopg[binary]'")
    try:
        from pymongo import MongoClient
        from pymongo.operations import SearchIndexModel
    except ImportError:
        sys.exit("pymongo>=4.5 is required: pip install pymongo")

    pg_dsn = os.environ["PG_DSN"]
    mongo_uri = os.environ["MONGO_URI"]

    ensure_inventory(INVENTORY)
    print(f"[build_catalog] reading up to {CATALOG_SIZE} products from {INVENTORY}")
    rows = []
    docs = []
    for idx, obj in enumerate(stream_products(INVENTORY, CATALOG_SIZE, EMBED_DIM), start=1):
        sku = f"SKU-{idx:06d}"
        name = (obj.get("product") or "Unknown product").strip()
        category = (obj.get("category") or "General").strip()
        sub_category = (obj.get("sub_category") or "").strip() or None
        brand = (obj.get("brand") or "").strip() or None
        try:
            price = round(float(obj.get("sale_price") or 0) or 1.0, 2)
        except (TypeError, ValueError):
            price = 1.0
        if price <= 0:
            price = 1.0
        stock = 50 + (idx % 200)  # deterministic, non-zero
        rows.append((sku, name, category, sub_category, brand, price, stock, "us-west"))
        # Mongo doc: keep the searchable fields + embedding, add the join key.
        docs.append({
            "sku": sku,
            "product": name,
            "category": category,
            "sub_category": sub_category,
            "brand": brand,
            "sale_price": price,
            "type": obj.get("type"),
            "rating": obj.get("rating"),
            "description": obj.get("description"),
            "gemini_embedding": obj["gemini_embedding"],
        })

    if len(rows) < 2:
        sys.exit(f"[build_catalog] only found {len(rows)} valid products; need >= 2")
    print(f"[build_catalog] prepared {len(rows)} products (SKU-000001..SKU-{len(rows):06d})")

    # RESET=1 is the ONLY way this script destroys data. By default it is
    # idempotent and NEVER touches existing carts/orders — so re-running
    # bootstrap on a populated DB can't wipe user transactions.
    reset = os.environ.get("RESET", "").lower() in ("1", "true", "yes")

    # --- PostgreSQL: load the catalog (only if empty, or RESET) --------------
    with psycopg.connect(pg_dsn) as conn:
        have = conn.execute("SELECT count(*) FROM products").fetchone()[0]
        if reset or have == 0:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE products RESTART IDENTITY CASCADE;")  # cascades to cart_items/order_items
                cur.executemany(
                    """INSERT INTO products
                       (sku, name, category, sub_category, brand, price, stock_qty, store_region)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                    rows,
                )
            conn.commit()
            print(f"[build_catalog] postgres: loaded {len(rows)} products" + (" (RESET)" if reset else ""))
        else:
            print(f"[build_catalog] postgres: {have} products already present — skipping "
                  f"catalog load (use RESET=1 to force)")

    # --- Demo cart/order seed (only on a fresh DB, or RESET) -----------------
    demo_sql = os.path.join(os.path.dirname(__file__), "..", "db", "postgres", "demo", "90_demo_cart_order.sql")
    if os.path.exists(demo_sql):
        with psycopg.connect(pg_dsn) as conn:
            carts = conn.execute("SELECT count(*) FROM carts").fetchone()[0]
            orders = conn.execute("SELECT count(*) FROM orders").fetchone()[0]
            if reset:
                conn.execute("TRUNCATE cart_items, carts, order_items, orders RESTART IDENTITY CASCADE;")
                conn.execute(open(demo_sql).read())
                conn.commit()
                print("[build_catalog] postgres: RESET — reseeded alice's cart + bob's order")
            elif carts == 0 and orders == 0:
                conn.execute(open(demo_sql).read())
                conn.commit()
                print("[build_catalog] postgres: seeded alice's cart + bob's order")
            else:
                print(f"[build_catalog] postgres: {carts} cart(s) / {orders} order(s) exist — "
                      f"leaving transactional data UNTOUCHED (use RESET=1 to wipe)")

    # --- MongoDB: load inventory (only if empty, or RESET) ------------------
    mc = MongoClient(mongo_uri)
    coll = mc["grocery_store"]["inventory"]
    have_mongo = coll.count_documents({})
    if reset or have_mongo == 0:
        coll.delete_many({})
        coll.insert_many(docs)
        print(f"[build_catalog] mongo: inserted {len(docs)} inventory docs" + (" (RESET)" if reset else ""))
    else:
        print(f"[build_catalog] mongo: {have_mongo} docs already present — skipping (use RESET=1 to force)")

    index_name = "vector_index"
    try:
        existing = {ix["name"] for ix in coll.list_search_indexes()}
    except Exception:
        existing = set()
    if index_name not in existing:
        model = SearchIndexModel(
            name=index_name,
            type="vectorSearch",
            definition={
                "fields": [{
                    "type": "vector",
                    "path": "gemini_embedding",
                    "numDimensions": EMBED_DIM,
                    "similarity": "cosine",
                }]
            },
        )
        coll.create_search_index(model=model)
        print(f"[build_catalog] mongo: created vector index '{index_name}' "
              f"(it may take ~30s to become queryable)")
    else:
        print(f"[build_catalog] mongo: vector index '{index_name}' already exists")

    print("[build_catalog] done.")


if __name__ == "__main__":
    main()
