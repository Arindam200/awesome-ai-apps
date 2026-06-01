"""Travel tools for the Nebius LangChain planner."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any

import requests
from langchain_core.tools import tool

HTTP_TIMEOUT_SECONDS = 12
USER_AGENT = "nebius-travel-planner/0.1"


WEATHER_CODES = {
    0: "clear sky",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "depositing rime fog",
    51: "light drizzle",
    53: "moderate drizzle",
    55: "dense drizzle",
    61: "slight rain",
    63: "moderate rain",
    65: "heavy rain",
    71: "slight snow",
    73: "moderate snow",
    75: "heavy snow",
    80: "slight rain showers",
    81: "moderate rain showers",
    82: "violent rain showers",
    95: "thunderstorm",
    96: "thunderstorm with slight hail",
    99: "thunderstorm with heavy hail",
}


def _get_json(url: str, params: dict[str, Any]) -> dict[str, Any]:
    response = requests.get(
        url,
        params=params,
        headers={"User-Agent": USER_AGENT},
        timeout=HTTP_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def _daily_value(daily: dict[str, Any], key: str, index: int) -> Any:
    values = daily.get(key) or []
    if index >= len(values):
        return None
    return values[index]


def _geocode(place: str) -> dict[str, Any] | None:
    payload = _get_json(
        "https://geocoding-api.open-meteo.com/v1/search",
        {"name": place, "count": 1, "language": "en", "format": "json"},
    )
    results = payload.get("results") or []
    return results[0] if results else None


@tool
def geocode_destination(place: str) -> str:
    """Find the best matching location for a destination name.

    Returns JSON with name, country, coordinates, timezone, and population
    where available. Use this before weather calls or when the user's
    destination could be ambiguous.
    """
    try:
        payload = _get_json(
            "https://geocoding-api.open-meteo.com/v1/search",
            {"name": place, "count": 3, "language": "en", "format": "json"},
        )
    except Exception as exc:  # noqa: BLE001 - tool output should be user-readable.
        return json.dumps({"error": f"Geocoding failed: {exc}"})

    matches = []
    for item in payload.get("results", []):
        matches.append(
            {
                "name": item.get("name"),
                "country": item.get("country"),
                "admin1": item.get("admin1"),
                "latitude": item.get("latitude"),
                "longitude": item.get("longitude"),
                "timezone": item.get("timezone"),
                "population": item.get("population"),
            }
        )
    if not matches:
        return json.dumps({"error": f"No location found for {place}."})
    return json.dumps({"matches": matches}, indent=2)


@tool
def get_weather_summary(
    destination: str,
    start_date: str = "",
    end_date: str = "",
) -> str:
    """Get a daily weather summary for a destination.

    Dates must be ISO strings in YYYY-MM-DD format. If omitted or outside the
    near-term forecast window, the tool returns a seven-day forecast from
    today using Open-Meteo.
    """
    try:
        location = _geocode(destination)
        if not location:
            return json.dumps({"error": f"No location found for {destination}."})

        today = date.today()
        start = _parse_iso_date(start_date) or today
        end = _parse_iso_date(end_date) or min(start + timedelta(days=6), today + timedelta(days=15))
        note = None

        if start < today or start > today + timedelta(days=15):
            note = (
                "Requested dates are outside Open-Meteo's short forecast window; "
                "showing the next seven days instead."
            )
            start = today
            end = today + timedelta(days=6)
        elif end < start:
            end = start
        elif end > today + timedelta(days=15):
            note = "Forecast truncated to the available 16-day Open-Meteo window."
            end = today + timedelta(days=15)

        payload = _get_json(
            "https://api.open-meteo.com/v1/forecast",
            {
                "latitude": location["latitude"],
                "longitude": location["longitude"],
                "daily": [
                    "weather_code",
                    "temperature_2m_max",
                    "temperature_2m_min",
                    "precipitation_probability_max",
                ],
                "temperature_unit": "celsius",
                "timezone": location.get("timezone", "auto"),
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
            },
        )
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": f"Weather lookup failed: {exc}"})

    daily = payload.get("daily", {})
    days = []
    for index, day in enumerate(daily.get("time", [])):
        code = _daily_value(daily, "weather_code", index)
        days.append(
            {
                "date": day,
                "condition": WEATHER_CODES.get(code, f"weather code {code}"),
                "high_c": _daily_value(daily, "temperature_2m_max", index),
                "low_c": _daily_value(daily, "temperature_2m_min", index),
                "precip_probability_percent": _daily_value(
                    daily, "precipitation_probability_max", index
                ),
            }
        )

    return json.dumps(
        {
            "location": {
                "name": location.get("name"),
                "country": location.get("country"),
                "timezone": location.get("timezone"),
            },
            "note": note,
            "forecast": days,
        },
        indent=2,
    )


@tool
def destination_research(query: str, max_results: int = 5) -> str:
    """Search the web for travel research.

    Use for current attractions, neighborhoods, restaurants, transport,
    seasonal events, visa notes, safety context, and rough local prices.
    Returns concise search result snippets with links when available.
    """
    max_results = max(1, min(max_results, 8))
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS

        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": f"Search failed: {exc}"})

    cleaned = []
    for result in results:
        cleaned.append(
            {
                "title": result.get("title"),
                "url": result.get("href") or result.get("url"),
                "snippet": result.get("body"),
            }
        )
    if not cleaned:
        return json.dumps({"error": "No search results found."})
    return json.dumps({"query": query, "results": cleaned}, indent=2)


@tool
def convert_currency(amount: float, from_currency: str, to_currency: str) -> str:
    """Convert money using current Frankfurter exchange rates.

    Currency codes should be ISO 4217 codes such as USD, EUR, INR, GBP, or JPY.
    """
    source = from_currency.strip().upper()
    target = to_currency.strip().upper()
    if source == target:
        return json.dumps(
            {"amount": amount, "from_currency": source, "to_currency": target, "converted": amount}
        )
    try:
        payload = _get_json(
            "https://api.frankfurter.app/latest",
            {"amount": amount, "from": source, "to": target},
        )
        converted = payload.get("rates", {}).get(target)
        if converted is None:
            return json.dumps({"error": f"No rate returned for {source} to {target}."})
        return json.dumps(
            {
                "amount": amount,
                "from_currency": source,
                "to_currency": target,
                "converted": converted,
                "date": payload.get("date"),
            },
            indent=2,
        )
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": f"Currency conversion failed: {exc}"})


@tool
def estimate_daily_budget(
    destination: str,
    travel_style: str,
    travelers: int,
    days: int,
    currency: str = "USD",
) -> str:
    """Estimate a trip budget by style, travelers, and trip length.

    Returns a transparent baseline estimate. It should be treated as a first
    pass and refined with destination-specific search results.
    """
    styles = {
        "backpacker": {"lodging_room": 35, "food_pp": 22, "transit_pp": 9, "activities_pp": 16},
        "budget": {"lodging_room": 65, "food_pp": 32, "transit_pp": 14, "activities_pp": 24},
        "standard": {"lodging_room": 120, "food_pp": 48, "transit_pp": 20, "activities_pp": 38},
        "comfort": {"lodging_room": 220, "food_pp": 78, "transit_pp": 36, "activities_pp": 65},
        "premium": {"lodging_room": 420, "food_pp": 145, "transit_pp": 75, "activities_pp": 130},
    }
    normalized_style = travel_style.strip().lower()
    tier = styles.get(normalized_style, styles["standard"])
    travelers = max(1, travelers)
    days = max(1, days)
    nights = max(1, days - 1)
    rooms = max(1, (travelers + 1) // 2)

    lodging = tier["lodging_room"] * nights * rooms
    food = tier["food_pp"] * days * travelers
    transit = tier["transit_pp"] * days * travelers
    activities = tier["activities_pp"] * days * travelers
    contingency = round((lodging + food + transit + activities) * 0.12, 2)
    total_usd = round(lodging + food + transit + activities + contingency, 2)

    result = {
        "destination": destination,
        "style_used": normalized_style if normalized_style in styles else "standard",
        "travelers": travelers,
        "days": days,
        "nights": nights,
        "rooms_assumed": rooms,
        "currency_note": "Base estimate is in USD before optional conversion.",
        "breakdown_usd": {
            "lodging": lodging,
            "food": food,
            "local_transit": transit,
            "activities": activities,
            "contingency_12_percent": contingency,
            "total": total_usd,
        },
    }

    target = currency.strip().upper()
    if target and target != "USD":
        try:
            converted = json.loads(convert_currency.invoke({"amount": total_usd, "from_currency": "USD", "to_currency": target}))
            result["converted_total"] = converted
        except Exception as exc:  # noqa: BLE001
            result["conversion_error"] = str(exc)

    return json.dumps(result, indent=2)


@tool
def packing_and_prep_list(
    destination: str,
    season_or_month: str,
    activities: str,
    trip_length_days: int,
) -> str:
    """Create a concise packing and preparation checklist for the trip."""
    days = max(1, trip_length_days)
    activity_text = activities.lower()
    items = [
        "passport or government ID",
        "travel insurance details",
        "booking confirmations saved offline",
        "payment card plus emergency cash",
        "phone charger and universal adapter",
        "basic medicines and prescriptions",
    ]
    if any(word in activity_text for word in ["beach", "swim", "snorkel", "island"]):
        items.extend(["swimwear", "reef-safe sunscreen", "dry bag", "sandals"])
    if any(word in activity_text for word in ["hike", "trek", "walk", "nature"]):
        items.extend(["broken-in walking shoes", "light rain shell", "daypack", "water bottle"])
    if any(word in activity_text for word in ["business", "conference", "meeting"]):
        items.extend(["smart outfit", "laptop charger", "portable power bank"])
    if days >= 7:
        items.append("laundry plan or quick-dry clothing")

    return json.dumps(
        {
            "destination": destination,
            "season_or_month": season_or_month,
            "activities_considered": activities,
            "checklist": items,
        },
        indent=2,
    )


TRAVEL_TOOLS = [
    geocode_destination,
    get_weather_summary,
    destination_research,
    convert_currency,
    estimate_daily_budget,
    packing_and_prep_list,
]
