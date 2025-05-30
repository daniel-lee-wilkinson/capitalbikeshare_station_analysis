import sqlite3
import pandas as pd
from zip_coded import g_starts
from pathlib import Path

# 🔧 File paths
root = Path(__file__).resolve().parents[1]  # one level above /code
in_path = root / "input_data"
data_output_path = root / "processed_data"
# open your .db file
conn = sqlite3.connect(in_path /"april2025.db")

# read only the station name + coordinates of starting trips
stations_df = pd.read_sql_query("""
    SELECT DISTINCT
           start_station_name,
           ROUND(start_lat, 4) AS lat_r,
           ROUND(start_lng, 4) AS lon_r
    FROM trips
    WHERE start_station_name IS NOT NULL
""", conn)

g_starts_named = g_starts.merge(
    stations_df,
    on=["lat_r", "lon_r"],
    how="left"  # keeps unnamed clusters too
)

print(g_starts_named[["start_rides", "zip", "matrix_cat", "start_station_name"]]
      .sort_values("start_rides", ascending=False)
      .head(15)
      .to_string(index=False))

unnamed = g_starts_named[g_starts_named["start_station_name"].isna()]
print(f"Unnamed clusters: {len(unnamed)}")

# Show top 10 by start_rides
print(unnamed.sort_values("start_rides", ascending=False)
              [["start_rides", "lat_r", "lon_r", "zip", "matrix_cat"]]
              .head(10)
              .to_string(index=False))

named = g_starts_named[g_starts_named["start_station_name"].notna()]
named.to_csv(data_output_path / "named_cluster_matrix.csv", index=False)

g_starts_named["is_named"] = g_starts_named["start_station_name"].notna()
summary = (
    g_starts_named
    .groupby(["matrix_cat", "is_named"])
    .size()
    .unstack(fill_value=0)
    .rename(columns={True: "named", False: "unnamed"})
)

# Add a total column
summary["total"] = summary["named"] + summary["unnamed"]

# Optional: reorder for readability
summary = summary[["named", "unnamed", "total"]]
print(summary)

g_starts_named[g_starts_named["is_named"]].groupby("matrix_cat")["start_station_name"].nunique()

for cat in g_starts_named["matrix_cat"].unique():
    top = (
        g_starts_named
        .query("matrix_cat == @cat and is_named")
        .sort_values("start_rides", ascending=False)
        [["start_station_name", "start_rides", "zip"]]
        .head(5)
    )
    print(f"\n=== {cat} ===")
    print(top.to_string(index=False))
