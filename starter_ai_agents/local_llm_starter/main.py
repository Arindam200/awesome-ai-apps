"""Provider-neutral tool-calling agent using an OpenAI-compatible API."""

import ast
import json
import math
import operator
import os
from datetime import datetime

from dotenv import load_dotenv
from openai import OpenAI, OpenAIError

MAX_ROUNDS = 5
OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}


def get_config():
    load_dotenv()
    return (
        os.getenv("LLM_BASE_URL", "http://localhost:11434/v1"),
        os.getenv("LLM_MODEL", "qwen3:8b"),
        os.getenv("LLM_API_KEY", "not-needed").strip() or "not-needed",
    )


def get_current_time():
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


def word_count(text):
    return len(text.split())


def calculate(expression):
    """Evaluate basic arithmetic without eval()."""

    def visit(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            if isinstance(node.value, float) and not math.isfinite(node.value):
                raise ValueError("Result is not finite.")
            return node.value

        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = visit(node.operand)
            return value if isinstance(node.op, ast.UAdd) else -value

        if isinstance(node, ast.BinOp) and type(node.op) in OPS:
            left, right = visit(node.left), visit(node.right)

            if isinstance(node.op, ast.Pow) and abs(right) > 20:
                raise ValueError("Exponent too large.")

            result = OPS[type(node.op)](left, right)

            if not isinstance(result, (int, float)):
                raise ValueError("Result must be a real number.")
            if isinstance(result, int) and result.bit_length() > 4096:
                raise ValueError("Result too large.")
            if isinstance(result, float) and not math.isfinite(result):
                raise ValueError("Result is not finite.")

            return result

        raise ValueError("Only basic arithmetic is allowed.")

    if not isinstance(expression, str) or len(expression) > 200:
        raise ValueError("Expression must be under 200 characters.")

    try:
        return visit(ast.parse(expression, mode="eval").body)
    except (SyntaxError, ZeroDivisionError, OverflowError) as exc:
        raise ValueError("Invalid arithmetic expression.") from exc


def tool(name, description, arg=None):
    params = {"type": "object", "properties": {}}
    if arg:
        params["properties"][arg] = {"type": "string"}
        params["required"] = [arg]

    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": params,
        },
    }


TOOLS = [
    tool("get_current_time", "Get the current local date and time."),
    tool("word_count", "Count words in text.", "text"),
    tool("calculate", "Evaluate basic arithmetic.", "expression"),
]

FUNCTIONS = {
    "get_current_time": (get_current_time, set()),
    "word_count": (word_count, {"text"}),
    "calculate": (calculate, {"expression"}),
}


def run_tool(name, raw):
    if name not in FUNCTIONS:
        raise ValueError(f"Unknown tool: {name}")

    function, required = FUNCTIONS[name]
    args = json.loads(raw or "{}")

    if (
        not isinstance(args, dict)
        or set(args) != required
        or not all(isinstance(value, str) for value in args.values())
    ):
        raise ValueError(f"Invalid arguments for {name}.")

    return str(function(**args))


def run_agent(client, model, prompt):
    messages = [
        {"role": "system", "content": "Use tools when needed; never invent results."},
        {"role": "user", "content": prompt},
    ]

    def request(with_tools=True):
        kwargs = {"model": model, "messages": messages}
        if with_tools:
            kwargs["tools"] = TOOLS

        try:
            response = client.chat.completions.create(**kwargs)
        except OpenAIError as exc:
            raise RuntimeError(f"LLM request failed: {exc}") from exc

        if not response.choices:
            raise RuntimeError("Model returned no response.")

        return response.choices[0].message

    for _ in range(MAX_ROUNDS):
        msg = request()

        if not msg.tool_calls:
            return msg.content or "The model returned an empty response."

        messages.append(
            {
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [
                    call.model_dump(exclude_none=True) for call in msg.tool_calls
                ],
            }
        )

        for call in msg.tool_calls:
            try:
                result = run_tool(call.function.name, call.function.arguments)
            except Exception as exc:
                result = f"Tool error: {exc}"

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": result,
                }
            )

    msg = request(with_tools=False)
    return msg.content or "The model returned an empty response."


def main():
    try:
        url, model, key = get_config()
        client = OpenAI(api_key=key, base_url=url)
    except (ValueError, OpenAIError) as exc:
        raise SystemExit(f"Configuration error: {exc}") from exc

    print(f"Endpoint: {url}\nModel: {model}")
    print("Type 'exit' or 'quit' to stop.")

    while True:
        try:
            prompt = input("\nYou: ").strip()
            if prompt.lower() in {"exit", "quit"}:
                break
            if prompt:
                print("\nAssistant:", run_agent(client, model, prompt))
        except (EOFError, KeyboardInterrupt):
            break
        except RuntimeError as exc:
            print(f"\nError: {exc}")

    print("\nGoodbye!")


if __name__ == "__main__":
    main()
