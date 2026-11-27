"""Model, endpoint, prices and paths."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
TOOLS_DIR = ROOT / "tools"
TESTS_DIR = ROOT / "tests"
FAILURES_DIR = ROOT / "failures"
load_dotenv(ROOT / ".env")

BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
MODEL = os.getenv("MODEL_ID", "deepseek-ai/DeepSeek-V4.1-Flash-1017-fast")
# USD per 1M tokens: input, cached input, output
PRICE = {"input": float(os.getenv("PRICE_INPUT", 0.60)),
         "cached": float(os.getenv("PRICE_CACHE", 0.012)),
         "output": float(os.getenv("PRICE_OUTPUT", 2.40))}

MAX_REPAIRS_PER_TOOL = 2
MAX_RETRIES = 3


def cost_usd(prompt: int, cached: int, output: int) -> float:
    return ((prompt - cached) * PRICE["input"] + cached * PRICE["cached"]
            + output * PRICE["output"]) / 1_000_000


def make_model():
    from langchain_openai import ChatOpenAI

    key = os.getenv("NEBIUS_API_KEY")
    if not key:
        raise RuntimeError("Set NEBIUS_API_KEY in .env (see .env.example)")
    return ChatOpenAI(model=MODEL, base_url=BASE_URL, api_key=key,
                      temperature=0, max_tokens=4096, streaming=True, stream_usage=True)
