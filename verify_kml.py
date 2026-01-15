#!/usr/bin/env python3
"""
Simple KML verification script to check the extended KML format.
"""

import xml.etree.ElementTree as ET
import sys

def verify_kml(kml_file):
    """Verify KML file structure and extended data."""
    try:
        tree = ET.parse(kml_file)
        root = tree.getroot()

        # Check namespaces
        namespaces = {
            'kml': 'http://www.opengis.net/kml/2.2',
            'gx': 'http://www.google.com/kml/ext/2.2'
        }

        print(f"Verifying KML file: {kml_file}")
        print("=" * 50)

        # Check document name
        doc_name = root.find('.//kml:name', namespaces)
        if doc_name is not None:
            print(f"Document name: {doc_name.text}")

        # Check schema
        schemas = root.findall('.//kml:Schema', namespaces)
        print(f"Schemas found: {len(schemas)}")
        for schema in schemas:
            schema_name = schema.get('name')
            print(f"  - Schema: {schema_name}")
            fields = schema.findall('.//gx:SimpleField', namespaces)
            for field in fields:
                field_name = field.get('name')
                field_type = field.get('type')
                display_name = field.find('.//kml:displayName', namespaces)
                display_text = display_name.text if display_name is not None else "N/A"
                print(f"    - Field: {field_name} ({field_type}) - {display_text}")

        # Check tracks
        tracks = root.findall('.//gx:Track', namespaces)
        print(f"gx:Track elements found: {len(tracks)}")

        if tracks:
            first_track = tracks[0]
            when_elements = first_track.findall('.//kml:when', namespaces)
            coord_elements = first_track.findall('.//gx:coord', namespaces)
            extended_data = first_track.findall('.//kml:ExtendedData', namespaces)

            print(f"  First track:")
            print(f"    - Timestamps: {len(when_elements)}")
            print(f"    - Coordinates: {len(coord_elements)}")
            print(f"    - Extended data sections: {len(extended_data)}")

            if when_elements:
                print(f"    - First timestamp: {when_elements[0].text}")
            if coord_elements:
                print(f"    - First coordinate: {coord_elements[0].text}")

            # Check speed and bearing data
            for ext_data in extended_data:
                speed_arrays = ext_data.findall('.//gx:SimpleArrayData[@name="speed"]', namespaces)
                bearing_arrays = ext_data.findall('.//gx:SimpleArrayData[@name="bearing"]', namespaces)

                for speed_array in speed_arrays:
                    speed_values = speed_array.findall('.//gx:value', namespaces)
                    print(f"    - Speed values: {len(speed_values)}")
                    if speed_values:
                        non_zero_speeds = [v.text for v in speed_values[:5] if v.text != '0' and v.text != '0.0']
                        if non_zero_speeds:
                            print(f"    - Sample speeds: {non_zero_speeds}")

                for bearing_array in bearing_arrays:
                    bearing_values = bearing_array.findall('.//gx:value', namespaces)
                    print(f"    - Bearing values: {len(bearing_values)}")
                    if bearing_values:
                        non_zero_bearings = [v.text for v in bearing_values[:5] if v.text != '0' and v.text != '0.0']
                        if non_zero_bearings:
                            print(f"    - Sample bearings: {non_zero_bearings}")

        print("=" * 50)
        print("✅ KML verification completed successfully!")

    except ET.ParseError as e:
        print(f"❌ XML Parse Error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

    return True

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 verify_kml.py <kml_file>")
        sys.exit(1)

    kml_file = sys.argv[1]
    success = verify_kml(kml_file)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
