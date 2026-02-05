#!/usr/bin/env python3
"""
This script reads KML, NMEA files, or Android log folders containing GPS track data
and creates graphs showing speed over time extracted from VTG NMEA messages.
"""

import xml.etree.ElementTree as ET
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, date, timedelta
import argparse
import sys
import os
import numpy as np
import re
import glob

def parse_android_log_speed_data(logd_folder):
    """
    Parse speed data from Android log files containing NMEA VTG messages.

    Args:
        logd_folder (str): Path to the logd folder containing Android log files

    Returns:
        tuple: (timestamps, speeds_kmh, coordinates, bearings)
    """
    try:
        timestamps = []
        speeds_kmh = []
        coordinates = []
        bearings = []

        # Enhanced pattern to match NMEA sentences in Android logs - more flexible
        nmea_pattern = re.compile(r'\$G[NP][A-Z]{3}[^$\r\n]*(?:\*[0-9A-F]{2})?')

        # Android log timestamp patterns
        timestamp_patterns = [
            # Common Android logcat format: MM-DD HH:MM:SS.mmm
            re.compile(r'(\d{2})-(\d{2})\s+(\d{2}):(\d{2}):(\d{2})\.(\d{3})'),
            # Alternative format: YYYY-MM-DD HH:MM:SS.mmm
            re.compile(r'(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2}):(\d{2})\.(\d{3})'),
            # Simple timestamp: HH:MM:SS.mmm
            re.compile(r'(\d{2}):(\d{2}):(\d{2})\.(\d{3})'),
        ]

        current_date = datetime.now().date()  # Default to current date
        current_speed = None
        current_bearing = None
        current_lat = None
        current_lon = None

        # Get all log files in the logd folder
        log_files = glob.glob(os.path.join(logd_folder, '*'))
        log_files = [f for f in log_files if os.path.isfile(f)]

        if not log_files:
            print(f"No log files found in {logd_folder}")
            return [], [], [], []

        print(f"Processing {len(log_files)} log files from {logd_folder}")

        # Process files in reverse order (newest first)
        for log_file in sorted(log_files, reverse=True):
            print(f"Processing {os.path.basename(log_file)}...")

            try:
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as file:
                    for line_num, line in enumerate(file, 1):
                        line = line.strip()
                        if not line:
                            continue

                        # Skip lines containing "s:1*78" (raw coordinates)
                        if 's:1*78' in line:
                            continue

                        # Look for NMEA sentences in the log line
                        nmea_matches = nmea_pattern.findall(line)
                        if not nmea_matches:
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

                        # If no timestamp found, use a default one for debugging
                        if log_timestamp is None:
                            log_timestamp = datetime.now()

                        # Validate and fix timestamp chronological order
                        log_timestamp = validate_and_fix_timestamp(log_timestamp, timestamps, line_num, log_file)

                        # Process each NMEA sentence found in the line
                        for nmea_sentence in nmea_matches:
                            try:
                                nmea_sentence = nmea_sentence.strip()

                                if nmea_sentence.startswith('$GPVTG') or nmea_sentence.startswith('$GNVTG'):
                                    # VTG - Velocity Made Good
                                    parts = nmea_sentence.split(',')

                                    if len(parts) >= 8:
                                        # VTG format: $GPVTG,course_t,T,course_m,M,speed_n,N,speed_k,K,mode*checksum
                                        course_true_str = parts[1]  # True track made good (degrees)
                                        speed_kmh_str = parts[7]  # Speed in km/h
                                        speed_knots_str = parts[5]  # Speed in knots (fallback)
                                        mode_field = parts[8] if len(parts) > 8 else ''
                                        mode = mode_field.split('*')[0] if '*' in mode_field else mode_field

                                        # Process bearing data
                                        try:
                                            if course_true_str and course_true_str != '':
                                                current_bearing = float(course_true_str)
                                        except ValueError:
                                            pass

                                        # Process speed data
                                        try:
                                            # Prefer km/h over knots for better accuracy
                                            if speed_kmh_str and speed_kmh_str != '' and speed_kmh_str != '0.000':
                                                current_speed = float(speed_kmh_str)
                                            elif speed_knots_str and speed_knots_str != '' and speed_knots_str != '0.000':
                                                # Convert knots to km/h
                                                current_speed = float(speed_knots_str) * 1.852
                                        except ValueError:
                                            pass

                                elif nmea_sentence.startswith('$GPRMC') or nmea_sentence.startswith('$GNRMC'):
                                    # RMC - Recommended Minimum Course (fallback for speed and bearing)
                                    parts = nmea_sentence.split(',')

                                    if len(parts) >= 9:
                                        status = parts[2]
                                        speed_knots_str = parts[7]  # Speed in knots
                                        course_str = parts[8]  # Track angle in degrees (True)

                                        # Only use valid fixes
                                        if status == 'A':
                                            # Parse bearing (fallback if no VTG)
                                            if course_str and course_str != '' and current_bearing is None:
                                                try:
                                                    current_bearing = float(course_str)
                                                except ValueError:
                                                    pass

                                            # Parse speed (fallback if no VTG)
                                            if speed_knots_str and speed_knots_str != '' and current_speed is None:
                                                try:
                                                    # Convert knots to km/h (fallback if no VTG)
                                                    current_speed = float(speed_knots_str) * 1.852
                                                except ValueError:
                                                    pass

                                elif nmea_sentence.startswith('$GPGGA') or nmea_sentence.startswith('$GNGGA'):
                                    # GGA - Global Positioning System Fix Data (for coordinates)
                                    parts = nmea_sentence.split(',')
                                    if len(parts) >= 6:
                                        lat_str = parts[2]
                                        lat_dir = parts[3]
                                        lon_str = parts[4]
                                        lon_dir = parts[5]
                                        quality = parts[6]

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
                                                except ValueError:
                                                    pass

                                # If we have speed data and a timestamp, record it
                                if current_speed is not None:
                                    # Only add if we have new data or significant time difference
                                    if (not timestamps or
                                        abs((log_timestamp - timestamps[-1]).total_seconds()) > 1):

                                        timestamps.append(log_timestamp)
                                        speeds_kmh.append(current_speed)
                                        bearings.append(current_bearing if current_bearing is not None else 0.0)

                                        if current_lat is not None and current_lon is not None:
                                            coordinates.append((current_lon, current_lat))
                                        else:
                                            coordinates.append(None)

                                    # Reset current data after recording
                                    current_speed = None
                                    current_bearing = None

                            except Exception as e:
                                continue  # Skip malformed NMEA sentences

            except Exception as e:
                print(f"Warning: Error processing {log_file}: {e}")
                continue

        print(f"Parsed {len(timestamps)} valid speed records from Android logs")
        return timestamps, speeds_kmh, coordinates, bearings

    except Exception as e:
        print(f"Error processing Android logs: {e}")
        return [], [], [], []

def parse_nmea_speed_data(nmea_file):
    """
    Parse speed data from an NMEA file.

    Args:
        nmea_file (str): Path to the NMEA file

    Returns:
        tuple: (timestamps, speeds_kmh, coordinates, bearings)
    """
    try:
        timestamps = []
        speeds_kmh = []
        coordinates = []
        bearings = []

        current_date = None
        current_time = None
        current_speed = None
        current_bearing = None
        current_lat = None
        current_lon = None

        with open(nmea_file, 'r', encoding='utf-8', errors='ignore') as file:
            for line_num, line in enumerate(file, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    # Parse different NMEA sentence types
                    if line.startswith('$GPVTG') or line.startswith('$GNVTG'):
                        # VTG - Velocity Made Good
                        parts = line.split(',')
                        if len(parts) >= 8:
                            course_true_str = parts[1]  # True track made good (degrees)
                            speed_kmh_str = parts[7]  # Speed in km/h
                            speed_knots_str = parts[5]  # Speed in knots (fallback)
                            mode = parts[8].split('*')[0] if len(parts) > 8 else ''

                            # Only use data with valid mode
                            if mode and mode in ['A', 'D']:
                                try:
                                    if course_true_str and course_true_str != '':
                                        current_bearing = float(course_true_str)
                                except ValueError:
                                    pass

                                try:
                                    if speed_kmh_str and speed_kmh_str != '':
                                        current_speed = float(speed_kmh_str)
                                    elif speed_knots_str and speed_knots_str != '':
                                        current_speed = float(speed_knots_str) * 1.852
                                except ValueError:
                                    pass

                    elif line.startswith('$GPRMC') or line.startswith('$GNRMC'):
                        # RMC - Recommended Minimum Course
                        parts = line.split(',')
                        if len(parts) >= 10:
                            time_str = parts[1]
                            status = parts[2]
                            speed_knots_str = parts[7]
                            course_str = parts[8]
                            date_str = parts[9]

                            # Parse date (DDMMYY)
                            if date_str and len(date_str) == 6:
                                day = int(date_str[:2])
                                month = int(date_str[2:4])
                                year = 2000 + int(date_str[4:6])  # Assume 20xx
                                current_date = date(year, month, day)

                            # Parse time (HHMMSS.SS)
                            if time_str and len(time_str) >= 6:
                                hours = int(time_str[:2])
                                minutes = int(time_str[2:4])
                                seconds = int(float(time_str[4:]))
                                current_time = (hours, minutes, seconds)

                            # Parse bearing (fallback if no VTG)
                            if status == 'A' and course_str and course_str != '' and current_bearing is None:
                                try:
                                    current_bearing = float(course_str)
                                except ValueError:
                                    pass

                            # Parse speed (fallback if no VTG)
                            if status == 'A' and speed_knots_str and current_speed is None:
                                try:
                                    current_speed = float(speed_knots_str) * 1.852
                                except ValueError:
                                    pass

                    elif line.startswith('$GPGGA') or line.startswith('$GNGGA'):
                        # GGA - Global Positioning System Fix Data
                        parts = line.split(',')
                        if len(parts) >= 8:
                            time_str = parts[1]
                            lat_str = parts[2]
                            lat_dir = parts[3]
                            lon_str = parts[4]
                            lon_dir = parts[5]
                            quality = parts[6]

                            # Parse time (HHMMSS.SS)
                            if time_str and len(time_str) >= 6:
                                hours = int(time_str[:2])
                                minutes = int(time_str[2:4])
                                seconds = int(float(time_str[4:]))
                                current_time = (hours, minutes, seconds)

                            # Parse coordinates (only with valid fix)
                            if quality and int(quality) > 0:
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
                                    except ValueError:
                                        pass

                    # If we have complete data, record it
                    if (current_date and current_time and current_speed is not None):

                        timestamp = datetime.combine(
                            current_date,
                            datetime.min.time().replace(
                                hour=current_time[0],
                                minute=current_time[1],
                                second=current_time[2]
                            )
                        )

                        # Only add if we have new data
                        if not timestamps or timestamp != timestamps[-1]:
                            timestamps.append(timestamp)
                            speeds_kmh.append(current_speed)
                            bearings.append(current_bearing if current_bearing is not None else 0.0)

                            if current_lat is not None and current_lon is not None:
                                coordinates.append((current_lon, current_lat))
                            else:
                                coordinates.append(None)

                        # Reset current data after recording
                        current_speed = None
                        current_bearing = None

                except (ValueError, IndexError) as e:
                    print(f"Warning: Error parsing line {line_num}: {e}")
                    continue

        print(f"Parsed {len(timestamps)} valid NMEA speed records")
        return timestamps, speeds_kmh, coordinates, bearings

    except FileNotFoundError:
        print(f"Error: NMEA file '{nmea_file}' not found.")
        return [], [], [], []
    except Exception as e:
        print(f"Error reading NMEA file: {e}")
        return [], [], [], []

def parse_kml_speed_data(kml_file):
    """
    Parse speed data from a KML file.

    Args:
        kml_file (str): Path to the KML file

    Returns:
        tuple: (timestamps, speeds_kmh, coordinates, bearings)
    """
    try:
        tree = ET.parse(kml_file)
        root = tree.getroot()

        timestamps = []
        speeds_kmh = []
        coordinates = []
        bearings = []

        # Look for gx:Track elements with speed data
        for track in root.iter():
            if track.tag.endswith('Track'):
                when_elements = track.findall('.//{http://www.google.com/kml/ext/2.2}when')
                coord_elements = track.findall('.//{http://www.google.com/kml/ext/2.2}coord')

                # Look for speed and bearing data in ExtendedData
                speed_data = []
                bearing_data = []
                for extended_data in track.iter():
                    if extended_data.tag.endswith('ExtendedData'):
                        for schema_data in extended_data.iter():
                            if schema_data.tag.endswith('SimpleArrayData'):
                                if schema_data.get('name') == 'speed':
                                    for value in schema_data.findall('.//{http://www.google.com/kml/ext/2.2}value'):
                                        try:
                                            speed_data.append(float(value.text or 0))
                                        except ValueError:
                                            speed_data.append(0)
                                elif schema_data.get('name') == 'bearing':
                                    for value in schema_data.findall('.//{http://www.google.com/kml/ext/2.2}value'):
                                        try:
                                            bearing_data.append(float(value.text or 0))
                                        except ValueError:
                                            bearing_data.append(0)

                # Combine timestamps, coordinates, speeds, and bearings
                min_len = min(len(when_elements), len(coord_elements))
                if speed_data:
                    min_len = min(min_len, len(speed_data))

                for i in range(min_len):
                    # Parse timestamp
                    time_str = when_elements[i].text.strip()
                    try:
                        if 'T' in time_str:
                            if time_str.endswith('Z'):
                                timestamp = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                            else:
                                timestamp = datetime.fromisoformat(time_str)
                        else:
                            timestamp = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
                        timestamps.append(timestamp)
                    except ValueError:
                        continue

                    # Parse coordinates
                    coord_str = coord_elements[i].text.strip()
                    coord_parts = coord_str.split()
                    if len(coord_parts) >= 2:
                        lon, lat = float(coord_parts[0]), float(coord_parts[1])
                        coordinates.append((lon, lat))
                    else:
                        coordinates.append(None)

                    # Add speed data
                    if speed_data and i < len(speed_data):
                        speeds_kmh.append(speed_data[i])
                    else:
                        speeds_kmh.append(0)

                    # Add bearing data
                    if bearing_data and i < len(bearing_data):
                        bearings.append(bearing_data[i])
                    else:
                        bearings.append(0.0)

        # If no speed data found, generate synthetic data for demonstration
        if not speeds_kmh and timestamps:
            print("No speed data found in KML. Generating synthetic data for demonstration.")
            np.random.seed(42)  # For reproducible results
            base_speed = 30  # km/h

            for i, ts in enumerate(timestamps):
                # Add some variation
                speed_variation = np.random.uniform(-10, 15)
                speed = max(0, min(80, base_speed + speed_variation))
                speeds_kmh.append(speed)
                bearings.append(np.random.uniform(0, 360))  # Random bearing for demo

        print(f"Parsed {len(timestamps)} KML records with speed data")
        return timestamps, speeds_kmh, coordinates, bearings

    except ET.ParseError as e:
        print(f"Error parsing KML file: {e}")
        return [], [], [], []
    except Exception as e:
        print(f"Unexpected error: {e}")
        return [], [], [], []

def calculate_bearing_accuracy(coordinates, bearings):
    """
    Calculate bearing accuracy by comparing NMEA bearing with calculated bearing from coordinates.

    Args:
        coordinates (list): List of coordinate tuples (lon, lat)
        bearings (list): List of bearing values from NMEA messages

    Returns:
        list: Bearing accuracy differences in degrees
    """
    if len(coordinates) < 2 or len(bearings) < 2:
        return []

    bearing_accuracy = []

    for i in range(1, len(coordinates)):
        if coordinates[i] is None or coordinates[i-1] is None:
            bearing_accuracy.append(None)
            continue

        # Calculate bearing between consecutive coordinates
        lon1, lat1 = coordinates[i-1]
        lon2, lat2 = coordinates[i]

        # Convert to radians
        lat1_rad = np.radians(lat1)
        lat2_rad = np.radians(lat2)
        delta_lon_rad = np.radians(lon2 - lon1)

        # Calculate bearing using great circle formula
        y = np.sin(delta_lon_rad) * np.cos(lat2_rad)
        x = np.cos(lat1_rad) * np.sin(lat2_rad) - np.sin(lat1_rad) * np.cos(lat2_rad) * np.cos(delta_lon_rad)

        calculated_bearing = np.degrees(np.arctan2(y, x))

        # Normalize to 0-360 degrees
        calculated_bearing = (calculated_bearing + 360) % 360

        # Compare with NMEA bearing
        nmea_bearing = bearings[i]
        if nmea_bearing is not None and nmea_bearing > 0:
            # Calculate the difference (shortest angular distance)
            diff = abs(calculated_bearing - nmea_bearing)
            if diff > 180:
                diff = 360 - diff
            bearing_accuracy.append(diff)
        else:
            bearing_accuracy.append(None)

    return bearing_accuracy

def filter_data_by_date(timestamps, speeds_kmh, coordinates, bearings, filter_date):
    """
    Filter data by a specific date.

    Args:
        timestamps (list): List of datetime objects
        speeds_kmh (list): Speed values in km/h
        coordinates (list): List of coordinate tuples
        bearings (list): List of bearing values
        filter_date (date): Date to filter by

    Returns:
        tuple: Filtered (timestamps, speeds_kmh, coordinates, bearings)
    """
    if not timestamps:
        return timestamps, speeds_kmh, coordinates, bearings

    filtered_timestamps = []
    filtered_speeds = []
    filtered_coords = []
    filtered_bearings = []

    for i, ts in enumerate(timestamps):
        if ts.date() == filter_date:
            filtered_timestamps.append(ts)
            if i < len(speeds_kmh):
                filtered_speeds.append(speeds_kmh[i])
            if i < len(coordinates):
                filtered_coords.append(coordinates[i])
            if i < len(bearings):
                filtered_bearings.append(bearings[i])

    print(f"Filtered to {len(filtered_timestamps)} speed data points for date {filter_date}")
    return filtered_timestamps, filtered_speeds, filtered_coords, filtered_bearings

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

def detect_file_type(filepath):
    """
    Detect if the input is KML file, NMEA file, or Android logd folder.

    Args:
        filepath (str): Path to the file or folder

    Returns:
        str: 'kml', 'nmea', 'android_logs', or 'unknown'
    """
    try:
        # Check if it's a directory (potentially Android logs)
        if os.path.isdir(filepath):
            # Check if it contains log files or is named 'logd'
            if os.path.basename(filepath).lower() == 'logd' or any(
                os.path.isfile(os.path.join(filepath, f))
                for f in os.listdir(filepath)
            ):
                return 'android_logs'
            return 'unknown'

        # File analysis
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as file:
            # Read first few lines
            lines = [file.readline().strip() for _ in range(10)]
            content = ' '.join(lines).lower()

            # Check for KML markers
            if '<?xml' in content or '<kml' in content or 'xmlns' in content:
                return 'kml'

            # Check for NMEA markers
            if any(line.startswith('$GP') or line.startswith('$GN') for line in lines):
                return 'nmea'

            # Check for Android log format with NMEA sentences
            for line in lines:
                if '$GP' in line or '$GN' in line:
                    return 'android_logs'

            return 'unknown'

    except Exception:
        return 'unknown'

def plot_speed_data(timestamps, speeds_kmh, bearings=None, coordinates=None, title="GPS Speed Data", filepath=None, show_bearing=False):
    """
    Create a plot showing speed over time, optionally with bearing accuracy.

    Args:
        timestamps (list): List of datetime objects
        speeds_kmh (list): Speed values in km/h
        bearings (list, optional): List of bearing values
        coordinates (list, optional): List of coordinate tuples
        title (str): Plot title
        filepath (str, optional): Path to save the plot
        show_bearing (bool): Whether to show bearing accuracy subplot
    """
    if not timestamps or not speeds_kmh:
        print("No speed data to plot")
        return

    # Create the plot
    if show_bearing and bearings and coordinates:
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))

        # Speed plot
        ax1.plot(timestamps, speeds_kmh, 'g-', linewidth=2,
                label='Speed (km/h)', marker='o', markersize=3, alpha=0.8)

        ax1.set_ylabel('Speed (km/h)', fontsize=12)
        ax1.set_title(title, fontsize=14, pad=20)
        ax1.legend(fontsize=11)
        ax1.grid(True, alpha=0.3)
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        ax1.xaxis.set_major_locator(mdates.MinuteLocator(interval=5))

        # Set y-axis limits for speed
        if speeds_kmh:
            max_speed = max(speeds_kmh)
            ax1.set_ylim(0, max_speed * 1.1)

        # Add speed statistics
        if speeds_kmh:
            avg_speed = np.mean(speeds_kmh)
            max_speed = max(speeds_kmh)
            min_speed = min(speeds_kmh)

            stats_text = f"Avg Speed: {avg_speed:.1f} km/h\n"
            stats_text += f"Max Speed: {max_speed:.1f} km/h\n"
            stats_text += f"Min Speed: {min_speed:.1f} km/h\n"
            stats_text += f"Data Points: {len(timestamps)}"

            ax1.text(0.02, 0.98, stats_text, transform=ax1.transAxes,
                   fontsize=10, verticalalignment='top',
                   bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.8))

        # Bearing accuracy plot
        bearing_accuracy = calculate_bearing_accuracy(coordinates, bearings)
        if bearing_accuracy:
            # Filter out None values for plotting
            filtered_times = []
            filtered_accuracy = []
            for i, acc in enumerate(bearing_accuracy):
                if acc is not None and i + 1 < len(timestamps):
                    filtered_times.append(timestamps[i + 1])
                    filtered_accuracy.append(acc)

            if filtered_accuracy:
                ax2.plot(filtered_times, filtered_accuracy, 'r-', linewidth=2,
                        label='Bearing Accuracy Error (degrees)', marker='o', markersize=3, alpha=0.8)

                ax2.set_xlabel('Time', fontsize=12)
                ax2.set_ylabel('Bearing Error (degrees)', fontsize=12)
                ax2.set_title('Bearing Accuracy (NMEA vs Calculated)', fontsize=12)
                ax2.legend(fontsize=11)
                ax2.grid(True, alpha=0.3)
                ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
                ax2.xaxis.set_major_locator(mdates.MinuteLocator(interval=5))

                # Add bearing statistics
                avg_error = np.mean(filtered_accuracy)
                max_error = max(filtered_accuracy)
                min_error = min(filtered_accuracy)

                bearing_stats_text = f"Avg Error: {avg_error:.1f}°\n"
                bearing_stats_text += f"Max Error: {max_error:.1f}°\n"
                bearing_stats_text += f"Min Error: {min_error:.1f}°\n"
                bearing_stats_text += f"Data Points: {len(filtered_accuracy)}"

                ax2.text(0.02, 0.98, bearing_stats_text, transform=ax2.transAxes,
                       fontsize=10, verticalalignment='top',
                       bbox=dict(boxstyle='round', facecolor='lightcoral', alpha=0.8))
            else:
                ax2.text(0.5, 0.5, 'No bearing accuracy data available',
                        ha='center', va='center', transform=ax2.transAxes)

        plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')
        plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')
    else:
        fig, ax = plt.subplots(figsize=(12, 8))

        # Plot the speed data
        ax.plot(timestamps, speeds_kmh, 'g-', linewidth=2,
                label='Speed (km/h)', marker='o', markersize=3, alpha=0.8)

        # Customize the plot
        ax.set_xlabel('Time', fontsize=12)
        ax.set_ylabel('Speed (km/h)', fontsize=12)
        ax.set_title(title, fontsize=14, pad=20)
        ax.legend(fontsize=11)
        ax.grid(True, alpha=0.3)

        # Format x-axis dates
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        ax.xaxis.set_major_locator(mdates.MinuteLocator(interval=5))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')

        # Set y-axis limits
        if speeds_kmh:
            max_speed = max(speeds_kmh)
            ax.set_ylim(0, max_speed * 1.1)

        # Add statistics
        if speeds_kmh:
            avg_speed = np.mean(speeds_kmh)
            max_speed = max(speeds_kmh)
            min_speed = min(speeds_kmh)

            stats_text = f"Avg Speed: {avg_speed:.1f} km/h\n"
            stats_text += f"Max Speed: {max_speed:.1f} km/h\n"
            stats_text += f"Min Speed: {min_speed:.1f} km/h\n"
            stats_text += f"Data Points: {len(timestamps)}"

            ax.text(0.02, 0.98, stats_text, transform=ax.transAxes,
                   fontsize=10, verticalalignment='top',
                   bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.8))

    plt.tight_layout()

    if filepath:
        plt.savefig(filepath, bbox_inches='tight', dpi=300,
                   facecolor='white', edgecolor='none')
        print(f"Speed plot saved to {filepath}")
    else:
        plt.show()

def create_detailed_speed_analysis(timestamps, speeds_kmh, bearings=None, coordinates=None, filepath=None, show_bearing=False):
    """
    Create a detailed speed analysis plot with multiple subplots.

    Args:
        timestamps (list): List of datetime objects
        speeds_kmh (list): Speed values in km/h
        bearings (list, optional): List of bearing values
        coordinates (list, optional): List of coordinate tuples
        filepath (str, optional): Path to save the plot
        show_bearing (bool): Whether to include bearing accuracy analysis
    """
    if not timestamps or not speeds_kmh:
        print("No speed data for detailed analysis")
        return

    if show_bearing and bearings and coordinates:
        fig = plt.figure(figsize=(15, 12))
        gs = fig.add_gridspec(3, 2, height_ratios=[1, 1, 1])

        # Speed over time
        ax1 = fig.add_subplot(gs[0, :])
        ax1.plot(timestamps, speeds_kmh, 'g-', linewidth=2, alpha=0.8)
        ax1.set_title('Speed Over Time', fontsize=12)
        ax1.set_ylabel('Speed (km/h)')
        ax1.grid(True, alpha=0.3)
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))

        # Speed distribution histogram
        ax2 = fig.add_subplot(gs[1, 0])
        ax2.hist(speeds_kmh, bins=30, alpha=0.7, color='green', edgecolor='black')
        ax2.set_title('Speed Distribution', fontsize=12)
        ax2.set_xlabel('Speed (km/h)')
        ax2.set_ylabel('Frequency')
        ax2.grid(True, alpha=0.3)
        ax2.axvline(np.mean(speeds_kmh), color='red', linestyle='--', label=f'Mean: {np.mean(speeds_kmh):.1f}')
        ax2.legend()

        # Bearing accuracy over time
        ax3 = fig.add_subplot(gs[1, 1])
        bearing_accuracy = calculate_bearing_accuracy(coordinates, bearings)
        if bearing_accuracy:
            filtered_times = []
            filtered_accuracy = []
            for i, acc in enumerate(bearing_accuracy):
                if acc is not None and i + 1 < len(timestamps):
                    filtered_times.append(timestamps[i + 1])
                    filtered_accuracy.append(acc)

            if filtered_accuracy:
                ax3.plot(filtered_times, filtered_accuracy, 'r-', linewidth=2, alpha=0.8)
                ax3.set_title('Bearing Accuracy Error', fontsize=12)
                ax3.set_ylabel('Error (degrees)')
                ax3.grid(True, alpha=0.3)
                ax3.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            else:
                ax3.text(0.5, 0.5, 'No bearing accuracy data', ha='center', va='center', transform=ax3.transAxes)
        else:
            ax3.text(0.5, 0.5, 'No bearing accuracy data', ha='center', va='center', transform=ax3.transAxes)

        # Speed vs time scatter plot
        ax4 = fig.add_subplot(gs[2, 0])
        scatter = ax4.scatter(timestamps, speeds_kmh, c=speeds_kmh, cmap='viridis', alpha=0.6, s=20)
        ax4.set_title('Speed Data Points', fontsize=12)
        ax4.set_ylabel('Speed (km/h)')
        ax4.grid(True, alpha=0.3)
        ax4.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        plt.colorbar(scatter, ax=ax4, label='Speed (km/h)')

        # Cumulative distance
        ax5 = fig.add_subplot(gs[2, 1])
        if len(timestamps) > 1:
            time_diffs = [(timestamps[i] - timestamps[i-1]).total_seconds() / 3600
                         for i in range(1, len(timestamps))]  # hours
            distances = [speeds_kmh[i] * time_diffs[i-1] for i in range(1, len(speeds_kmh))]  # km
            cumulative_distance = np.cumsum([0] + distances)

            ax5.plot(timestamps, cumulative_distance, 'b-', linewidth=2)
            ax5.set_title('Cumulative Distance', fontsize=12)
            ax5.set_ylabel('Distance (km)')
            ax5.grid(True, alpha=0.3)
            ax5.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))

            # Add total distance annotation
            total_dist = cumulative_distance[-1]
            ax5.text(0.02, 0.98, f'Total Distance: {total_dist:.2f} km',
                    transform=ax5.transAxes, fontsize=10, verticalalignment='top',
                    bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8))
        else:
            ax5.text(0.5, 0.5, 'Insufficient data for\ncumulative distance',
                    ha='center', va='center', transform=ax5.transAxes)

    else:
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))

        # Main time series plot
        ax1.plot(timestamps, speeds_kmh, 'g-', linewidth=2, alpha=0.8)
        ax1.set_title('Speed Over Time', fontsize=12)
        ax1.set_ylabel('Speed (km/h)')
        ax1.grid(True, alpha=0.3)
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))

        # Speed distribution histogram
        ax2.hist(speeds_kmh, bins=30, alpha=0.7, color='green', edgecolor='black')
        ax2.set_title('Speed Distribution', fontsize=12)
        ax2.set_xlabel('Speed (km/h)')
        ax2.set_ylabel('Frequency')
        ax2.grid(True, alpha=0.3)
        ax2.axvline(np.mean(speeds_kmh), color='red', linestyle='--', label=f'Mean: {np.mean(speeds_kmh):.1f}')
        ax2.legend()

        # Speed vs time scatter plot (colored by speed)
        scatter = ax3.scatter(timestamps, speeds_kmh, c=speeds_kmh, cmap='viridis', alpha=0.6, s=20)
        ax3.set_title('Speed Data Points (Colored by Speed)', fontsize=12)
        ax3.set_ylabel('Speed (km/h)')
        ax3.grid(True, alpha=0.3)
        ax3.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        plt.colorbar(scatter, ax=ax3, label='Speed (km/h)')

        # Cumulative distance (approximate)
        if len(timestamps) > 1:
            time_diffs = [(timestamps[i] - timestamps[i-1]).total_seconds() / 3600
                         for i in range(1, len(timestamps))]  # hours
            distances = [speeds_kmh[i] * time_diffs[i-1] for i in range(1, len(speeds_kmh))]  # km
            cumulative_distance = np.cumsum([0] + distances)

            ax4.plot(timestamps, cumulative_distance, 'b-', linewidth=2)
            ax4.set_title('Cumulative Distance', fontsize=12)
            ax4.set_ylabel('Distance (km)')
            ax4.grid(True, alpha=0.3)
            ax4.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))

            # Add total distance annotation
            total_dist = cumulative_distance[-1]
            ax4.text(0.02, 0.98, f'Total Distance: {total_dist:.2f} km',
                    transform=ax4.transAxes, fontsize=10, verticalalignment='top',
                    bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8))
        else:
            ax4.text(0.5, 0.5, 'Insufficient data for\ncumulative distance',
                    ha='center', va='center', transform=ax4.transAxes)

    plt.tight_layout()

    if filepath:
        plt.savefig(filepath, bbox_inches='tight', dpi=300,
                   facecolor='white', edgecolor='none')
        print(f"Detailed speed analysis saved to {filepath}")
    else:
        plt.show()

def trim_low_speed_points(timestamps, speeds_kmh, coordinates, bearings, min_speed):
    """
    Trim points with speed below a certain threshold from the start and end of the data.

    Args:
        timestamps (list): List of datetime objects
        speeds_kmh (list): Speed values in km/h
        coordinates (list): List of coordinate tuples
        bearings (list): List of bearing values
        min_speed (float): Minimum speed threshold in km/h

    Returns:
        tuple: Trimmed (timestamps, speeds_kmh, coordinates, bearings)
    """
    if not timestamps or not speeds_kmh:
        return timestamps, speeds_kmh, coordinates, bearings

    # Convert min_speed to float
    min_speed = float(min_speed)

    # Find first index with speed >= min_speed
    start_index = 0
    while start_index < len(speeds_kmh) and speeds_kmh[start_index] < min_speed:
        start_index += 1

    # Find last index with speed >= min_speed
    end_index = len(speeds_kmh) - 1
    while end_index >= 0 and speeds_kmh[end_index] < min_speed:
        end_index -= 1

    # If all points are below min_speed, return empty lists
    if start_index > end_index:
        return [], [], [], []

    # Trim the data
    trimmed_timestamps = timestamps[start_index:end_index+1]
    trimmed_speeds = speeds_kmh[start_index:end_index+1]
    trimmed_coords = coordinates[start_index:end_index+1]
    trimmed_bearings = bearings[start_index:end_index+1]

    print(f"Trimmed data to {len(trimmed_timestamps)} points (min speed: {min_speed} km/h)")
    return trimmed_timestamps, trimmed_speeds, trimmed_coords, trimmed_bearings

def validate_and_fix_timestamp(log_timestamp, timestamps, line_num, log_file):
    """
    Validate timestamp chronological order and fix if necessary.

    Args:
        log_timestamp: The timestamp to validate
        timestamps: List of existing timestamps
        line_num: Current line number for error reporting
        log_file: Current log file for error reporting

    Returns:
        datetime: Validated/corrected timestamp
    """
    if not timestamps:
        return log_timestamp

    # Check if timestamp is after the last timestamp (normal case)
    if log_timestamp >= timestamps[-1]:
        return log_timestamp

    # Timestamp is out of order - need to fix it
    print(f"Warning: Out-of-order timestamp at {os.path.basename(log_file)}:{line_num}")
    print(f"  Expected >= {timestamps[-1]}, got {log_timestamp}")

    # Find the correct position for interpolation
    if len(timestamps) >= 2:
        # Interpolate between last two timestamps
        time_diff = (timestamps[-1] - timestamps[-2]).total_seconds()
        # Add the same time difference to create next expected timestamp
        corrected_timestamp = timestamps[-1] + timedelta(seconds=time_diff)
        print(f"  Corrected to: {corrected_timestamp}")
        return corrected_timestamp
    else:
        # Only one previous timestamp, add 1 second
        corrected_timestamp = timestamps[-1] + timedelta(seconds=1)
        print(f"  Corrected to: {corrected_timestamp}")
        return corrected_timestamp

if __name__ == "__main__":
    """Main function to handle command line arguments and execute visualization."""
    parser = argparse.ArgumentParser(
        description='Analyze and visualize GPS speed data from KML files, NMEA files, or Android log folders',
        epilog='''
Examples:
  %(prog)s track.kml
  %(prog)s gps_log.nmea -o speed_plot.png
  %(prog)s logd/ --format android_logs --detailed
  %(prog)s logd/ --date today --output today_speed.png
  %(prog)s logd/ --date 2026-01-15 --detailed
  %(prog)s track.kml --detailed --output detailed_speed_analysis.png
  %(prog)s gps_data.txt --format nmea --title "NMEA Speed Analysis"
  %(prog)s logd/ --min-speed 5.0  # Trim points below 5 km/h
  %(prog)s logd/ --no-trim  # Keep all speed data including stationary
  %(prog)s logd/ --bearing  # Include bearing accuracy analysis
  %(prog)s logd/ --detailed --bearing  # Detailed analysis with bearing accuracy
        ''',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('input_path',
                       help='Path to the KML file, NMEA file, or Android logd folder containing GPS track data')

    parser.add_argument('-o', '--output',
                       help='Output file path for saving the visualization (PNG format)')

    parser.add_argument('--format',
                       choices=['auto', 'kml', 'nmea', 'android_logs'],
                       default='auto',
                       help='Input format (default: auto-detect)')

    parser.add_argument('--detailed',
                       action='store_true',
                       help='Create detailed analysis with multiple subplots')

    parser.add_argument('--title',
                       default='GPS Speed Data',
                       help='Title for the plot (default: GPS Speed Data)')

    parser.add_argument('--date',
                       type=parse_date_argument,
                       help='Filter data by date. Use "today" or YYYY-MM-DD format (e.g., 2026-01-15)')

    parser.add_argument('--min-speed',
                       type=float,
                       default=2.0,
                       help='Minimum speed threshold in km/h to trim start/end points (default: 2.0)')

    parser.add_argument('--no-trim',
                       action='store_true',
                       help='Skip trimming of low-speed points at start and end')

    parser.add_argument('--bearing',
                       action='store_true',
                       help='Include bearing accuracy analysis in the visualization')

    parser.add_argument('--version',
                       action='version',
                       version='GPS Speed Analyzer 1.1.0')

    args = parser.parse_args()

    # Check if input path exists
    if not os.path.exists(args.input_path):
        print(f"Error: Input path '{args.input_path}' not found.")
        sys.exit(1)

    # Detect file format
    if args.format == 'auto':
        file_type = detect_file_type(args.input_path)
        if file_type == 'unknown':
            print("Warning: Could not auto-detect format. Trying KML first, then NMEA...")
            file_type = 'kml'  # Default fallback
    else:
        file_type = args.format

    print(f"Analyzing speed data from {args.input_path} (format: {file_type})")

    # Parse the input based on format
    if file_type == 'android_logs':
        timestamps, speeds_kmh, coordinates, bearings = parse_android_log_speed_data(args.input_path)
    elif file_type == 'nmea':
        timestamps, speeds_kmh, coordinates, bearings = parse_nmea_speed_data(args.input_path)
    else:  # kml or fallback
        timestamps, speeds_kmh, coordinates, bearings = parse_kml_speed_data(args.input_path)

        # If KML parsing failed and format was auto, try NMEA then Android logs
        if not timestamps and args.format == 'auto':
            print("KML parsing failed, trying NMEA format...")
            timestamps, speeds_kmh, coordinates, bearings = parse_nmea_speed_data(args.input_path)

            if not timestamps:
                print("NMEA parsing failed, trying Android logs format...")
                timestamps, speeds_kmh, coordinates, bearings = parse_android_log_speed_data(args.input_path)

    if not timestamps:
        print("No timestamp data found in input.")
        sys.exit(1)

    # Apply date filtering if specified
    if args.date:
        print(f"Filtering data for date: {args.date}")
        timestamps, speeds_kmh, coordinates, bearings = filter_data_by_date(
            timestamps, speeds_kmh, coordinates, bearings, args.date
        )

        if not timestamps:
            print(f"No data found for date {args.date}")
            sys.exit(1)

    # Trim low-speed points at start and end (unless disabled)
    if not args.no_trim and speeds_kmh:
        print(f"Trimming low-speed points (< {args.min_speed} km/h) from start and end...")
        timestamps, speeds_kmh, coordinates, bearings = trim_low_speed_points(
            timestamps, speeds_kmh, coordinates, bearings, args.min_speed
        )

        if not timestamps:
            print("No data remaining after trimming low-speed points.")
            sys.exit(1)

    print(f"Found {len(timestamps)} speed data points")
    if timestamps:
        print(f"Time range: {timestamps[0]} to {timestamps[-1]}")

        if speeds_kmh:
            print(f"Speed range: {min(speeds_kmh):.1f} - {max(speeds_kmh):.1f} km/h (avg: {np.mean(speeds_kmh):.1f} km/h)")

    # Create visualization
    if args.detailed:
        create_detailed_speed_analysis(timestamps, speeds_kmh, bearings, coordinates, args.output, args.bearing)
    else:
        plot_speed_data(timestamps, speeds_kmh, bearings, coordinates, args.title, args.output, args.bearing)