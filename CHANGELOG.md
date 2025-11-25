# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- New `kml_track_visualizer.py` script for GPS track visualization
- KML file parsing functionality with XML ElementTree
- `visualize_kml_on_osm()` function for displaying GPS tracks over OpenStreetMap
- `visualize_kml_simple()` alternative function using GeoPandas
- Support for start/end point markers on GPS tracks
- Automatic bounding box calculation with padding for optimal map view
- Customizable track colors and line widths
- Legend support showing GPS track, start, and end points

### Changed
- Removed excessive white space around map visualization
- Added tight layout settings for cleaner plot rendering
- Hidden axes for more professional map appearance
- Optimized plot margins and padding

### Improved
- Better code structure with reusable functions
- Enhanced documentation and type hints
- More flexible visualization options

## [1.0.0] - 2024-01-01

### Added
- Initial release of road network visualization script
- New `navigation_network.py` module with reusable visualization functions
- `visualize_osm_network()` function for flexible network visualization
- Support for different network types (drive, walk, bike, all, all_private)
- Configurable figure dimensions (height and width)
- Optional file saving functionality with high DPI (300) output
- Example usage with Manhattan and Tokyo locations
- OSMnx integration for downloading OpenStreetMap data
- Street network visualization using matplotlib
- Building overlay functionality with gray styling
- Support for place-based queries (city, neighborhood, etc.)
- Default location set to Kamppi, Helsinki, Finland
- Comprehensive documentation and comments

### Features
- Download street network data from OpenStreetMap
- Visualize road networks as interactive plots
- Overlay building footprints on street maps
- Load and display GPS tracks from KML files
- Customizable location targeting
- Clean matplotlib-based rendering

### Dependencies
- osmnx: OpenStreetMap network analysis library
- matplotlib: Plotting and visualization
- geopandas: Geospatial data analysis (optional for KML support)
- shapely: Geometric object handling
- NetworkX: Graph data structure support (via OSMnx)
