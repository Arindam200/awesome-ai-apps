"""
prepare_data.py — Download and prepare real NYC taxi trip data.

Downloads Yellow Taxi trip records from the NYC TLC open data portal,
extracts a fixed sample of rows, and saves a clean CSV for benchmarking.

This is run ONCE before starting experiments. The prepared CSV is cached
locally and reused by benchmark.py.

Usage:
    pip install pandas pyarrow
    python prepare_data.py
"""

import os
import sys

DATA_DIR  = "data"
CSV_PATH  = os.path.join(DATA_DIR, "taxi_trips.csv")
N_ROWS    = 500_000
SEED      = 42

PARQUET_URL = "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2024-01.parquet"

COLUMNS = [
    "tpep_pickup_datetime",
    "tpep_dropoff_datetime",
    "passenger_count",
    "trip_distance",
    "PULocationID",
    "DOLocationID",
    "payment_type",
    "fare_amount",
    "tip_amount",
    "total_amount",
]

CSV_HEADER = (
    "pickup_datetime,dropoff_datetime,passenger_count,trip_distance,"
    "pickup_location,dropoff_location,payment_type,"
    "fare_amount,tip_amount,total_amount\n"
)


def download_and_prepare():
    try:
        import pandas as pd
    except ImportError:
        print("ERROR: pandas and pyarrow are required for data preparation.")
        print("  pip install pandas pyarrow")
        sys.exit(1)

    os.makedirs(DATA_DIR, exist_ok=True)

    if os.path.exists(CSV_PATH):
        n = sum(1 for _ in open(CSV_PATH)) - 1
        if n >= N_ROWS:
            print(f"Data already prepared: {CSV_PATH} ({n:,} rows)")
            return CSV_PATH

    print(f"Downloading NYC taxi data from TLC open data portal...")
    print(f"  URL: {PARQUET_URL}")
    df = pd.read_parquet(PARQUET_URL, columns=COLUMNS)
    print(f"  Downloaded {len(df):,} rows")

    df = df.dropna(subset=["passenger_count", "trip_distance", "fare_amount"])
    df = df[df["trip_distance"] > 0]
    df = df[df["fare_amount"] > 0]
    df = df[df["passenger_count"] > 0]

    if len(df) > N_ROWS:
        df = df.sample(n=N_ROWS, random_state=SEED).reset_index(drop=True)
    print(f"  Sampled {len(df):,} clean rows")

    df["tpep_pickup_datetime"] = df["tpep_pickup_datetime"].dt.strftime("%Y-%m-%d %H:%M:%S")
    df["tpep_dropoff_datetime"] = df["tpep_dropoff_datetime"].dt.strftime("%Y-%m-%d %H:%M:%S")
    df["passenger_count"] = df["passenger_count"].astype(int)
    df["PULocationID"] = df["PULocationID"].astype(int)
    df["DOLocationID"] = df["DOLocationID"].astype(int)
    df["payment_type"] = df["payment_type"].astype(int)
    df["fare_amount"] = df["fare_amount"].round(2)
    df["tip_amount"] = df["tip_amount"].round(2)
    df["total_amount"] = df["total_amount"].round(2)

    df.columns = [
        "pickup_datetime", "dropoff_datetime", "passenger_count", "trip_distance",
        "pickup_location", "dropoff_location", "payment_type",
        "fare_amount", "tip_amount", "total_amount",
    ]

    df.to_csv(CSV_PATH, index=False)
    size_mb = os.path.getsize(CSV_PATH) / (1024 * 1024)
    print(f"  Saved: {CSV_PATH} ({len(df):,} rows, {size_mb:.1f} MB)")
    return CSV_PATH


if __name__ == "__main__":
    download_and_prepare()
    print("Done. You can now run: python benchmark.py")
