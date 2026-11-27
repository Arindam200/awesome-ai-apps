from contracts import validate
from tools.fetch_pricing import fetch_pricing


def test_reads_current_api_schema():
    out = fetch_pricing("deepseek-ai/DeepSeek-V4.1-Flash-1017-fast")
    assert out == {"model": "deepseek-ai/DeepSeek-V4.1-Flash-1017-fast", "input_usd_per_1m": 0.60,
                   "cached_usd_per_1m": 0.012, "output_usd_per_1m": 2.40}


def test_other_models_and_contract():
    args = {"model_id": "meta-llama/Llama-3.3-70B-Instruct"}
    out = fetch_pricing(**args)
    assert out["input_usd_per_1m"] == 0.13
    validate("fetch_pricing", args, out)
