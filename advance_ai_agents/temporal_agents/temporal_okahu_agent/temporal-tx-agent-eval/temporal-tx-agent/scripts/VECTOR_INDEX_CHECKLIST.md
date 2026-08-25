# Vector Index Creation Checklist

Quick checklist for creating the vector search index in Couchbase Capella.

## ✅ Pre-Creation Checklist

- [ ] Documents exist in Couchbase with `embedding` field
- [ ] Embeddings are 1536-dimensional arrays
- [ ] Collection name is known (e.g., `transactions`)
- [ ] Bucket name is known (e.g., `temporal`)
- [ ] Scope name is known (usually `_default`)

## ✅ Index Configuration Checklist

### Basic Settings
- [ ] Index Name: `transaction_vector_index`
- [ ] Bucket: `temporal` (or your bucket name)
- [ ] Scope: `_default` (or your scope)
- [ ] Collection: `transactions` (must match exactly)

### Type Mapping
- [ ] Type Name: `_default.transactions` (or `transactions`)
- [ ] Enabled: ✅ Checked
- [ ] Dynamic: ❌ Disabled/False

### Vector Field (CRITICAL!)
- [ ] Field Name: `embedding` (exactly, case-sensitive)
- [ ] Field Type: `Vector` (from dropdown)
- [ ] Dimensions: `1536` (exactly this number)
- [ ] Similarity: `cosine` (from dropdown)

### Optional Fields
- [ ] `transaction_id`: Type `text`, Analyzer `keyword`
- [ ] `transaction_type`: Type `text`, Analyzer `keyword`
- [ ] `amount`: Type `number`

## ✅ Post-Creation Checklist

- [ ] Index appears in Indexes list
- [ ] Status shows "Building" initially
- [ ] Status changes to "Ready" (green) after 2-5 minutes
- [ ] Indexed document count matches transaction count
- [ ] No error messages displayed

## 🧪 Test Vector Search

After index is ready, test it:

```python
from couchbase.cluster import Cluster
from couchbase.options import ClusterOptions
from couchbase.auth import PasswordAuthenticator
from couchbase.vector_search import VectorQuery

# Connect to Couchbase
cluster = Cluster(
    'couchbases://your-cluster.cloud.couchbase.com',
    ClusterOptions(PasswordAuthenticator('username', 'password'))
)
bucket = cluster.bucket('temporal')
collection = bucket.scope('_default').collection('transactions')

# Create a test embedding (1536 dimensions)
test_embedding = [0.1] * 1536

# Perform vector search
result = collection.search(
    'transaction_vector_index',
    VectorQuery('embedding', test_embedding).limit(5)
)

for row in result:
    print(f"Transaction: {row.id}, Score: {row.score}")
```

## ❌ Troubleshooting

**Index not appearing:**
- Refresh the page
- Check you're in the correct cluster
- Verify Search service is enabled

**Status stuck on "Building":**
- Wait 5-10 minutes for large datasets
- Check cluster resources
- Verify documents have embeddings

**Status shows "Error":**
- Check collection name matches exactly
- Verify documents have `embedding` field
- Ensure embeddings are arrays with 1536 elements
- Check error message for details

**Vector search returns no results:**
- Verify index status is "Ready"
- Check embedding field name is exactly `embedding`
- Verify dimensions are 1536
- Ensure similarity metric is `cosine`

## 📚 Reference

- Full guide: `scripts/create_vector_index.md`
- Run guide: `RUN_GUIDE.md`
- Couchbase Docs: https://docs.couchbase.com/server/current/fts/fts-vector-search.html

