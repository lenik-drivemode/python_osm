# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- NMEA file format support in `satellite_analyzer.py`
- `parse_nmea_satellite_data()` function for extracting satellite data from NMEA files
- Support for NMEA sentence types: GGA, GSV, and RMC
- `detect_file_type()` function for automatic format detection (KML vs NMEA)
- `--format` command line option to specify input file format (auto, kml, nmea)
- Coordinate parsing from NMEA GGA sentences
- Date and time parsing from NMEA RMC sentences
- Robust NMEA parsing with error handling for malformed sentences
- Auto-fallback from KML to NMEA parsing when format detection fails
- Enhanced command line examples for NMEA usage

### Changed
- Updated version to 2.0.0 to reflect major feature addition
- Enhanced command line argument description to mention NMEA support
- Improved error handling and user feedback for file parsing
- Modified main function to handle both KML and NMEA input files

### Improved
- Better file format detection and parsing workflow
- More comprehensive satellite data extraction from multiple sources
- Enhanced user experience with automatic format detection
- Robust parsing that handles various NMEA dialects and corrupted data

## [Previous Versions]

### Added
- New `satellite_analyzer.py` script for GPS satellite data analysis
- New `kml_visualizer.py` script for GPS track visualization
- Command line argument processing with argparse for flexible usage
- KML file parsing functionality with XML ElementTree
- `parse_kml_satellite_data()` function to extract satellite information from KML files
- `plot_satellite_data()` function for basic satellite visualization over time
- `create_detailed_analysis()` function for comprehensive multi-subplot analysis
- Support for parsing satellites in view and satellites in use from KML ExtendedData
- Automatic synthetic data generation when satellite data is not available in KML
- Time series plotting with proper date formatting
- Statistical information display (averages, duration)
- Distribution histograms for satellite counts
- Scatter plot analysis of satellite usage efficiency
- Robust timestamp parsing for various KML formats
- Fixed `ox.graph_from_bbox()` parameter passing in `kml_visualizer.py`
- New `navigation_network.py` module with reusable visualization functions
- `visualize_kml_on_osm()` function for displaying GPS tracks over OpenStreetMap
- `visualize_kml_simple()` alternative function using GeoPandas
- Support for start/end point markers on GPS tracks
- Automatic bounding box calculation with padding for optimal map view
- `visualize_osm_network()` function for flexible network visualization
- Support for different network types (drive, walk, bike, all, all_private)
- OSMnx integration for downloading OpenStreetMap data
- Street network visualization using matplotlib
- Building overlay functionality with gray styling
- Initial release of road network visualization script

### Features
- Download street network data from OpenStreetMap
- Visualize road networks as interactive plots
- Overlay building footprints on street maps
- Load and display GPS tracks from KML files
- Analyze GPS satellite data from both KML and NMEA files
- Parse NMEA sentences for comprehensive GPS data extraction
- Command line interface for KML/NMEA visualization and satellite analysis
- Automatic file format detection and parsing
- Customizable location targeting
- Clean matplotlib-based rendering

### Dependencies
- osmnx: OpenStreetMap network analysis library
- matplotlib: Plotting and visualization
- geopandas: Geospatial data analysis (optional for KML support)
- shapely: Geometric object handling
- argparse: Command line argument parsing (built-in)
- numpy: Numerical operations
- xml.etree.ElementTree: XML parsing (built-in)
- datetime: Date and time handling (built-in)
- re: Regular expressions (built-in)
- NetworkX: Graph data structure support (via OSMnx)
