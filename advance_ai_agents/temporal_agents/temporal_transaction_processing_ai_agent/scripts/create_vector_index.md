# Creating Vector Search Index in Couchbase Capella

## ⚠️ Important Notes Before Starting

- **Vector Dimensions**: Must be exactly `1536` (matches OpenAI text-embedding-3-small)
- **Field Name**: Must be exactly `embedding` (case-sensitive)
- **Similarity**: Use `cosine` (recommended for embeddings)
- **Collection**: Must match your collection name exactly (case-sensitive)
- **Index Building**: May take 2-5 minutes depending on data volume

## Method 1: Using Couchbase Capella UI (Recommended)

### Step-by-Step Instructions

#### Step 1: Navigate to Search

1. **Log in to Couchbase Capella**
   - Go to https://cloud.couchbase.com
   - Sign in and navigate to your cluster

2. **Open Search Service**
   - In the left sidebar, click **"Search"** (or look for the search icon)
   - Click the **"Indexes"** tab at the top
   - Click the **"Create Index"** button (usually blue/green, top right)

#### Step 2: Basic Index Configuration

3. **Configure Index Settings**
   - **Index Name**: `transaction_vector_index` (or any name you prefer)
   - **Bucket**: Select your bucket from dropdown (e.g., `temporal`)
   - **Scope**: Select `_default` (or your custom scope)
   - **Collection**: Select `transactions` (must match your collection name)
   - Click **"Next"** or **"Continue"** button

#### Step 3: Configure Type Mappings

4. **Add Custom Type Mapping**
   - You should see a section for "Type Mappings" or "Document Type"
   - Click **"Add Custom Mapping"** or **"Add Type"** button
   - **Type Name**: Enter `_default.transactions` 
     - *Note: Format is `scope.collection` or just `transactions` depending on UI version*
   - ✅ Check the **"Enabled"** checkbox
   - Set **"Dynamic"** dropdown to **"false"** or **"Disabled"**
     - *This ensures we define fields manually instead of auto-detecting*

#### Step 4: Add Vector Field (CRITICAL!)

5. **Add the Vector Field**
   - In the type mapping section, look for **"Fields"** or **"Properties"**
   - Click **"Add Field"** or **"+"** button
   - Fill in the field configuration:
     - **Field Name**: `embedding` (exactly this, case-sensitive)
     - **Field Type**: Select **"Vector"** from the dropdown
       - *If you don't see "Vector" option, make sure you're using Capella (not older Couchbase Server)*
     - **Dimensions**: `1536` (must be exactly this number)
     - **Similarity**: Select **"cosine"** from dropdown
       - *Options: cosine, dot_product, euclidean - use cosine*
   - Click **"Add"** or **"Save"** to add the field

#### Step 5: Add Other Fields (Optional but Recommended)

6. **Add Additional Fields for Better Search**
   
   **transaction_id field:**
   - Click **"Add Field"** again
   - **Field Name**: `transaction_id`
   - **Field Type**: `text`
   - **Analyzer**: Select `keyword` (or `standard` if keyword not available)
   - Click **"Add"**

   **transaction_type field:**
   - Click **"Add Field"**
   - **Field Name**: `transaction_type`
   - **Field Type**: `text`
   - **Analyzer**: `keyword`
   - Click **"Add"**

   **amount field:**
   - Click **"Add Field"**
   - **Field Name**: `amount`
   - **Field Type**: `number`
   - Click **"Add"**

#### Step 6: Create the Index

7. **Finalize and Create**
   - Review your configuration:
     - ✅ Index name is set
     - ✅ Bucket/Scope/Collection are correct
     - ✅ Vector field `embedding` with 1536 dimensions and cosine similarity
     - ✅ Other fields added (optional)
   - Click **"Create Index"** or **"Save"** button
   - You should see a confirmation message

#### Step 7: Wait for Index to Build

8. **Monitor Index Status**
   - The index will appear in the Indexes list
   - Status will show **"Building"** (yellow/orange indicator)
   - Wait 2-5 minutes for indexing to complete
   - Status will change to **"Ready"** (green checkmark) when done
   - You can refresh the page to check status

#### Step 8: Verify Index is Ready

9. **Confirm Index is Ready**
   - Index status should show **"Ready"** (green)
   - Indexed document count should match your transaction count
   - If status is still "Building", wait a bit longer
   - If status shows "Error", check the error message and verify:
     - Collection name matches exactly
     - Documents have `embedding` field
     - Embedding arrays have exactly 1536 elements

## Method 2: Using REST API

If you prefer using the REST API, here's the JSON configuration:

```bash
curl -X PUT \
  "https://<your-cluster>.cloud.couchbase.com:18094/api/index/transaction_vector_index" \
  -u "<username>:<password>" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "fulltext-index",
    "name": "transaction_vector_index",
    "sourceType": "couchbase",
    "sourceName": "temporal",
    "planParams": {
      "maxPartitionsPerPIndex": 1024,
      "indexPartitions": 1
    },
    "params": {
      "doc_config": {
        "mode": "scope.collection.type_field",
        "type_mapping": {
          "types": {
            "_default.transactions": {
              "enabled": true,
              "dynamic": false,
              "properties": {
                "transaction_id": {
                  "enabled": true,
                  "fields": [{
                    "name": "transaction_id",
                    "type": "text",
                    "analyzer": "keyword"
                  }]
                },
                "embedding": {
                  "enabled": true,
                  "fields": [{
                    "name": "embedding",
                    "type": "vector",
                    "dims": 1536,
                    "similarity": "cosine"
                  }]
                }
              }
            }
          }
        }
      }
    }
  }'
```

Replace:
- `<your-cluster>` with your Capella cluster hostname
- `<username>` with your Capella username
- `<password>` with your Capella password
- `temporal` with your bucket name if different

## Method 3: Using Python Script

I'll create a Python script to help automate this via the REST API.

## Verification

After creating the index, verify it works:

```bash
# Check index status
curl -X GET \
  "https://<your-cluster>.cloud.couchbase.com:18094/api/index/transaction_vector_index" \
  -u "<username>:<password>"
```

The index status should be `"indexed"` or `"ready"`.

## Important Notes

1. **Index Building Time**: Large datasets may take several minutes to index
2. **Vector Dimensions**: Must match exactly (1536 for text-embedding-3-small)
3. **Similarity Metric**: Cosine similarity is recommended for embeddings
4. **Collection Name**: Must match exactly (case-sensitive)

## Troubleshooting

**Index not appearing**: 
- Refresh the page
- Check bucket/scope/collection names match exactly

**Index stuck in "Building"**:
- Wait a few minutes
- Check cluster resources
- Verify documents have embeddings

**Vector search not working**:
- Verify embedding field name is `embedding`
- Check dimensions are 1536
- Ensure similarity is `cosine`

