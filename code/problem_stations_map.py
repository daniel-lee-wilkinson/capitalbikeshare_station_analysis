import matplotlib.pyplot as plt
import contextily as ctx
from join_matrix_station_names_from_db import g_starts_named
from zip_coded import g_starts

# Prepare for plotting
sink_named = g_starts_named.query("matrix_cat == 'Net sink ZIP' and is_named").copy()
sink_named = sink_named.to_crs(epsg=3857)

# Plot
fig, ax = plt.subplots(figsize=(12, 10))
sink_named.plot(
    ax=ax,
    color="red",
    markersize=sink_named["start_rides"],
    alpha=0.8,
    edgecolor="black",
    linewidth=0.3
)
ctx.add_basemap(ax, source=ctx.providers["CartoDB"]["PositronNoLabels"])
ax.set_title("Net Sink Stations (Named)")
plt.axis("off")
plt.tight_layout()
plt.show()



