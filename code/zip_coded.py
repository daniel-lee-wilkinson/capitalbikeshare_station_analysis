import pandas as pd, geopandas as gpd, matplotlib.pyplot as plt
from shapely.geometry import Point
import contextily as ctx
from matplotlib.colors import Normalize
from matplotlib.colors import LogNorm
import numpy as np
import xyzservices
from pathlib import Path
# ───────────────────────────────────────────────────────────────
# 1. FILES & CRS
# ───────────────────────────────────────────────────────────────
root = Path(__file__).resolve().parents[1]  # one level above /code
out_path = root / "figures"
out_path.parent.mkdir(parents=True, exist_ok=True)  # create folder if needed
output_data_path = root / "processed_data"
in_path = root / "input_data"

TRIPS = in_path / "trips.csv"
ZCTA = in_path / "tl_2024_us_zcta520.shp"
CRS_LL, CRS_WEB = "EPSG:4326", 3857     # WGS 84 and Web-Mercator

# ───────────────────────────────────────────────────────────────
# 2. LOAD & CLEAN TRIPS
# ───────────────────────────────────────────────────────────────
df = (pd.read_csv(TRIPS)
        .dropna(subset=["start_lat","start_lng","end_lat","end_lng"])
        .query("38.4 <= start_lat <= 39.3 and -77.6 <= start_lng <= -76.6")
        .query("38.4 <= end_lat   <= 39.3 and -77.6 <= end_lng   <= -76.6"))
g_start = gpd.GeoDataFrame(df,
         geometry=gpd.points_from_xy(df.start_lng, df.start_lat), crs=CRS_LL)
g_end   = gpd.GeoDataFrame(df,
         geometry=gpd.points_from_xy(df.end_lng,   df.end_lat),   crs=CRS_LL)

# ───────────────────────────────────────────────────────────────
# 3. LOAD ZIPS actually used by the system
# ───────────────────────────────────────────────────────────────
zcta = (gpd.read_file(ZCTA)[["ZCTA5CE20","geometry"]]
          .rename(columns={"ZCTA5CE20":"zip"})
          .to_crs(CRS_LL))

used_zips = pd.concat([
                gpd.sjoin(g_start, zcta, predicate="within", how="left")["zip"],
                gpd.sjoin(g_end,   zcta, predicate="within", how="left")["zip"]
            ]).dropna().unique()
zcta = zcta[zcta["zip"].isin(used_zips)]

# helper: robust single-match join
def match_zip(points, label):
    s = (gpd.sjoin(points, zcta, predicate="within", how="left")
           .reset_index().drop_duplicates("index")
           .set_index("index")["zip"].rename(label))
    return s

df = df.join(match_zip(g_start, "o_zip")).join(match_zip(g_end, "d_zip"))
df = df.dropna(subset=["o_zip","d_zip"])

# ───────────────────────────────────────────────────────────────
# 4A. START clusters  (points)
# ───────────────────────────────────────────────────────────────
df["lat_r"], df["lon_r"] = df.start_lat.round(4), df.start_lng.round(4)
starts = (df.groupby(["lat_r","lon_r"]).size()
            .reset_index(name="start_rides"))
starts["geometry"] = [Point(xy) for xy in zip(starts.lon_r, starts.lat_r)]
g_starts = gpd.GeoDataFrame(starts, geometry="geometry", crs=CRS_LL).to_crs(epsg=CRS_WEB)

# ───────────────────────────────────────────────────────────────
# 4B. DESTINATION rides per ZIP  (polygons)
# ───────────────────────────────────────────────────────────────
dest = (df.groupby("d_zip").size().reset_index(name="dest_rides"))
zcta = zcta.merge(dest, left_on="zip", right_on="d_zip", how="left")
zcta["dest_rides"] = zcta["dest_rides"].fillna(0)
zcta_web = zcta.to_crs(epsg=CRS_WEB)

# ───────────────────────────────────────────────────────────────
# 5. PLOT – one axis, two layers
# ───────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(10,10))

# 5A  destination choropleth first
poly_norm = LogNorm(vmin=1, vmax=zcta_web.dest_rides.max())
zcta_web.plot(
    ax=ax,
    column="dest_rides",
    cmap="Blues",          # cool palette
    norm=poly_norm,
    alpha=0.6,
    edgecolor="darkblue",
    linewidth = 0.2,
    legend=True,
    legend_kwds={
        "label": "rides ending in ZIP\n(log-scale)",
        "orientation": "vertical",
        "shrink": 0.6
    }
)

# 5B  start-point clusters on top

import matplotlib.lines as mlines



g_starts_sorted = g_starts.sort_values("start_rides")   # ascending ➜ darkest at bottom of frame

size = np.sqrt(g_starts_sorted.start_rides) * 0.9  # adjust multiplier to taste
g_starts_sorted.plot(
    ax=ax,
    column="start_rides",
    cmap="OrRd",
    norm=LogNorm(vmin=1, vmax=g_starts_sorted.start_rides.max()),
    markersize=5,               # uniform radius
    alpha=0.5,
    edgecolor="black", linewidth=0.1,
    legend=True,
    legend_kwds={"label":"rides starting at cluster (log)", "shrink":0.6},
    zorder=3
)
# basemap & cosmetics


ctx.add_basemap(ax, source=ctx.providers["CartoDB"]["PositronNoLabels"])


ax.set_title("Bike-share starts (dots) and destination density by ZIP (polygons)")
ax.axis("off"); plt.tight_layout(); plt.savefig(out_path / "clusters_zip_coded.png", bbox_inches = "tight", dpi = 300); plt.show()



import pandas as pd, geopandas as gpd
from shapely.geometry import Point

# ── after you've already built g_starts (clusters) and zcta_web (ZIP polygons) ──

# 1A.  classify ZIPs by destination density  ─────────────────────────────
# choose quantiles or absolute numbers; here we do quartiles
q25, q75 = zcta_web.dest_rides.quantile([0.25, 0.75])
def zip_level(row):
    if row.dest_rides >= q75:
        return "dark"          # many rides ending  ➜  dark blue
    elif row.dest_rides <= q25:
        return "pale"          # few rides ending  ➜  pale blue
    else:
        return "medium"
zcta_web["zip_class"] = zcta_web.apply(zip_level, axis=1)

# 1B.  classify clusters by start-ride volume  ───────────────────────────
s25, s75 = g_starts.start_rides.quantile([0.25, 0.75])
def dot_level(r):
    if r.start_rides >= s75:
        return "large"
    elif r.start_rides <= s25:
        return "small"
    else:
        return "medium"
g_starts["dot_class"] = g_starts.apply(dot_level, axis=1)

# spatial join clusters → ZIP polygon to bring over the zip_class label
g_starts = g_starts.to_crs(zcta_web.crs)      # ensure same CRS (both 3857)
g_starts = g_starts.sjoin(
    zcta_web[["zip", "zip_class", "geometry"]],   # keep geometry
    how="left",
    predicate="within"
)


def matrix_label(r):
    if   r.zip_class == "dark"   and r.dot_class == "large":  return "High-turnover hub"
    elif r.zip_class == "dark"   and r.dot_class == "small":  return "Net sink ZIP"
    elif r.zip_class == "pale"   and r.dot_class == "large":  return "Net source hub"
    elif r.zip_class == "pale"   and r.dot_class == "small":  return "Low traffic"
    else: return "Balanced"

g_starts["matrix_cat"] = g_starts.apply(matrix_label, axis=1)

# Show sample clusters per category
for cat in ["High-turnover hub", "Net sink ZIP", "Net source hub", "Balanced"]:
    subset = g_starts[g_starts.matrix_cat == cat]
    print(f"\n=== {cat}  (n={len(subset)}) ===")
    print(subset[["start_rides", "zip", "matrix_cat"]].head().to_string())


# Save to CSV or GeoJSON if needed
g_starts.to_csv(output_data_path /"cluster_matrix_tags.csv", index=False)
# or g_starts.to_file("cluster_matrix_tags.gpkg", driver="GPKG")

# n = number of clusters that meet the "balanced" criteria
# start_rides = rides starting at that exact cluster
# dest_rides = rides ending in that exact ZIP polygon
# high turnover hub rows are the stations that send and receive many trips
# net sink ZIP rows are small stations inside big ZIPs (visitor drop-zones)
# net source hub rows are high-departure docks in residential ZIPs

# Filter by matrix_cat and inspect the lat_r / lon_r (or station ID) to pinpoint exactly which dock needs new racks, rebalancing, or signage.
# pick the category you’re interested in
target_cat = "Net sink ZIP"          # or "High-turnover hub", ...

# 1. subset clusters
sink_df = g_starts[g_starts["matrix_cat"] == target_cat].copy()
print(f"{len(sink_df):,} clusters match «{target_cat}»")

# 2. bring destination counts onto each cluster (one-time merge)
sink_df = sink_df.merge(
    zcta_web[["zip", "dest_rides"]],
    on="zip",
    how="left"
)

# 3. sort — pick ONE metric to drive the order
sink_df = sink_df.sort_values(
    ["dest_rides", "start_rides"],       # primary, secondary key
    ascending=[False, False]             # both descending
)


# 4. inspect
cols = ["start_rides", "dest_rides", "zip", "lat_r", "lon_r"]
print(sink_df[cols].head(15).to_string(index=False))
