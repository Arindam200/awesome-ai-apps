# AutoResearch — NYC Taxi Analytics Optimisation

## Goal
Maximise the `score` (trips processed per second) reported by `benchmark.py`
while keeping every output numerically correct.

## Project structure

| File | Role | Modify? |
|------|------|---------|
| `prepare_data.py` | Downloads real NYC taxi Parquet → CSV | NO |
| `data/taxi_trips.csv` | 500K real Yellow Taxi trip records | NO |
| `benchmark.py` | Loads CSV, runs `solve.process()`, verifies, scores | NO |
| `solve.py` | **Your analytics pipeline — the ONLY file you touch** | YES |
| `program.md` | These instructions | NO |
| `results.tsv` | Experiment log (auto-generated) | NO |

## Data format

CSV rows (no header passed to `process()`):
```
pickup_datetime,dropoff_datetime,passenger_count,trip_distance,
pickup_location,dropoff_location,payment_type,
fare_amount,tip_amount,total_amount
```

Example:
```
2024-01-15 08:23:45,2024-01-15 08:41:12,1,3.2,237,161,1,18.70,4.96,28.16
```

## What solve.py computes

1. **payment_revenue** — total revenue per payment type
2. **hourly_avg_tip** — average tip amount per hour (0-23)
3. **passenger_distribution** — trip count per passenger count (capped at 7)
4. **distance_stats** — mean, P50, P95 of trip distances
5. **duration_p95_minutes** — P95 trip duration (requires datetime parsing)
6. **busiest_hours** — top 5 hours by trip count
7. **top_routes** — top 10 (pickup, dropoff) location pairs
8. **avg_fare_per_mile_by_hour** — average fare/mile per hour (trips > 0.5 mi)
9. **daily_revenue** — total revenue per date, sorted by date

## Metric

```
score = num_trips / processing_time_seconds
```

Higher is better. Score is 0 if any output is wrong.

## Rules

- Only modify `solve.py`
- Keep the function signature: `process(csv_data: str) -> dict`
- All 9 output keys must be correct — benchmark verifies every value
- Only use Python standard library (plus numpy if you want)
- One focused change per experiment

## Known bottlenecks in the naive baseline

- Creates 500K dict objects (one per row)
- Makes 9+ separate passes over all records
- Calls `datetime.strptime()` 500K+ times for duration calculation
- Sorts full arrays for percentile calculations
- Manual dict-based counting instead of `collections.Counter`

## Optimisation ideas

- **Single pass**: accumulate all counters in one loop
- **`collections.Counter`**: C-level counting vs manual dict ops
- **Avoid `datetime.strptime()`**: parse timestamps with string slicing
- **Tuples instead of dicts**: 500K tuples vs 500K dicts = massive allocation savings
- **`heapq.nlargest`** for top-N instead of full sort
- **Combine distance + duration + fare computation** in one loop
- **Pre-split once, index by position** instead of named dict keys

## Do NOT

- Modify benchmark.py or prepare_data.py
- Hardcode output values
- Repeat changes already in the experiment history
- Import external packages not in the standard library (except numpy)
