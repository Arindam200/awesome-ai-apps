# Temporal Application Implementation

This directory contains a production-ready Temporal application for transaction processing with comprehensive state management, retries, timeouts, and durability.

## Architecture Overview

### Components

1. **Worker** (`run_worker.py`)
   - Connects to Temporal server
   - Registers workflows and activities
   - Polls for tasks from the task queue
   - Handles graceful shutdown

2. **Workflow** (`workflows.py`)
   - `TransactionProcessingWorkflow` - Main orchestration workflow
   - State management with `WorkflowExecutionState`
   - Signals for human review
   - Queries for workflow state inspection
   - Retry policies and error handling

3. **Activities** (`activities.py`)
   - `generate_embedding` - Creates embeddings using OpenAI
   - `analyze_transaction_with_ai` - AI-powered transaction analysis
   - `search_similar_transactions` - Vector search for fraud patterns
   - `apply_business_rules` - Compliance and business rule checks
   - `save_decision` - Persists decision to database
   - `update_transaction_status` - Updates transaction status
   - `create_human_review` - Creates human review records
   - All activities include heartbeats for long-running operations

## Key Features

### 1. State Management
- **Workflow State**: Tracks execution progress through `WorkflowExecutionState`
- **State Persistence**: State is automatically persisted by Temporal
- **Recovery**: Workflows can resume from last known state after failures
- **State Queries**: Real-time state inspection via `get_state()` query

### 2. Retry Policies
- **Activity Retries**: Configurable retry policies for each activity
- **Exponential Backoff**: Automatic backoff for transient failures
- **Non-Retryable Errors**: Specific error types that don't retry (e.g., compliance violations)
- **Maximum Attempts**: Limits on retry attempts to prevent infinite loops

### 3. Timeouts
- **Start-to-Close Timeout**: Maximum time for activity execution
- **Heartbeat Timeout**: For long-running activities with heartbeats
- **Workflow Timeout**: Overall workflow execution timeout
- **Human Review Timeout**: 7-day timeout for human review escalation

### 4. Durability
- **Automatic Persistence**: All workflow state is persisted by Temporal
- **Event History**: Complete audit trail of workflow execution
- **Failure Recovery**: Automatic recovery from worker crashes
- **No Data Loss**: Guaranteed execution even during system failures

### 5. Signals and Queries
- **Signals**: `human_review_complete` - Receives human review decisions
- **Queries**: `get_state` - Inspects current workflow state
- **Async Communication**: Non-blocking communication with workflows

### 6. Error Handling
- **Compensation Logic**: Automatic rollback on failures
- **Error Classification**: Retryable vs non-retryable errors
- **State Tracking**: Error messages and retry counts in state
- **Graceful Degradation**: Fallback behaviors for API failures

## Workflow Execution Flow

```
1. Initialize State
   ↓
2. Generate Embedding (with retry)
   ↓
3. Search Similar Transactions (with retry)
   ↓
4. Apply Business Rules (compliance checks)
   ↓
5. Analyze with AI (with retry, longer timeout)
   ↓
6. Check if Human Review Needed
   ├─ Yes → Create Review → Wait for Signal (7-day timeout)
   └─ No → Continue
   ↓
7. Save Decision (with retry, critical operation)
   ↓
8. Update Transaction Status (with retry, critical operation)
   ↓
9. Complete
```

## Running the Worker

```bash
# Start Temporal server first
docker-compose up -d

# Run the worker
python -m temporal.run_worker
```

## Testing

```bash
# Run workflow tests
pytest temporal/tests/test_workflow.py -v
```

## Configuration

Key configuration in `utils/config.py`:
- `TEMPORAL_HOST` - Temporal server address
- `TEMPORAL_NAMESPACE` - Temporal namespace
- `TEMPORAL_TASK_QUEUE` - Task queue name

## Best Practices Implemented

1. ✅ **Deterministic Workflows**: No random operations, time, or external calls in workflows
2. ✅ **Activity Heartbeats**: Long-running activities send heartbeats
3. ✅ **Proper Timeouts**: Appropriate timeouts for each activity type
4. ✅ **Retry Policies**: Tailored retry policies per activity
5. ✅ **State Management**: Explicit state tracking for recovery
6. ✅ **Error Handling**: Comprehensive error handling and compensation
7. ✅ **Testability**: Workflow tests using Temporal test framework
8. ✅ **Signals & Queries**: For async communication and state inspection

## Monitoring

- **Temporal UI**: View workflows at http://localhost:8080
- **Workflow Queries**: Use `get_state()` to inspect workflow state
- **Activity Heartbeats**: Monitor activity progress via heartbeats
- **Event History**: Complete execution history in Temporal UI

## Resilience Features

- **Automatic Retries**: Transient failures are automatically retried
- **Failure Recovery**: Workflows resume after worker crashes
- **Compensation**: Failed workflows update transaction status
- **Timeout Handling**: Human review timeouts default to reject
- **Error Classification**: Non-retryable errors fail fast

