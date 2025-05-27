import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import matplotlib.pyplot as plt
import contextily as ctx
import matplotlib.pyplot as plt
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize
from mpl_toolkits.axes_grid1 import make_axes_locatable

# -------------------------------------------------------------------------------------
# SECTION 1: Load & Clean Employer Data
# -------------------------------------------------------------------------------------

from pathlib import Path


# Always anchor relative to the current script's location (code/)
root = Path(__file__).resolve().parent

# Up one level from /code to project root
project_root = root.parent

# Paths to key folders
input_path = project_root / "input_data"
output_path = project_root / "processed_data"
figures_path = project_root / "figures"

# Read the file

geocoded_employers = output_path / "geocoded_employers.csv"
csv_path = geocoded_employers
df_employers = pd.read_csv(csv_path)
# Drop rows with missing geocodes
valid_employers = df_employers.dropna(subset=["lat", "lon"]).reset_index(drop=True)

# Convert to GeoDataFrame with geometry column
valid_employers["geometry"] = valid_employers.apply(
    lambda row: Point(row["lon"], row["lat"]), axis=1
)
gdf_employers = gpd.GeoDataFrame(valid_employers, geometry="geometry", crs="EPSG:4326")
gdf_employers = gdf_employers.to_crs(epsg=3857)  # match basemap projection

# Define the subset of key employers you want to highlight
key_employers = [
    "National Geographic Society",
    "District of Columbia CVS Pharmacy",
    "Georgetown University",
    "Children's National Medical Center",  # corrected spelling
    "General Dynamics Information Technology"
]

# Filter for only the key employers (case-insensitive match)
highlighted = gdf_employers[gdf_employers["name"].str.lower().isin([k.lower() for k in key_employers])]

# -------------------------------------------------------------------------------------
# SECTION 2: Load and Process Trip Data
# -------------------------------------------------------------------------------------

# Load ride data
df = pd.read_csv(input_path / "trips.csv")
df = df.dropna(subset=["start_lat", "start_lng"]).copy()

# Group rides by rounded start coordinates (approx. station clusters)
df["lat_round"] = df["start_lat"].round(4)
df["lng_round"] = df["start_lng"].round(4)
station_counts = df.groupby(["lat_round", "lng_round"]).size().reset_index(name="ride_count")

# Convert to GeoDataFrame
station_counts["geometry"] = station_counts.apply(lambda row: Point(row["lng_round"], row["lat_round"]), axis=1)
gdf = gpd.GeoDataFrame(station_counts, geometry="geometry", crs="EPSG:4326").to_crs(epsg=3857)

# Sort to ensure higher ride counts are plotted on top
gdf = gdf.sort_values("ride_count")

# -------------------------------------------------------------------------------------
# SECTION 3: Plotting
# -------------------------------------------------------------------------------------
# Create plot
fig, ax = plt.subplots(figsize=(12, 10))

# ───────────────────────────────────────────────
# Plot start density (without auto legend)
norm = Normalize(vmin=gdf["ride_count"].min(), vmax=gdf["ride_count"].max())
gdf.plot(
    ax=ax,
    column="ride_count",
    cmap="inferno_r",
    markersize=6,
    linewidth=0.3,
    alpha=1,
    norm=norm,
    legend=False,
    zorder=1
)

# ───────────────────────────────────────────────
# Plot key employers
highlighted.plot(
    ax=ax,
    color="black",
    markersize=80,
    marker="*",
    label="Key Employers",
    zorder=3
)

# Add labels
for x, y, label in zip(highlighted.geometry.x, highlighted.geometry.y, highlighted["name"]):
    ax.text(x, y, label, fontsize=8, ha='left', va='bottom', color='black')

# ───────────────────────────────────────────────
# Custom colorbar (scaled down)
divider = make_axes_locatable(ax)
cax = divider.append_axes("right", size="3%", pad=0.1)  # make the bar thinner

sm = ScalarMappable(norm=norm, cmap="inferno_r")
sm.set_array([])
cbar = fig.colorbar(sm, cax=cax)
cbar.set_label("Ride Starts per Cluster", fontsize=10)

# ───────────────────────────────────────────────
# Basemap and save
ctx.add_basemap(ax, source=ctx.providers.CartoDB.Positron)
ax.set_title("Bike Ride Start Hotspots with Key Employers", fontsize=14)
ax.axis("off")
plt.tight_layout()
plt.savefig(figures_path / "stations_by_key_employers.png", bbox_inches="tight", dpi=300)
plt.show()