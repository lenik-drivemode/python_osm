# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- Removed excessive white space around map visualization
- Added tight layout settings for cleaner plot rendering
- Hidden axes for more professional map appearance
- Optimized plot margins and padding

## [1.0.0] - 2024-01-01

### Added
- Initial release of road network visualization script
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
- Customizable location targeting
- Clean matplotlib-based rendering

### Dependencies
- osmnx: OpenStreetMap network analysis library
- matplotlib: Plotting and visualization
- NetworkX: Graph data structure support (via OSMnx)