#!/usr/bin/python
# -*- coding: utf-8 -*-

"""KML Converter
Script to convert telematics location CSV file into KML format.

Usage:
    python kml_convert.py <input_file>

Requirements:
- simplekml==1.3.6
- geographiclib==1.52
- geopy==2.4.1
"""

import argparse
import csv
import time
from datetime import datetime
from typing import Dict

import simplekml
from simplekml import Container

FieldName = str
FolderName = str


class LocationPointCreator:
    location_fields = [
        "accuracy_meters",
        "bearing_degrees",
        "bearing_accuracy_degrees",
        "altitude_meters",
        "vertical_accuracy_meters",
        "speed_meters_per_second",
        "speed_accuracy_meters_per_second",
        "time_milliseconds",
        "elapsed_realtime_nanoseconds",
        "source",
        "trip_id",
        "user_id",
        "meter_id",
    ]

    def add_new_point(self, folder: Container, row) -> Container:
        latitude = float(row["latitude"])
        longitude = float(row["longitude"])
        timestamp = datetime.fromisoformat(row['timestamp'].replace(' ', 'T', 1).replace(' UTC', 'Z'))
        timestamp_formatted = timestamp.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        point = folder.newpoint(name=timestamp_formatted, coords=[(longitude, latitude)])
        point.timestamp.when = timestamp_formatted
        point.extendeddata = simplekml.ExtendedData()
        for field in self.location_fields:
            value = row[field]
            if "_meters_per_second" in field:
                # Convert speed from m/s to km/h
                field = field.replace("_meters_per_second", "_km_per_hour")
                value = float(value) * 3600 / 1000
            point.extendeddata.newdata(name=field, value=value, displayname=field)
        return point


class MapboxEnhancedPointCreator(LocationPointCreator):
    mapbox_enhanced_fields = [
        "is_off_road",
        "offroad_probability",
        "is_teleport",
        "speed_limit",
        "road_edge_match_probability",
        "z_level",
        "road_name",
        "is_degraded_map_matching",
        "is_tunnel",
    ]

    def __init__(self):
        self.style = simplekml.Style()
        self.style.iconstyle.color = simplekml.Color.red

    def add_new_point(self, folder: Container, row) -> Container:
        point = super().add_new_point(folder, row)
        for field in self.mapbox_enhanced_fields:
            point.extendeddata.newdata(name=field, value=row[field], displayname=field)
        point.style = self.style
        return point


class KMLConverter:
    def __init__(self):
        parser = argparse.ArgumentParser("Script to convert telematics location CSV file into KML format.")
        parser.add_argument("input_file", help="Input CSV file")
        self.input_file = parser.parse_args().input_file
        self.folders_cache: Dict[FieldName: Dict[FolderName: Container]] = {}
        self.tracks_cache: Dict[str, Dict] = {}

    def map_fix_type_to_number(self, fix_type_str):
        """Map fix_type string values to numbers for chart visualization

        GPS Fix Type standards:
        0 = No fix / Invalid / Unknown
        1 = Dead reckoning only
        2 = 2D fix
        3 = 3D fix / GNSS + Dead reckoning combined
        """
        fix_type_mapping = {
            "": 0,  # Empty/null values - No fix
            "Unknown": 0,  # Unknown - No fix
            "Dead reckoning fix": 1,  # Dead reckoning only
            "GNSS fix or combined dead reckoning fix": 3  # Combined fix (most accurate)
        }
        return fix_type_mapping.get(fix_type_str, 0)

    def _get_or_add_folder(self, parent: Container, field_name: FieldName, folder_name: FolderName) -> Container:
        folders = self.folders_cache.get(field_name, {})
        if folder_name not in folders:
            folder = parent.newfolder(name=folder_name)
            folders[folder_name] = folder
            self.folders_cache[field_name] = folders
        else:
            folder = folders[folder_name]
        return folder

    def convert_from_csv(self):
        # Group data by user_id, trip_id, and source to create tracks
        tracks_data = {}

        min_timestamp = None
        max_timestamp = None

        with open(self.input_file, "r") as file:
            reader = csv.DictReader(file)
            for row in reader:
                user_id: str = row["user_id"] or "unknown user_id"
                trip_id: str = row["trip_id"] or "unknown trip_id"
                source: str = row["source"] or "unknown source"
                timestamp: str = row["timestamp"]

                track_key = f"{user_id}/{trip_id}/{source}"

                if track_key not in tracks_data:
                    tracks_data[track_key] = {
                        'user_id': user_id,
                        'trip_id': trip_id,
                        'source': source,
                        'points': []
                    }

                tracks_data[track_key]['points'].append(row)

                min_timestamp = min(min_timestamp, timestamp) if min_timestamp else timestamp
                max_timestamp = max(max_timestamp, timestamp) if max_timestamp else timestamp

        # Generate KML directly as string
        basename = self.input_file.split(".")[0]
        timestr = time.strftime("%Y%m%d%H%M%S")
        output_file = f"{basename}_{timestr}.kml"

        kml_content = self._generate_kml_with_tracks(tracks_data, min_timestamp, max_timestamp)

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(kml_content)

    def _generate_kml_with_tracks(self, tracks_data, min_timestamp, max_timestamp):
        """Generate complete KML content with gx:Track elements"""

        placemarks = []

        for track_key, track_info in tracks_data.items():
            source = track_info['source']
            points = track_info['points']

            # Sort points by timestamp
            points.sort(key=lambda x: x['timestamp'])

            placemark_xml = self._create_placemark_with_track(source, points)
            placemarks.append(placemark_xml)

        placemarks_content = '\n'.join(placemarks)

        return f'''<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2" xmlns:gx="http://www.google.com/kml/ext/2.2">
<Document>
<name>{min_timestamp} - {max_timestamp}</name>
{placemarks_content}
</Document>
</kml>'''

    def _create_placemark_with_track(self, source, points):
        """Create a placemark with gx:Track"""
        when_elements = []
        coord_elements = []
        extended_data_arrays = {}

        # Map source names to what index.js expects
        display_name = "gnss" if source == "corrected" else "mapbox"

        # Define fields
        location_fields = [
            "accuracy_meters", "bearing_degrees", "bearing_accuracy_degrees",
            "altitude_meters", "vertical_accuracy_meters", "speed_meters_per_second",
            "speed_accuracy_meters_per_second", "time_milliseconds",
            "elapsed_realtime_nanoseconds", "source", "trip_id", "user_id", "meter_id"
        ]

        # Add satellite data for raw/gnss data
        if source == "corrected":
            satellite_fields = ["satellites_in_view", "satellites_in_use", "satellites_asnr", "fix_type"]
            location_fields.extend(satellite_fields)

        if source == "mapbox":
            mapbox_fields = [
                "is_off_road", "offroad_probability", "is_teleport", "speed_limit",
                "road_edge_match_probability", "z_level", "road_name",
                "is_degraded_map_matching", "is_tunnel"
            ]
            location_fields.extend(mapbox_fields)

        # Initialize arrays
        for field in location_fields:
            extended_data_arrays[field] = []

        # Add utc field for index.js compatibility
        extended_data_arrays["utc"] = []

        # Process points
        for row in points:
            latitude = float(row["latitude"])
            longitude = float(row["longitude"])
            altitude = float(row["altitude_meters"]) if row["altitude_meters"] else 0.0

            timestamp = datetime.fromisoformat(row['timestamp'].replace(' ', 'T', 1).replace(' UTC', 'Z'))
            timestamp_formatted = timestamp.strftime('%Y-%m-%dT%H:%M:%S.%fZ')

            # Convert timestamp to UTC milliseconds for index.js
            utc_milliseconds = int(timestamp.timestamp() * 1000)

            when_elements.append(f'<when>{timestamp_formatted}</when>')
            coord_elements.append(f'<gx:coord>{longitude} {latitude} {altitude}</gx:coord>')

            # Add UTC milliseconds
            extended_data_arrays["utc"].append(str(utc_milliseconds))

            # Collect extended data
            for field in location_fields:
                value = row.get(field, "")

                # Handle satellite data fields - map from different column names
                if field == "satellites_in_view":
                    value = row.get("satellite_in_view", "")
                elif field == "satellites_in_use":
                    value = row.get("satellite_in_use", "")
                elif field == "satellites_asnr":
                    value = row.get("average_snr", "")
                elif field == "fix_type":
                    # fix_type is available for corrected/gnss source
                    if source == "corrected":
                        raw_value = row.get("fix_type", "")
                        # Map string values to numbers for visualization
                        value = str(self.map_fix_type_to_number(raw_value))
                    else:
                        value = "0"  # mapbox doesn't have fix_type, default to 0
                elif field == "is_degraded_map_matching":
                    # is_degraded_map_matching is available for mapbox source
                    if source == "mapbox":
                        value = row.get("is_degraded_map_matching", "")
                    else:
                        value = ""  # corrected doesn't have is_degraded_map_matching
                elif "_meters_per_second" in field and value:
                    # Keep original m/s values for raw data processing
                    value = str(float(value))

                extended_data_arrays[field].append(str(value))

        # Create SimpleArrayData
        simple_array_data_parts = []
        for field, values in extended_data_arrays.items():
            if values and any(values):
                values_xml = '\n'.join(f'<gx:value>{value}</gx:value>' for value in values)
                simple_array_data_parts.append(f'''<gx:SimpleArrayData name="{field}">
{values_xml}
</gx:SimpleArrayData>''')

        simple_array_data_xml = '\n'.join(simple_array_data_parts)

        when_xml = '\n'.join(when_elements)
        coord_xml = '\n'.join(coord_elements)

        if simple_array_data_xml:
            extended_data_xml = f'''<ExtendedData>
<SchemaData schemaUrl="#{source}_schema">
{simple_array_data_xml}
</SchemaData>
</ExtendedData>'''
        else:
            extended_data_xml = ''

        return f'''<Placemark>
<name>{display_name}</name>
<gx:Track>
{when_xml}
{coord_xml}
{extended_data_xml}
</gx:Track>
</Placemark>'''

if __name__ == "__main__":
    kml_converter = KMLConverter()
    kml_converter.convert_from_csv()
