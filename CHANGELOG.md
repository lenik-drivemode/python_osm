# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- New `convert_logs_to_kml.py` script for converting Android logs to KML format
- `parse_android_logs_for_coordinates()` function for extracting GPS coordinates from Android logs
- `create_kml_track()` function for generating KML documents with GPS tracks
- Multi-track support: automatic track separation on 10+ minute data gaps
- Multiple track styling with different colors for each track
- KML folder organization for multiple tracks
- Individual start/end markers for each track
- Track duration and point count statistics
- Support for converting NMEA messages from Android log files to KML tracks
- KML track generation with start/end point markers
- Command line interface for Android log to KML conversion
- Date filtering support for KML conversion (today or YYYY-MM-DD format)
- Customizable track names and descriptions in generated KML
- GPS statistics reporting (coordinate ranges, altitude, speed)
- Support for GGA and RMC NMEA sentence parsing for coordinates and metadata
- High-quality KML output compatible with Google Earth and other mapping apps
- Android log file support in `satellite_analyzer.py`
- `parse_android_log_satellite_data()` function for extracting NMEA data from Android logcat files
- Support for processing multiple log files from Android `logd/` folder
- Android log timestamp pattern recognition and parsing
- Regex-based NMEA sentence extraction from log files
- Support for various Android log timestamp formats
- Date filtering functionality with `--date` command line option
- Support for "today" keyword and YYYY-MM-DD date format filtering
- `filter_data_by_date()` function for filtering satellite data by specific dates
- `parse_date_argument()` function for robust date parsing
- NMEA file format support in `satellite_analyzer.py`
- `parse_nmea_satellite_data()` function for extracting satellite data from NMEA files
- Support for NMEA sentence types: GGA, GSV, and RMC
- Enhanced `detect_file_type()` function for automatic format detection (KML vs NMEA vs Android logs)
- `--format android_logs` command line option to specify Android log folder processing
- Coordinate parsing from NMEA GGA sentences in Android logs
- Date and time parsing from Android log timestamps
- Robust NMEA parsing with error handling for malformed sentences
- Auto-fallback parsing sequence: KML → NMEA → Android logs
- Enhanced command line examples for Android log usage and date filtering

### Changed
- Updated version to 2.1.0 to reflect Android log support addition
- Enhanced command line argument description to mention Android log support
- Modified `input_file` argument to `input_path` to support both files and folders
- Improved error handling and user feedback for all parsing methods
- Enhanced main function to handle KML files, NMEA files, and Android log folders
- Modified `convert_logs_to_kml.py` to ignore NMEA messages containing "s:1*78"
- Modified `convert_logs_to_kml.py` to ignore NMEA messages starting with "s:1*78"

### Improved
- Better file/folder format detection and parsing workflow
- More comprehensive satellite data extraction from multiple sources
- Enhanced user experience with automatic format detection
- Robust parsing that handles various log formats and corrupted data
- Support for batch processing of multiple Android log files

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
