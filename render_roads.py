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

# 3. Plot the street network
# This visualizes the downloaded street network using Matplotlib.
fig, ax = ox.plot_graph(graph, show=False, close=False)

# Optional: Download and plot buildings
area = ox.geocode_to_gdf(place_name)
buildings = ox.features_from_place(place_name, tags={'building': True})
buildings.plot(ax=ax, fc='gray', ec='none', alpha=0.7)

# 4. Display the plot
plt.show()
