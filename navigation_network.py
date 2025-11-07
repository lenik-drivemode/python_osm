#!/usr/bin/env python3
"""
This module provides functions to retrieve and visualize
street network data from OpenStreetMap using the OSMnx library.
"""
import osmnx as ox
import matplotlib.pyplot as plt

def visualize_osm_network(place_name, network_type='drive', fig_height=8, fig_width=8, filepath=None):
    """
    Retrieves and visualizes a street network from OpenStreetMap using osmnx.

    Args:
        place_name (str): The name of the place to retrieve the network for (e.g., "Piedmont, California, USA").
        network_type (str): The type of network to retrieve ('drive', 'walk', 'bike', 'all', 'all_private').
        fig_height (int): Height of the plot.
        fig_width (int): Width of the plot.
        filepath (str, optional): Path to save the plot image. If None, the plot is displayed.
    """
    # Retrieve the street network
    G = ox.graph_from_place(place_name, network_type=network_type)

    # Plot the network
    fig, ax = ox.plot_graph(G, figsize=(fig_height, fig_width), show=False, close=bool(filepath))

    if filepath:
        plt.savefig(filepath, bbox_inches='tight', dpi=300)
        print(f"Network visualization saved to {filepath}")
    else:
        plt.tight_layout(pad=0)
        plt.show()

if __name__ == "__main__":
    visualize_osm_network("Manhattan, New York City, USA", network_type='drive', filepath="manhattan_walk_network.png")
    visualize_osm_network("Shinagawa, Tokyo, Japan", network_type='drive')
