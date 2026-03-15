# Data Seeding Script

## Overview

The `seed_data.py` script populates Couchbase with sample transaction data for testing and demonstration purposes.

## Usage

### Basic Usage (Seed with Default Data)

```bash
python -m scripts.seed_data
```

This will create **13 sample transactions** with:
- Various transaction types (ACH, wire_transfer, international)
- Different risk levels (normal, suspicious, high-value)
- Embeddings for vector search (if OpenAI API key is configured)
- Sample decisions for some transactions

### Custom Number of Transactions

```bash
# Create 50 transactions
python -m scripts.seed_data 50

# Create 100 transactions
python -m scripts.seed_data 100
```

### Without Embeddings

If you don't have OpenAI API key or want to skip embedding generation:

```bash
python -m scripts.seed_data --no-embeddings
```

### Clear All Data

⚠️ **Warning**: This deletes ALL transactions and decisions!

```bash
python -m scripts.seed_data clear
```

## Sample Data Included

The script creates transactions in these categories:

### 1. Normal Transactions (Expected: Approve)
- Low-value ACH transfers
- Domestic wire transfers
- Personal transfers

### 2. Suspicious Transactions (Expected: Escalate)
- Structuring patterns (amounts just under $5000)
- Offshore account transfers
- High-risk country transactions
- New account high-value transfers

### 3. High-Value Transactions (Expected: Escalate)
- Wire transfers over $50,000
- Large enterprise payments

### 4. Fraud Pattern Transactions (Expected: Reject)
- Money mule patterns
- Unknown sender transactions
- Fee deduction patterns

### 5. Velocity Pattern Transactions (Expected: Escalate)
- Multiple rapid transactions from same sender

## Data Structure

Each transaction includes:
- `transaction_id` - Unique identifier
- `transaction_type` - ACH, wire_transfer, or international
- `amount` - Transaction amount
- `sender` - Sender information (name, country, account)
- `recipient` - Recipient information
- `description` - Transaction description
- `risk_flags` - List of risk indicators
- `status` - Transaction status
- `embedding` - 1536-dimensional vector (if embeddings enabled)
- `embedding_model` - Model used (text-embedding-3-small or mock)
- `created_at` - Timestamp (randomized within last 30 days)

## Decisions

For some transactions, the script also creates decision records with:
- `decision` - approve, reject, or escalate
- `confidence_score` - AI confidence (0-100)
- `risk_score` - Calculated risk score (0-100)
- `reasoning` - Decision reasoning
- `risk_factors` - List of risk factors

## Prerequisites

1. **Couchbase Setup**: Collections and indexes must be created first
   ```bash
   python -m scripts.setup_couchbase
   ```

2. **OpenAI API Key** (optional, for embeddings):
   - Set `OPENAI_API_KEY` in `.env`
   - Without it, mock embeddings will be used

3. **Couchbase Connection**: Configured in `.env`
   - `COUCHBASE_CONNECTION_STRING`
   - `COUCHBASE_USERNAME`
   - `COUCHBASE_PASSWORD`

## Example Output

```
✅ Connected to Couchbase
✅ Opened collection: transactions
Creating 13 sample transactions...
✅ Generated embedding for transaction TXN_20240108_ABC12345
✅ Generated embedding for transaction TXN_20240108_DEF67890
...
✅ Successfully created 13 transactions
✅ Successfully created 8 decisions

📊 Summary:
   - Transactions: 13
   - Decisions: 8
   - Embeddings: Yes

💡 Sample transaction IDs (first 5):
   - Transaction type: ach, Amount: $2500.0, Expected: approve
   - Transaction type: wire_transfer, Amount: $15000.0, Expected: approve
   - Transaction type: wire_transfer, Amount: $4999.0, Expected: escalate
   - Transaction type: international, Amount: $75000.0, Expected: escalate
   - Transaction type: wire_transfer, Amount: $100000.0, Expected: escalate
```

## Use Cases

1. **Testing**: Populate database for testing workflows and activities
2. **Demo**: Show system capabilities with realistic data
3. **Development**: Test vector search with known similar transactions
4. **Training**: Demonstrate fraud detection patterns

## Notes

- Transactions are created with random timestamps within the last 30 days
- Embeddings are generated using OpenAI API (or mock if unavailable)
- Some transactions have matching patterns for testing vector similarity
- Decisions are created for approximately 30% of approved transactions and all escalated/rejected ones

## Troubleshooting

**Error: Connection failed**
- Check Couchbase connection string in `.env`
- Verify Couchbase is running and accessible

**Error: Collection not found**
- Run `python -m scripts.setup_couchbase` first
- Verify collection names in `.env`

**Warning: Could not generate embedding**
- Check OpenAI API key
- Mock embeddings will be used instead
- Vector search will still work but with less accuracy

