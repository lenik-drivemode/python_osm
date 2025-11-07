#!/usr/bin/env python3
"""
This script downloads and visualizes road network data
for a specified location using the OSMnx library.
"""

import osmnx as ox
import matplotlib.pyplot as plt

# 1. Define the place of interest
# You can specify a city, a neighborhood, or even a bounding box.
place_name = "Kamppi, Helsinki, Finland" 

# 2. Download the street network data for the specified place
# This fetches the OSM street network as a NetworkX MultiDiGraph object.
graph = ox.graph_from_place(place_name)

# 3. Plot the street network with tight layout
# This visualizes the downloaded street network using Matplotlib.
fig, ax = ox.plot_graph(graph, show=False, close=False, 
                        bbox_inches='tight', pad_inches=0.1)

# Optional: Download and plot buildings
area = ox.geocode_to_gdf(place_name)
buildings = ox.features_from_place(place_name, tags={'building': True})
buildings.plot(ax=ax, fc='gray', ec='none', alpha=0.7)

# Remove margins and whitespace
plt.subplots_adjust(left=0, bottom=0, right=1, top=1, wspace=0, hspace=0)
ax.margins(0)
ax.axis('off')  # Hide axes for cleaner look

# 4. Display the plot
plt.tight_layout(pad=0)
plt.show()
