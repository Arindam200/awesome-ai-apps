"""Look up a model's token prices (USD per 1M tokens) from the provider API."""
from urllib.parse import quote

from provider_api.client import get_json


def fetch_pricing(model_id: str) -> dict:
    data = get_json(f"/v2/models/{quote(model_id, safe='')}")
    return {
        "model": data["model"],
        "input_usd_per_1m": float(data["pricing"]["unit_usd"]),
        "cached_usd_per_1m": float(data["pricing"]["cached_unit_usd"]),
        "output_usd_per_1m": float(data["pricing"]["output_unit_usd"]),
    }
