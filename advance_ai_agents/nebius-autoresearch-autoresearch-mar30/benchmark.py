"""
benchmark.py — Fixed evaluation harness for Nebius AutoResearch.

Loads REAL NYC Yellow Taxi trip data (prepared by prepare_data.py), runs
solve.process(), verifies correctness against a golden reference, and
scores throughput.

DO NOT MODIFY THIS FILE. This is the ground-truth evaluation.

Usage:
    python prepare_data.py   # one-time data download
    python benchmark.py      # run the benchmark

Output:
    ---
    score:              <trips_per_second>   (higher is better, 0 if incorrect)
    processing_time:    <seconds>
    correctness:        pass | FAIL
    num_trips:          500000
"""

import os
import time
import math
import sys
import traceback
from collections import Counter, defaultdict
from datetime import datetime

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DATA_PATH   = os.path.join("data", "taxi_trips.csv")
TIME_BUDGET = 30  # seconds

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

def load_csv(path: str) -> str:
    """Read the CSV file and return everything after the header as a string."""
    if not os.path.exists(path):
        print(f"ERROR: {path} not found. Run 'python prepare_data.py' first.")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        header = f.readline()
        return f.read()

# ---------------------------------------------------------------------------
# Golden reference implementation
# ---------------------------------------------------------------------------

def _parse_row(line: str) -> dict | None:
    parts = line.split(",")
    if len(parts) < 10:
        return None
    try:
        return {
            "pickup_datetime": parts[0],
            "dropoff_datetime": parts[1],
            "passenger_count": int(parts[2]),
            "trip_distance": float(parts[3]),
            "pickup_location": int(parts[4]),
            "dropoff_location": int(parts[5]),
            "payment_type": int(parts[6]),
            "fare_amount": float(parts[7]),
            "tip_amount": float(parts[8]),
            "total_amount": float(parts[9]),
        }
    except (ValueError, IndexError):
        return None


def _trip_duration_minutes(pickup: str, dropoff: str) -> float | None:
    try:
        fmt = "%Y-%m-%d %H:%M:%S"
        dt = (datetime.strptime(dropoff, fmt) - datetime.strptime(pickup, fmt)).total_seconds()
        return dt / 60.0 if dt > 0 else None
    except (ValueError, TypeError):
        return None


def _p95(values: list[float]) -> float:
    s = sorted(values)
    idx = max(0, int(math.ceil(0.95 * len(s))) - 1)
    return round(s[idx], 4)


def compute_reference(csv_data: str) -> tuple[dict, int]:
    """Compute golden reference answers. Returns (reference_dict, num_trips)."""
    lines = csv_data.split("\n")

    payment_revenue = defaultdict(float)
    hourly_tip_sums = defaultdict(float)
    hourly_tip_counts = defaultdict(int)
    passenger_counts = Counter()
    distances = []
    durations = []
    hourly_trip_counts = Counter()
    pickup_pairs = Counter()
    fare_per_mile_sums = defaultdict(float)
    fare_per_mile_counts = defaultdict(int)
    daily_revenue = defaultdict(float)
    total_trips = 0

    for line in lines:
        if not line.strip():
            continue
        row = _parse_row(line)
        if row is None:
            continue

        total_trips += 1
        pt = row["payment_type"]
        payment_revenue[pt] += row["total_amount"]

        hour = int(row["pickup_datetime"][11:13])
        if row["tip_amount"] >= 0:
            hourly_tip_sums[hour] += row["tip_amount"]
            hourly_tip_counts[hour] += 1

        pc = min(row["passenger_count"], 7)
        passenger_counts[pc] += 1

        distances.append(row["trip_distance"])

        dur = _trip_duration_minutes(row["pickup_datetime"], row["dropoff_datetime"])
        if dur is not None and dur > 0:
            durations.append(dur)

        hourly_trip_counts[hour] += 1

        pair = (row["pickup_location"], row["dropoff_location"])
        pickup_pairs[pair] += 1

        if row["trip_distance"] > 0.5:
            fpm = row["fare_amount"] / row["trip_distance"]
            fare_per_mile_sums[hour] += fpm
            fare_per_mile_counts[hour] += 1

        day = row["pickup_datetime"][:10]
        daily_revenue[day] += row["total_amount"]

    payment_revenue_rounded = {k: round(v, 2) for k, v in payment_revenue.items()}

    hourly_avg_tip = {}
    for h in range(24):
        if hourly_tip_counts[h] > 0:
            hourly_avg_tip[h] = round(hourly_tip_sums[h] / hourly_tip_counts[h], 4)
        else:
            hourly_avg_tip[h] = 0.0

    passenger_dist = dict(passenger_counts)

    distance_p50 = round(sorted(distances)[len(distances) // 2], 4)
    distance_p95 = _p95(distances)
    distance_mean = round(sum(distances) / len(distances), 4)

    duration_p95 = _p95(durations)

    busiest_hours = [h for h, _ in hourly_trip_counts.most_common(5)]

    top_routes = [(pair, count) for pair, count in pickup_pairs.most_common(10)]

    avg_fare_per_mile_by_hour = {}
    for h in range(24):
        if fare_per_mile_counts[h] > 0:
            avg_fare_per_mile_by_hour[h] = round(
                fare_per_mile_sums[h] / fare_per_mile_counts[h], 4
            )
        else:
            avg_fare_per_mile_by_hour[h] = 0.0

    daily_revenue_rounded = {k: round(v, 2) for k, v in sorted(daily_revenue.items())}

    return {
        "payment_revenue": payment_revenue_rounded,
        "hourly_avg_tip": hourly_avg_tip,
        "passenger_distribution": passenger_dist,
        "distance_stats": {
            "mean": distance_mean,
            "p50": distance_p50,
            "p95": distance_p95,
        },
        "duration_p95_minutes": duration_p95,
        "busiest_hours": busiest_hours,
        "top_routes": top_routes,
        "avg_fare_per_mile_by_hour": avg_fare_per_mile_by_hour,
        "daily_revenue": daily_revenue_rounded,
    }, total_trips


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def _match(ref, res, path, tol=1e-3):
    if isinstance(ref, tuple):
        ref = list(ref)
    if isinstance(res, tuple):
        res = list(res)

    if isinstance(ref, dict):
        if not isinstance(res, dict):
            print(f"  FAIL [{path}]: expected dict, got {type(res).__name__}")
            return False
        ref_s = {str(k): v for k, v in ref.items()}
        res_s = {str(k): v for k, v in res.items()}
        if ref_s.keys() != res_s.keys():
            missing = ref_s.keys() - res_s.keys()
            extra   = res_s.keys() - ref_s.keys()
            print(f"  FAIL [{path}]: key mismatch  missing={missing}  extra={extra}")
            return False
        return all(_match(ref_s[k], res_s[k], f"{path}.{k}", tol) for k in ref_s)

    if isinstance(ref, list):
        if not isinstance(res, (list, tuple)):
            print(f"  FAIL [{path}]: expected list, got {type(res).__name__}")
            return False
        res = list(res)
        if len(ref) != len(res):
            print(f"  FAIL [{path}]: length {len(ref)} vs {len(res)}")
            return False
        return all(_match(ref[i], res[i], f"{path}[{i}]", tol) for i in range(len(ref)))

    if isinstance(ref, float) or isinstance(res, float):
        try:
            rf, rs = float(ref), float(res)
        except (TypeError, ValueError):
            print(f"  FAIL [{path}]: cannot compare as float")
            return False
        if abs(rf - rs) > tol * max(abs(rf), 1e-10):
            print(f"  FAIL [{path}]: {rf} vs {rs}")
            return False
        return True

    if ref != res:
        print(f"  FAIL [{path}]: {ref!r} vs {res!r}")
        return False
    return True


def verify(result, reference):
    expected_keys = set(reference.keys())
    actual_keys   = set(result.keys()) if isinstance(result, dict) else set()
    if expected_keys != actual_keys:
        print(f"  FAIL: key mismatch  expected={expected_keys}  got={actual_keys}")
        return False
    return all(_match(reference[k], result[k], k) for k in reference)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"Loading taxi trip data from {DATA_PATH}...", flush=True)
    csv_data = load_csv(DATA_PATH)

    print("Computing reference answers...", flush=True)
    reference, num_trips = compute_reference(csv_data)

    print(f"Running solve.process() on {num_trips:,} real taxi trips...", flush=True)

    try:
        import solve
    except Exception as e:
        print(f"\nFAIL: cannot import solve.py — {type(e).__name__}: {e}")
        traceback.print_exc()
        print("---")
        print("score:              0.0")
        print("processing_time:    0.000")
        print("correctness:        FAIL")
        print(f"num_trips:          {num_trips}")
        sys.exit(1)

    t0 = time.perf_counter()
    try:
        result = solve.process(csv_data)
    except Exception as e:
        elapsed = time.perf_counter() - t0
        print(f"\nFAIL: solve.process() raised {type(e).__name__}: {e}")
        traceback.print_exc()
        print("---")
        print("score:              0.0")
        print(f"processing_time:    {elapsed:.3f}")
        print("correctness:        FAIL")
        print(f"num_trips:          {num_trips}")
        sys.exit(1)
    elapsed = time.perf_counter() - t0

    if elapsed > TIME_BUDGET:
        print(f"\nFAIL: exceeded time budget ({elapsed:.1f}s > {TIME_BUDGET}s)")
        print("---")
        print("score:              0.0")
        print(f"processing_time:    {elapsed:.3f}")
        print("correctness:        timeout")
        print(f"num_trips:          {num_trips}")
        sys.exit(1)

    correct = verify(result, reference)
    throughput = num_trips / elapsed
    score = throughput if correct else 0.0

    print()
    print("---")
    print(f"score:              {score:.1f}")
    print(f"processing_time:    {elapsed:.3f}")
    print(f"correctness:        {'pass' if correct else 'FAIL'}")
    print(f"trips_per_second:   {throughput:.1f}")
    print(f"num_trips:          {num_trips}")
