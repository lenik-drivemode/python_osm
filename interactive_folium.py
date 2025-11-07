#!/usr/bin/env python3
"""
This script creates an interactive OpenStreetMap visualization using the folium library.
"""
import folium

def create_interactive_osm_map(latitude, longitude, zoom_start=12, points_of_interest=None, output_filename="osm_map.html"):
    """
    Creates an interactive OpenStreetMap visualization using folium.

    Args:
        latitude (float): Latitude for the map's center.
        longitude (float): Longitude for the map's center.
        zoom_start (int): Initial zoom level of the map.
        points_of_interest (list of dict, optional): A list of dictionaries,
            where each dictionary represents a point of interest with 'lat', 'lon', and 'name' keys.
        output_filename (str): The name of the HTML file to save the map.
    """
    # Create a Folium map object
    m = folium.Map(location=[latitude, longitude], zoom_start=zoom_start)

    # Add points of interest if provided
    if points_of_interest:
        for poi in points_of_interest:
            folium.Marker(
                location=[poi['lat'], poi['lon']],
                popup=poi['name']
            ).add_to(m)

    # Save the map to an HTML file
    m.save(output_filename)
    print(f"Interactive map saved to {output_filename}")

if __name__ == "__main__":
    # Example usage:
    # Center the map around a specific location (e.g., Eiffel Tower, Paris)
    eiffel_tower_lat = 48.8584
    eiffel_tower_lon = 2.2945

    # Define some points of interest
    pois = [
        {'lat': 48.8606, 'lon': 2.3376, 'name': 'Louvre Museum'},
        {'lat': 48.8530, 'lon': 2.3499, 'name': 'Notre-Dame Cathedral'}
    ]

    create_interactive_osm_map(eiffel_tower_lat, eiffel_tower_lon, points_of_interest=pois)
