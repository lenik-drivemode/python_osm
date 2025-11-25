#!/usr/bin/env python3
"""
This script loads a KML file containing GPS tracks and displays them
over an OpenStreetMap background using OSMnx and matplotlib.
"""

import osmnx as ox
import matplotlib.pyplot as plt
import geopandas as gpd
from shapely.geometry import Point, LineString
import xml.etree.ElementTree as ET
import numpy as np
import argparse
import sys

def parse_kml_coordinates(kml_file):
    """
    Parse coordinates from a KML file.
    
    Args:
        kml_file (str): Path to the KML file
        
    Returns:
        list: List of (longitude, latitude) tuples
    """
    tree = ET.parse(kml_file)
    root = tree.getroot()
    
    # Handle namespace
    ns = {'kml': 'http://www.opengis.net/kml/2.2'}
    
    coordinates = []
    
    # Look for coordinates in various KML elements
    for elem in root.iter():
        if elem.tag.endswith('coordinates'):
            coord_text = elem.text.strip()
            for line in coord_text.split():
                if line:
                    parts = line.split(',')
                    if len(parts) >= 2:
                        lon, lat = float(parts[0]), float(parts[1])
                        coordinates.append((lon, lat))
    
    return coordinates

def visualize_kml_on_osm(kml_file, network_type='drive', fig_height=12, fig_width=12, 
                        track_color='red', track_width=3, filepath=None):
    """
    Load a KML track and display it over an OpenStreetMap background.
    
    Args:
        kml_file (str): Path to the KML file
        network_type (str): OSM network type ('drive', 'walk', 'bike', 'all')
        fig_height (int): Height of the plot
        fig_width (int): Width of the plot
        track_color (str): Color of the GPS track
        track_width (int): Width of the GPS track line
        filepath (str, optional): Path to save the plot image
    """
    
    try:
        # Parse KML coordinates
        coordinates = parse_kml_coordinates(kml_file)
        
        if not coordinates:
            print(f"No coordinates found in {kml_file}")
            return
            
        print(f"Loaded {len(coordinates)} GPS points from {kml_file}")
        
        # Calculate bounding box with some padding
        lons, lats = zip(*coordinates)
        min_lat, max_lat = min(lats), max(lats)
        min_lon, max_lon = min(lons), max(lons)
        
        # Add padding (approximately 10% of the range)
        lat_range = max_lat - min_lat
        lon_range = max_lon - min_lon
        padding = 0.1
        
        # Create bbox tuple (north, south, east, west)
        north = max_lat + lat_range * padding
        south = min_lat - lat_range * padding
        east = max_lon + lon_range * padding
        west = min_lon - lon_range * padding
        
        # Download OSM network for the bounding box
        print("Downloading OpenStreetMap data...")
        G = ox.graph_from_bbox(north, south, east, west, network_type=network_type)
        
        # Create the plot
        fig, ax = ox.plot_graph(G, figsize=(fig_width, fig_height), 
                               show=False, close=False, 
                               node_size=0, edge_linewidth=0.5, 
                               edge_color='#999999', bgcolor='white')
        
        # Plot the GPS track
        track_lons, track_lats = zip(*coordinates)
        ax.plot(track_lons, track_lats, color=track_color, 
               linewidth=track_width, alpha=0.8, zorder=10, 
               label='GPS Track')
        
        # Mark start and end points
        ax.scatter(track_lons[0], track_lats[0], color='green', 
                  s=100, zorder=11, label='Start', marker='o')
        ax.scatter(track_lons[-1], track_lats[-1], color='red', 
                  s=100, zorder=11, label='End', marker='s')
        
        # Add legend
        ax.legend(loc='upper right', fontsize=10)
        
        # Set title
        ax.set_title(f'GPS Track on OpenStreetMap\n{len(coordinates)} points', 
                    fontsize=14, pad=20)
        
        # Remove axes for cleaner look
        ax.axis('off')
        
        # Tight layout
        plt.tight_layout(pad=0)
        
        if filepath:
            plt.savefig(filepath, bbox_inches='tight', dpi=300, 
                       facecolor='white', edgecolor='none')
            print(f"Visualization saved to {filepath}")
        else:
            plt.show()
            
    except Exception as e:
        print(f"Error processing KML file: {e}")
        return

def visualize_kml_simple(kml_file, filepath=None):
    """
    Simple visualization using GeoPandas (alternative method).
    
    Args:
        kml_file (str): Path to the KML file
        filepath (str, optional): Path to save the plot image
    """
    try:
        # Try to read KML with GeoPandas
        gdf = gpd.read_file(kml_file, driver='KML')
        
        if gdf.empty:
            print(f"No data found in {kml_file}")
            return
            
        # Get bounds for OSM download (minx, miny, maxx, maxy)
        bounds = gdf.total_bounds
        
        # Convert to (north, south, east, west) for OSMnx
        north = bounds[3]  # maxy
        south = bounds[1]  # miny
        east = bounds[2]   # maxx
        west = bounds[0]   # minx
        
        # Download OSM network
        G = ox.graph_from_bbox(north, south, east, west)
        
        # Plot
        fig, ax = ox.plot_graph(G, show=False, close=False, 
                               node_size=0, edge_linewidth=0.5)
        
        # Plot KML data
        gdf.plot(ax=ax, color='red', linewidth=3, alpha=0.8)
        
        ax.set_title('KML Track on OpenStreetMap')
        ax.axis('off')
        
        if filepath:
            plt.savefig(filepath, bbox_inches='tight', dpi=300)
            print(f"Visualization saved to {filepath}")
        else:
            plt.show()
            
    except Exception as e:
        print(f"Error with GeoPandas method: {e}")
        print("Try using the visualize_kml_on_osm function instead.")

def main():
    """Main function to handle command line arguments and execute visualization."""
    parser = argparse.ArgumentParser(
        description='Visualize KML GPS tracks over OpenStreetMap data',
        epilog='''
Examples:
  %(prog)s track.kml
  %(prog)s track.kml -o output.png
  %(prog)s track.kml --network-type all --color blue --width 4
  %(prog)s track.kml --simple --output simple_track.png
        ''',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('kml_file', 
                       help='Path to the KML file containing GPS track data')
    
    parser.add_argument('-o', '--output', 
                       help='Output file path for saving the visualization (PNG format)')
    
    parser.add_argument('--network-type', 
                       choices=['drive', 'walk', 'bike', 'all', 'all_private'],
                       default='drive',
                       help='Type of OpenStreetMap network to download (default: drive)')
    
    parser.add_argument('--color', '--track-color',
                       default='red',
                       help='Color of the GPS track (default: red)')
    
    parser.add_argument('--width', '--track-width',
                       type=int, default=3,
                       help='Width of the GPS track line (default: 3)')
    
    parser.add_argument('--height', '--fig-height',
                       type=int, default=12,
                       help='Height of the plot figure (default: 12)')
    
    parser.add_argument('--width-fig', '--fig-width',
                       type=int, default=12,
                       help='Width of the plot figure (default: 12)')
    
    parser.add_argument('--simple',
                       action='store_true',
                       help='Use simple GeoPandas-based visualization method')
    
    parser.add_argument('--version',
                       action='version',
                       version='KML Visualizer 1.0.0')
    
    args = parser.parse_args()
    
    # Check if KML file exists
    import os
    if not os.path.exists(args.kml_file):
        print(f"Error: KML file '{args.kml_file}' not found.")
        sys.exit(1)
    
    # Choose visualization method based on arguments
    if args.simple:
        print(f"Using simple GeoPandas method for {args.kml_file}")
        visualize_kml_simple(
            kml_file=args.kml_file,
            filepath=args.output
        )
    else:
        print(f"Visualizing {args.kml_file} with OSMnx method")
        visualize_kml_on_osm(
            kml_file=args.kml_file,
            network_type=args.network_type,
            fig_height=args.height,
            fig_width=args.width_fig,
            track_color=args.color,
            track_width=args.width,
            filepath=args.output
        )

if __name__ == "__main__":
    main()