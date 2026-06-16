# MongoDB inventory (vector search)

The `grocery_store.inventory` collection holds the searchable product catalog
with pre-computed **Gemini embeddings** (`gemini_embedding`, 3072 dims) used by
the `semantic_product_search` Toolbox tool (`$vectorSearch`).

It is **not** seeded by a static file. `scripts/build_catalog.py` derives an
aligned catalog from `grocery_store.inventory.json` and loads it into BOTH
MongoDB and PostgreSQL with matching `sku` values, then creates the
`vector_index` search index. This guarantees that a product returned by vector
search also exists (with an authoritative price) in Postgres.

## Why Atlas Local

`$vectorSearch` requires the Atlas search node (`mongot`). The compose stack uses
`mongodb/mongodb-atlas-local`, which bundles it — so the laptop demo runs fully
offline and still uses real vector search. Community `mongo:7` does **not**
support `$vectorSearch`.

## Production

Point `MONGO_URI` at MongoDB Atlas (or self-managed Atlas Search) and create the
same `vector_index` on `gemini_embedding`. Toolbox connects with a least-privilege
DB user; the connection string lives only in Toolbox's environment / a secret.
