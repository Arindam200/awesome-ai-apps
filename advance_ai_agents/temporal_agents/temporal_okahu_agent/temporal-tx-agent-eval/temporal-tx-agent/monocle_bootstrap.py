"""Monocle telemetry bootstrap for the vendored temporal-tx sample.

All Monocle instrumentation lives here. The vendored sample under
`temporal-tx-agent/{ai,api,temporal,...}` is otherwise untouched —
the only addition to the sample is a single-line `import monocle_bootstrap`
at the top of `api/main.py` and `temporal/run_worker.py`, which is
unavoidable (telemetry must init inside every process that emits traces).

What we register:

1. `LLMClient.analyze_transaction` → an **agent** span named
   `"fraud_detector"` (span.type = "agentic.invocation").
2. `EmbeddingClient.generate_embedding` → a **tool** span named
   `"embed_transaction"` (span.type = "agentic.tool.invocation").
3. Each Temporal activity in `temporal.activities` → a **tool** span.
   These only fire in the full-stack live path.

OpenAI itself is auto-instrumented by Monocle so `inference` spans
(with token counts) come for free — we don't register anything for it.

The output processors below mirror the shape used by the built-in
langgraph and openai-agents adapters (see
`.venv/.../monocle_apptrace/instrumentation/metamodel/{langgraph,agents}/entities/inference.py`),
so `monocle_test_tools`' `.called_agent("fraud_detector")` and
`.called_tool("business_rules", agent_name="fraud_detector")`
assertions match real spans, not generic ones.
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv

_HERE = Path(__file__).resolve().parent
load_dotenv(_HERE / ".env")
os.environ.setdefault("MONOCLE_EXPORTER", "file")

from monocle_apptrace import setup_monocle_telemetry  # noqa: E402
from monocle_apptrace.instrumentation.common.constants import (  # noqa: E402
    SPAN_TYPES,
    SPAN_SUBTYPES,
)
from monocle_apptrace.instrumentation.common.wrapper import (  # noqa: E402
    task_wrapper,
    atask_wrapper,
)

AGENT_NAME = "fraud_detector"


def _first_arg_text(arguments):
    args = arguments.get("args") or ()
    kwargs = arguments.get("kwargs") or {}
    payload = None
    if args:
        payload = args[0]
    elif "transaction_data" in kwargs:
        payload = kwargs["transaction_data"]
    elif "text" in kwargs:
        payload = kwargs["text"]
    if payload is None:
        return ""
    if isinstance(payload, (dict, list)):
        try:
            return json.dumps(payload, default=str)[:2000]
        except Exception:
            return str(payload)[:2000]
    return str(payload)[:2000]


def _result_text(arguments):
    result = arguments.get("result")
    if result is None:
        return ""
    if isinstance(result, (dict, list)):
        try:
            return json.dumps(result, default=str)[:2000]
        except Exception:
            return str(result)[:2000]
    return str(result)[:2000]


def _agent_processor(agent_name: str) -> dict:
    return {
        "type": SPAN_TYPES.AGENTIC_INVOCATION,
        "subtype": SPAN_SUBTYPES.CONTENT_PROCESSING,
        "attributes": [
            [
                {"attribute": "type", "accessor": lambda a: "agent.temporal-tx"},
                {"attribute": "name", "accessor": lambda a, n=agent_name: n},
                {"attribute": "description",
                 "accessor": lambda a: "Fraud detection LLM agent for the temporal-tx sample."},
            ],
        ],
        "events": [
            {"name": "data.input", "attributes": [
                {"attribute": "input", "accessor": _first_arg_text},
            ]},
            {"name": "data.output", "attributes": [
                {"attribute": "response", "accessor": _result_text},
            ]},
        ],
    }


def _tool_processor(tool_name: str, source_agent: str = AGENT_NAME) -> dict:
    return {
        "type": SPAN_TYPES.AGENTIC_TOOL_INVOCATION,
        "subtype": SPAN_SUBTYPES.CONTENT_GENERATION,
        "attributes": [
            [
                {"attribute": "type", "accessor": lambda a: "tool.temporal-activity"},
                {"attribute": "name", "accessor": lambda a, n=tool_name: n},
                {"attribute": "description",
                 "accessor": lambda a, n=tool_name: f"Temporal activity: {n}"},
            ],
            [
                {"attribute": "type", "accessor": lambda a: "agent.temporal-tx"},
                {"attribute": "name", "accessor": lambda a, n=source_agent: n},
            ],
        ],
        "events": [
            {"name": "data.input", "attributes": [
                {"attribute": "input", "accessor": _first_arg_text},
            ]},
            {"name": "data.output", "attributes": [
                {"attribute": "response", "accessor": _result_text},
            ]},
        ],
    }


WRAPPER_METHODS = [
    # Agent — sync method, so task_wrapper.
    {
        "package": "ai.llm_client",
        "object": "LLMClient",
        "method": "analyze_transaction",
        "span_name": AGENT_NAME,
        "wrapper_method": task_wrapper,
        "output_processor": _agent_processor(AGENT_NAME),
    },
    # Embedding call — modelled as a tool of fraud_detector.
    {
        "package": "ai.embedding_client",
        "object": "EmbeddingClient",
        "method": "generate_embedding",
        "span_name": "embed_transaction",
        "wrapper_method": task_wrapper,
        "output_processor": _tool_processor("embed_transaction"),
    },
    # Temporal activities — module-level async functions.
    # Only fire in the LIVE test path (through the actual Temporal worker).
    {
        "package": "temporal.activities",
        "object": None,
        "method": "apply_business_rules",
        "span_name": "business_rules",
        "wrapper_method": atask_wrapper,
        "output_processor": _tool_processor("business_rules"),
    },
    {
        "package": "temporal.activities",
        "object": None,
        "method": "search_similar_transactions",
        "span_name": "vector_search",
        "wrapper_method": atask_wrapper,
        "output_processor": _tool_processor("vector_search"),
    },
    {
        "package": "temporal.activities",
        "object": None,
        "method": "save_decision",
        "span_name": "save_decision",
        "wrapper_method": atask_wrapper,
        "output_processor": _tool_processor("save_decision"),
    },
    {
        "package": "temporal.activities",
        "object": None,
        "method": "update_transaction_status",
        "span_name": "update_status",
        "wrapper_method": atask_wrapper,
        "output_processor": _tool_processor("update_status"),
    },
    {
        "package": "temporal.activities",
        "object": None,
        "method": "create_human_review",
        "span_name": "human_review",
        "wrapper_method": atask_wrapper,
        "output_processor": _tool_processor("human_review"),
    },
]


_INITIALIZED = False


def init() -> None:
    global _INITIALIZED
    if _INITIALIZED:
        return
    setup_monocle_telemetry(
        workflow_name="temporal-tx",
        wrapper_methods=WRAPPER_METHODS,
        union_with_default_methods=True,  # keep OpenAI / FastAPI auto-instrumentation
    )
    _INITIALIZED = True


init()
