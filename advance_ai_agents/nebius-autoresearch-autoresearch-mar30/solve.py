"""
solve.py — NYC Taxi trip analytics pipeline.

THIS IS THE ONLY FILE THE AGENT MODIFIES.

Process 500K real NYC Yellow Taxi trip records and compute business analytics.
The benchmark calls process(csv_data) and checks every output against a golden
reference computed from the same data.

Optimise for speed while keeping outputs correct. Higher trips/second = better score.
"""

from datetime import datetime


def process(csv_data: str) -> dict:
    """
    Process raw CSV data (no header) and return analytics results.

    Each line: pickup_datetime,dropoff_datetime,passenger_count,trip_distance,
               pickup_location,dropoff_location,payment_type,
               fare_amount,tip_amount,total_amount

    Returns a dict with exactly these keys:
        payment_revenue            : dict[int, float]  — total revenue per payment_type, rounded to 2
        hourly_avg_tip             : dict[int, float]  — avg tip per hour (0-23), rounded to 4
        passenger_distribution     : dict[int, int]    — trip count per passenger_count (capped at 7)
        distance_stats             : dict with mean, p50, p95 — each rounded to 4
        duration_p95_minutes       : float             — P95 trip duration in minutes, rounded to 4
        busiest_hours              : list[int]          — top 5 hours by trip count (desc order)
        top_routes                 : list[(tuple, int)] — top 10 (pickup, dropoff) pairs by count
        avg_fare_per_mile_by_hour  : dict[int, float]  — avg fare/mile per hour (trips > 0.5mi), rounded to 4
        daily_revenue              : dict[str, float]   — total revenue per date, rounded to 2, sorted by date
    """
    lines = csv_data.split("\n")

    # ── Parse all rows ─────────────────────────────────────────────────────
    records = []
    for line in lines:
        if not line.strip():
            continue
        parts = line.split(",")
        if len(parts) < 10:
            continue
        try:
            records.append({
                "pickup_datetime":  parts[0],
                "dropoff_datetime": parts[1],
                "passenger_count":  int(parts[2]),
                "trip_distance":    float(parts[3]),
                "pickup_location":  int(parts[4]),
                "dropoff_location": int(parts[5]),
                "payment_type":     int(parts[6]),
                "fare_amount":      float(parts[7]),
                "tip_amount":       float(parts[8]),
                "total_amount":     float(parts[9]),
            })
        except (ValueError, IndexError):
            continue

    # ── 1. Revenue by payment type ─────────────────────────────────────────
    payment_revenue = {}
    for r in records:
        pt = r["payment_type"]
        if pt in payment_revenue:
            payment_revenue[pt] += r["total_amount"]
        else:
            payment_revenue[pt] = r["total_amount"]
    payment_revenue = {k: round(v, 2) for k, v in payment_revenue.items()}

    # ── 2. Average tip by hour ─────────────────────────────────────────────
    tip_sums = {}
    tip_counts = {}
    for r in records:
        hour = int(r["pickup_datetime"][11:13])
        tip = r["tip_amount"]
        if tip >= 0:
            if hour in tip_sums:
                tip_sums[hour] += tip
                tip_counts[hour] += 1
            else:
                tip_sums[hour] = tip
                tip_counts[hour] = 1
    hourly_avg_tip = {}
    for h in range(24):
        if h in tip_sums and tip_counts[h] > 0:
            hourly_avg_tip[h] = round(tip_sums[h] / tip_counts[h], 4)
        else:
            hourly_avg_tip[h] = 0.0

    # ── 3. Passenger distribution ──────────────────────────────────────────
    passenger_distribution = {}
    for r in records:
        pc = min(r["passenger_count"], 7)
        if pc in passenger_distribution:
            passenger_distribution[pc] += 1
        else:
            passenger_distribution[pc] = 1

    # ── 4. Distance statistics ─────────────────────────────────────────────
    distances = []
    for r in records:
        distances.append(r["trip_distance"])
    distances_sorted = sorted(distances)
    n = len(distances_sorted)
    distance_mean = round(sum(distances) / n, 4)
    distance_p50 = round(distances_sorted[n // 2], 4)
    import math
    idx_95 = max(0, int(math.ceil(0.95 * n)) - 1)
    distance_p95 = round(distances_sorted[idx_95], 4)

    # ── 5. Duration P95 ───────────────────────────────────────────────────
    durations = []
    for r in records:
        try:
            fmt = "%Y-%m-%d %H:%M:%S"
            pickup  = datetime.strptime(r["pickup_datetime"], fmt)
            dropoff = datetime.strptime(r["dropoff_datetime"], fmt)
            dur = (dropoff - pickup).total_seconds() / 60.0
            if dur > 0:
                durations.append(dur)
        except (ValueError, TypeError):
            continue
    durations_sorted = sorted(durations)
    dur_idx = max(0, int(math.ceil(0.95 * len(durations_sorted))) - 1)
    duration_p95 = round(durations_sorted[dur_idx], 4)

    # ── 6. Busiest hours ──────────────────────────────────────────────────
    hourly_counts = {}
    for r in records:
        hour = int(r["pickup_datetime"][11:13])
        if hour in hourly_counts:
            hourly_counts[hour] += 1
        else:
            hourly_counts[hour] = 1
    sorted_hours = sorted(hourly_counts.items(), key=lambda x: -x[1])
    busiest_hours = [h for h, _ in sorted_hours[:5]]

    # ── 7. Top routes ─────────────────────────────────────────────────────
    route_counts = {}
    for r in records:
        pair = (r["pickup_location"], r["dropoff_location"])
        if pair in route_counts:
            route_counts[pair] += 1
        else:
            route_counts[pair] = 1
    sorted_routes = sorted(route_counts.items(), key=lambda x: -x[1])
    top_routes = [(pair, count) for pair, count in sorted_routes[:10]]

    # ── 8. Average fare per mile by hour ──────────────────────────────────
    fpm_sums = {}
    fpm_counts = {}
    for r in records:
        if r["trip_distance"] > 0.5:
            hour = int(r["pickup_datetime"][11:13])
            fpm = r["fare_amount"] / r["trip_distance"]
            if hour in fpm_sums:
                fpm_sums[hour] += fpm
                fpm_counts[hour] += 1
            else:
                fpm_sums[hour] = fpm
                fpm_counts[hour] = 1
    avg_fare_per_mile_by_hour = {}
    for h in range(24):
        if h in fpm_sums and fpm_counts[h] > 0:
            avg_fare_per_mile_by_hour[h] = round(fpm_sums[h] / fpm_counts[h], 4)
        else:
            avg_fare_per_mile_by_hour[h] = 0.0

    # ── 9. Daily revenue ──────────────────────────────────────────────────
    daily_rev = {}
    for r in records:
        day = r["pickup_datetime"][:10]
        if day in daily_rev:
            daily_rev[day] += r["total_amount"]
        else:
            daily_rev[day] = r["total_amount"]
    daily_revenue = {k: round(v, 2) for k, v in sorted(daily_rev.items())}

    return {
        "payment_revenue":           payment_revenue,
        "hourly_avg_tip":            hourly_avg_tip,
        "passenger_distribution":    passenger_distribution,
        "distance_stats":            {"mean": distance_mean, "p50": distance_p50, "p95": distance_p95},
        "duration_p95_minutes":      duration_p95,
        "busiest_hours":             busiest_hours,
        "top_routes":                top_routes,
        "avg_fare_per_mile_by_hour": avg_fare_per_mile_by_hour,
        "daily_revenue":             daily_revenue,
    }
