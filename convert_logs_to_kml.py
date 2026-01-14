#!/usr/bin/env python3
"""
This script converts Android log files containing NMEA GPS messages
into a KML track file that can be viewed in Google Earth or other
mapping applications.
"""

import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime, date
import argparse
import sys
import os
import re
import glob

def parse_android_logs_for_coordinates(logd_folder, filter_date=None, include_raw=False):
    """
    Parse Android log files and extract GPS coordinates from NMEA messages.
    Creates separate tracks when data gaps exceed 10 minutes.
    
    Args:
        logd_folder (str): Path to the logd folder containing Android log files
        filter_date (date, optional): Filter data by specific date
        include_raw (bool): Whether to include raw coordinates (s:1*78) tracks
        
    Returns:
        list: List of tracks, where each track is a list of tuples (timestamp, longitude, latitude, altitude, speed, course)
    """
    try:
        all_tracks = []
        current_track = []
        current_raw_track = []  # Separate track for raw coordinates (s:1*78 messages)
        
        # Pattern to match NMEA sentences in Android logs
        nmea_pattern = re.compile(r'\$G[PN][A-Z]{3}[^\r\n]*')
        
        # Android log timestamp patterns
        timestamp_patterns = [
            # Common Android logcat format: MM-DD HH:MM:SS.mmm
            re.compile(r'(\d{2})-(\d{2})\s+(\d{2}):(\d{2}):(\d{2})\.(\d{3})'),
            # Alternative format: YYYY-MM-DD HH:MM:SS.mmm
            re.compile(r'(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2}):(\d{2})\.(\d{3})'),
            # Simple timestamp: HH:MM:SS.mmm
            re.compile(r'(\d{2}):(\d{2}):(\d{2})\.(\d{3})'),
        ]
        
        current_date = filter_date or datetime.now().date()
        current_lat = None
        current_lon = None
        current_alt = None
        current_speed = None
        current_course = None
        last_valid_timestamp = None
        last_raw_timestamp = None  # Separate timestamp tracking for raw coordinates (s:1*78)
        
        # Track separation threshold (10 minutes)
        TRACK_GAP_THRESHOLD = 600  # seconds
        
        # Get all log files in the logd folder
        log_files = glob.glob(os.path.join(logd_folder, '*'))
        log_files = [f for f in log_files if os.path.isfile(f)]
        
        if not log_files:
            print(f"No log files found in {logd_folder}")
            return []
        
        print(f"Processing {len(log_files)} log files from {logd_folder}")
        
        def finalize_current_track():
            """Helper function to finalize current track and start a new one."""
            nonlocal current_track, all_tracks
            if current_track:
                all_tracks.append(current_track)
                print(f"Track {len(all_tracks)} completed with {len(current_track)} points")
                current_track = []
        
        def finalize_raw_track():
            """Helper function to finalize raw coordinates track and start a new one."""
            nonlocal current_raw_track, all_tracks
            if current_raw_track:
                all_tracks.append(current_raw_track)
                print(f"Raw Track {len(all_tracks)} completed with {len(current_raw_track)} points")
                current_raw_track = []
        
        for log_file in sorted(log_files, reverse=True):
            print(f"Processing {os.path.basename(log_file)}...")
            
            try:
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as file:
                    for line_num, line in enumerate(file, 1):
                        line = line.strip()
                        if not line:
                            continue
                        
                        # Look for NMEA sentences in the log line
                        nmea_matches = nmea_pattern.findall(line)
                        if not nmea_matches:
                            continue
                        
                        # Determine if this is a raw coordinates message or regular NMEA
                        is_raw_message = 's:1*78' in line
                        
                        # Skip raw messages if not requested
                        if is_raw_message and not include_raw:
                            continue
                        
                        # Try to extract timestamp from the log line
                        log_timestamp = None
                        for pattern in timestamp_patterns:
                            match = pattern.search(line)
                            if match:
                                groups = match.groups()
                                try:
                                    if len(groups) == 6 and len(groups[0]) == 2:  # MM-DD format
                                        month, day, hour, minute, second, millisec = groups
                                        log_timestamp = datetime.combine(
                                            current_date.replace(month=int(month), day=int(day)),
                                            datetime.min.time().replace(
                                                hour=int(hour), minute=int(minute), 
                                                second=int(second), microsecond=int(millisec)*1000
                                            )
                                        )
                                    elif len(groups) == 7:  # YYYY-MM-DD format
                                        year, month, day, hour, minute, second, millisec = groups
                                        log_timestamp = datetime(
                                            int(year), int(month), int(day),
                                            int(hour), int(minute), int(second), int(millisec)*1000
                                        )
                                    elif len(groups) == 4:  # HH:MM:SS format
                                        hour, minute, second, millisec = groups
                                        log_timestamp = datetime.combine(
                                            current_date,
                                            datetime.min.time().replace(
                                                hour=int(hour), minute=int(minute), 
                                                second=int(second), microsecond=int(millisec)*1000
                                            )
                                        )
                                except ValueError:
                                    continue
                                break
                        
                        # Check for time gap to create new track (separate logic for each stream)
                        if is_raw_message:
                            # Handle raw coordinates message stream
                            if (log_timestamp and last_raw_timestamp and 
                                (log_timestamp - last_raw_timestamp).total_seconds() > TRACK_GAP_THRESHOLD):
                                print(f"Time gap of {(log_timestamp - last_raw_timestamp).total_seconds():.1f} seconds detected in raw coordinates stream, starting new track")
                                finalize_raw_track()
                        else:
                            # Handle regular NMEA stream
                            if (log_timestamp and last_valid_timestamp and 
                                (log_timestamp - last_valid_timestamp).total_seconds() > TRACK_GAP_THRESHOLD):
                                print(f"Time gap of {(log_timestamp - last_valid_timestamp).total_seconds():.1f} seconds detected, starting new track")
                                finalize_current_track()
                        
                        # Process each NMEA sentence found in the line
                        for nmea_sentence in nmea_matches:
                            try:
                                nmea_sentence = nmea_sentence.strip()
                                
                                # Skip NMEA messages that start with "s:1*78"
                                if nmea_sentence.startswith('s:1*78'):
                                    continue
                                
                                if nmea_sentence.startswith('$GPGGA') or nmea_sentence.startswith('$GNGGA'):
                                    # GGA - Global Positioning System Fix Data
                                    parts = nmea_sentence.split(',')
                                    if len(parts) >= 10:
                                        lat_str = parts[2]
                                        lat_dir = parts[3]
                                        lon_str = parts[4]
                                        lon_dir = parts[5]
                                        quality = parts[6]
                                        altitude_str = parts[9]
                                        
                                        # Only use data with GPS fix (quality > 0)
                                        if quality and int(quality) > 0:
                                            # Parse coordinates
                                            if lat_str and lon_str and lat_dir and lon_dir:
                                                try:
                                                    # Convert DDMM.MMMM to decimal degrees
                                                    lat_deg = int(float(lat_str) // 100)
                                                    lat_min = float(lat_str) % 100
                                                    current_lat = lat_deg + lat_min / 60.0
                                                    if lat_dir == 'S':
                                                        current_lat = -current_lat
                                                        
                                                    lon_deg = int(float(lon_str) // 100)
                                                    lon_min = float(lon_str) % 100
                                                    current_lon = lon_deg + lon_min / 60.0
                                                    if lon_dir == 'W':
                                                        current_lon = -current_lon
                                                        
                                                    # Parse altitude
                                                    if altitude_str:
                                                        current_alt = float(altitude_str)
                                                        
                                                except ValueError:
                                                    continue
                                
                                elif nmea_sentence.startswith('$GPRMC') or nmea_sentence.startswith('$GNRMC'):
                                    # RMC - Recommended Minimum Course
                                    parts = nmea_sentence.split(',')
                                    if len(parts) >= 10:
                                        status = parts[2]
                                        speed_knots = parts[7]
                                        course_str = parts[8]
                                        date_str = parts[9]
                                        
                                        # Only use data with valid fix
                                        if status == 'A':  # Active/Valid
                                            # Parse speed (convert knots to km/h)
                                            if speed_knots:
                                                try:
                                                    current_speed = float(speed_knots) * 1.852
                                                except ValueError:
                                                    pass
                                            
                                            # Parse course
                                            if course_str:
                                                try:
                                                    current_course = float(course_str)
                                                except ValueError:
                                                    pass
                                            
                                            # Parse date (DDMMYY) to update current_date
                                            if date_str and len(date_str) == 6:
                                                try:
                                                    day = int(date_str[:2])
                                                    month = int(date_str[2:4])
                                                    year = 2000 + int(date_str[4:6])
                                                    current_date = date(year, month, day)
                                                except ValueError:
                                                    pass
                                
                                # If we have complete coordinate data and timestamp, record it
                                if (log_timestamp and current_lat is not None and current_lon is not None):
                                    # Apply date filter if specified
                                    if filter_date is None or log_timestamp.date() == filter_date:
                                        
                                        if is_raw_message:
                                            # Handle raw coordinates track
                                            # Only add if we have new coordinates or significant time difference
                                            if (not current_raw_track or 
                                                abs((log_timestamp - current_raw_track[-1][0]).total_seconds()) > 1 or
                                                abs(current_lat - current_raw_track[-1][2]) > 0.0001 or
                                                abs(current_lon - current_raw_track[-1][1]) > 0.0001):
                                                
                                                current_raw_track.append((
                                                    log_timestamp,
                                                    current_lon,
                                                    current_lat,
                                                    current_alt or 0,
                                                    current_speed or 0,
                                                    current_course or 0
                                                ))
                                                
                                                last_raw_timestamp = log_timestamp
                                        else:
                                            # Handle regular track
                                            # Only add if we have new coordinates or significant time difference
                                            if (not current_track or 
                                                abs((log_timestamp - current_track[-1][0]).total_seconds()) > 1 or
                                                abs(current_lat - current_track[-1][2]) > 0.0001 or
                                                abs(current_lon - current_track[-1][1]) > 0.0001):
                                                
                                                current_track.append((
                                                    log_timestamp,
                                                    current_lon,
                                                    current_lat,
                                                    current_alt or 0,
                                                    current_speed or 0,
                                                    current_course or 0
                                                ))
                                                
                                                last_valid_timestamp = log_timestamp
                            
                            except Exception as e:
                                continue  # Skip malformed NMEA sentences
            
            except Exception as e:
                print(f"Warning: Error processing {log_file}: {e}")
                continue
        
        # Finalize both track types
        finalize_current_track()
        if include_raw:
            finalize_raw_track()
        
        total_points = sum(len(track) for track in all_tracks)
        print(f"Extracted {total_points} GPS coordinates across {len(all_tracks)} tracks from Android logs")
        return all_tracks
        
    except Exception as e:
        print(f"Error processing Android logs: {e}")
        return []

def create_kml_track(tracks, track_name="GPS Track", description="Track converted from Android logs"):
    """
    Create a KML document with multiple GPS tracks from coordinates.
    
    Args:
        tracks (list): List of tracks, where each track is a list of tuples (timestamp, lon, lat, alt, speed, course)
        track_name (str): Base name for the tracks
        description (str): Description of the tracks
        
    Returns:
        str: KML document as string
    """
    if not tracks or not any(tracks):
        return None
    
    # Create KML root element
    kml = ET.Element('kml')
    kml.set('xmlns', 'http://www.opengis.net/kml/2.2')
    
    # Create Document
    document = ET.SubElement(kml, 'Document')
    
    # Add document name and description
    name_elem = ET.SubElement(document, 'name')
    name_elem.text = track_name
    
    desc_elem = ET.SubElement(document, 'description')
    total_points = sum(len(track) for track in tracks)
    desc_elem.text = f"{description}\nGenerated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\nTracks: {len(tracks)}, Total points: {total_points}"
    
    # Create styles for different tracks
    colors = ['ff0000ff', 'ff00ff00', 'ffff0000', 'ff00ffff', 'ffff00ff', 'ffffff00']
    
    for i in range(min(len(tracks), len(colors))):
        style = ET.SubElement(document, 'Style')
        style.set('id', f'trackStyle{i+1}')
        
        line_style = ET.SubElement(style, 'LineStyle')
        color_elem = ET.SubElement(line_style, 'color')
        color_elem.text = colors[i % len(colors)]
        width_elem = ET.SubElement(line_style, 'width')
        width_elem.text = '3'
    
    # Create a folder to contain all tracks
    folder = ET.SubElement(document, 'Folder')
    folder_name = ET.SubElement(folder, 'name')
    folder_name.text = f"GPS Tracks ({len(tracks)} tracks)"
    
    # Process each track
    for track_idx, coordinates in enumerate(tracks):
        if not coordinates:
            continue
            
        # Create Placemark for this track
        placemark = ET.SubElement(folder, 'Placemark')
        
        placemark_name = ET.SubElement(placemark, 'name')
        placemark_name.text = f"{track_name} - Track {track_idx + 1}"
        
        placemark_desc = ET.SubElement(placemark, 'description')
        start_time = coordinates[0][0].strftime('%Y-%m-%d %H:%M:%S')
        end_time = coordinates[-1][0].strftime('%Y-%m-%d %H:%M:%S')
        duration = coordinates[-1][0] - coordinates[0][0]
        placemark_desc.text = f"Track {track_idx + 1}: {start_time} to {end_time}\nDuration: {duration}\nPoints: {len(coordinates)}"
        
        # Reference the style
        style_url = ET.SubElement(placemark, 'styleUrl')
        style_url.text = f'#trackStyle{(track_idx % len(colors)) + 1}'
        
        # Create LineString for the track
        linestring = ET.SubElement(placemark, 'LineString')
        
        tessellate = ET.SubElement(linestring, 'tessellate')
        tessellate.text = '1'
        
        altitude_mode = ET.SubElement(linestring, 'altitudeMode')
        altitude_mode.text = 'absolute'
        
        # Create coordinates string
        coords_elem = ET.SubElement(linestring, 'coordinates')
        coord_strings = []
        for timestamp, lon, lat, alt, speed, course in coordinates:
            coord_strings.append(f"{lon},{lat},{alt}")
        
        coords_elem.text = '\n' + '\n'.join(coord_strings) + '\n'
        
        # Add start point for this track
        start_placemark = ET.SubElement(folder, 'Placemark')
        start_name = ET.SubElement(start_placemark, 'name')
        start_name.text = f'Track {track_idx + 1} Start'
        start_desc = ET.SubElement(start_placemark, 'description')
        start_desc.text = f"Track {track_idx + 1} start: {coordinates[0][0].strftime('%Y-%m-%d %H:%M:%S')}"
        
        start_point = ET.SubElement(start_placemark, 'Point')
        start_coords = ET.SubElement(start_point, 'coordinates')
        start_coords.text = f"{coordinates[0][1]},{coordinates[0][2]},{coordinates[0][3]}"
        
        # Add end point for this track
        end_placemark = ET.SubElement(folder, 'Placemark')
        end_name = ET.SubElement(end_placemark, 'name')
        end_name.text = f'Track {track_idx + 1} End'
        end_desc = ET.SubElement(end_placemark, 'description')
        end_desc.text = f"Track {track_idx + 1} end: {coordinates[-1][0].strftime('%Y-%m-%d %H:%M:%S')}"
        
        end_point = ET.SubElement(end_placemark, 'Point')
        end_coords = ET.SubElement(end_point, 'coordinates')
        end_coords.text = f"{coordinates[-1][1]},{coordinates[-1][2]},{coordinates[-1][3]}"
    
    # Convert to pretty-printed string
    rough_string = ET.tostring(kml, encoding='unicode')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent='  ')

def parse_date_argument(date_str):
    """
    Parse date argument, supporting 'today' and YYYY-MM-DD format.
    
    Args:
        date_str (str): Date string ('today' or 'YYYY-MM-DD')
        
    Returns:
        date: Parsed date object
    """
    if date_str.lower() == 'today':
        return date.today()
    
    try:
        # Parse YYYY-MM-DD format
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Invalid date format: '{date_str}'. Use 'today' or 'YYYY-MM-DD' format."
        )

def main():
    """Main function to handle command line arguments and execute conversion."""
    parser = argparse.ArgumentParser(
        description='Convert Android log files containing NMEA GPS messages to KML track format',
        epilog='''
Examples:
  %(prog)s logd/ -o gps_track.kml
  %(prog)s logd/ --date today -o today_track.kml
  %(prog)s logd/ --date 2026-01-13 --name "Daily Commute" -o commute.kml
  %(prog)s logd/ --raw -o tracks_with_raw.kml
        ''',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('logd_folder', 
                       help='Path to the Android logd folder containing log files')
    
    parser.add_argument('-o', '--output', 
                       required=True,
                       help='Output KML file path')
    
    parser.add_argument('--date',
                       type=parse_date_argument,
                       help='Filter data by date. Use "today" or YYYY-MM-DD format (e.g., 2026-01-13)')
    
    parser.add_argument('--name',
                       default='GPS Track',
                       help='Name for the GPS track (default: GPS Track)')
    
    parser.add_argument('--description',
                       default='Track converted from Android logs',
                       help='Description for the GPS track')
    
    parser.add_argument('--raw',
                       action='store_true',
                       help='Include raw coordinates (s:1*78) tracks in the output')
    
    parser.add_argument('--version',
                       action='version',
                       version='Android Logs to KML Converter 1.0.0')
    
    args = parser.parse_args()
    
    # Check if logd folder exists
    if not os.path.exists(args.logd_folder):
        print(f"Error: Logd folder '{args.logd_folder}' not found.")
        sys.exit(1)
    
    if not os.path.isdir(args.logd_folder):
        print(f"Error: '{args.logd_folder}' is not a directory.")
        sys.exit(1)
    
    # Parse Android logs for GPS coordinates
    date_filter_str = f" for date {args.date}" if args.date else ""
    raw_filter_str = " (including raw coordinates)" if args.raw else ""
    print(f"Extracting GPS coordinates from {args.logd_folder}{date_filter_str}{raw_filter_str}")
    
    tracks = parse_android_logs_for_coordinates(args.logd_folder, args.date, args.raw)
    
    if not tracks or not any(tracks):
        print("No GPS coordinates found in log files.")
        sys.exit(1)
    
    # Calculate statistics for all tracks
    all_coordinates = []
    for track in tracks:
        all_coordinates.extend(track)
    
    print(f"Found {len(tracks)} separate tracks with {len(all_coordinates)} total GPS coordinates")
    
    if all_coordinates:
        print(f"Time range: {all_coordinates[0][0]} to {all_coordinates[-1][0]}")
        
        # Calculate some basic statistics
        lats = [coord[2] for coord in all_coordinates]
        lons = [coord[1] for coord in all_coordinates]
        alts = [coord[3] for coord in all_coordinates]
        speeds = [coord[4] for coord in all_coordinates]
        
        print(f"Latitude range: {min(lats):.6f} to {max(lats):.6f}")
        print(f"Longitude range: {min(lons):.6f} to {max(lons):.6f}")
        print(f"Altitude range: {min(alts):.1f}m to {max(alts):.1f}m")
        
        avg_speed = sum(s for s in speeds if s > 0) / len([s for s in speeds if s > 0]) if any(s > 0 for s in speeds) else 0
        if avg_speed > 0:
            print(f"Average speed: {avg_speed:.1f} km/h")
        
        # Print track summary
        print("\nTrack Summary:")
        for i, track in enumerate(tracks, 1):
            duration = track[-1][0] - track[0][0] if len(track) > 1 else 0
            print(f"  Track {i}: {len(track)} points, {duration} duration")
    
    # Create KML document
    print("Creating KML document with multiple tracks...")
    kml_content = create_kml_track(tracks, args.name, args.description)
    
    if not kml_content:
        print("Error creating KML document.")
        sys.exit(1)
    
    # Write KML file
    try:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(kml_content)
        
        print(f"KML track saved to {args.output}")
        print(f"You can open this file in Google Earth or other mapping applications.")
        
    except Exception as e:
        print(f"Error writing KML file: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
