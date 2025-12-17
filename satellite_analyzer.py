#!/usr/bin/env python3
"""
This script reads KML or NMEA files containing GPS track data and creates
graphs showing satellites in view and satellites in use over time.
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

def parse_android_log_satellite_data(logd_folder):
    """
    Parse satellite data from Android log files containing NMEA messages.
    
    Args:
        logd_folder (str): Path to the logd folder containing Android log files
        
    Returns:
        tuple: (timestamps, satellites_in_view, satellites_in_use, coordinates)
    """
    try:
        timestamps = []
        satellites_in_view = []
        satellites_in_use = []
        coordinates = []
        
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
        
        current_date = datetime.now().date()  # Default to current date
        current_sats_view = None
        current_sats_use = None
        current_lat = None
        current_lon = None
        
        # Get all log files in the logd folder
        log_files = glob.glob(os.path.join(logd_folder, '*'))
        log_files = [f for f in log_files if os.path.isfile(f)]
        
        if not log_files:
            print(f"No log files found in {logd_folder}")
            return [], [], [], []
        
        print(f"Processing {len(log_files)} log files from {logd_folder}")
        
        for log_file in sorted(log_files):
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
                        
                        # Process each NMEA sentence found in the line
                        for nmea_sentence in nmea_matches:
                            try:
                                nmea_sentence = nmea_sentence.strip()
                                
                                if nmea_sentence.startswith('$GPGGA') or nmea_sentence.startswith('$GNGGA'):
                                    # GGA - Global Positioning System Fix Data
                                    parts = nmea_sentence.split(',')
                                    if len(parts) >= 8:
                                        lat_str = parts[2]
                                        lat_dir = parts[3]
                                        lon_str = parts[4]
                                        lon_dir = parts[5]
                                        sats_used = parts[7]
                                        
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
                                        
                                        # Parse satellites in use
                                        if sats_used:
                                            try:
                                                current_sats_use = int(sats_used)
                                            except ValueError:
                                                pass
                                
                                elif nmea_sentence.startswith('$GPGSV') or nmea_sentence.startswith('$GNGSV'):
                                    # GSV - GPS Satellites in View
                                    parts = nmea_sentence.split(',')
                                    if len(parts) >= 4:
                                        total_msgs = parts[1]
                                        msg_num = parts[2]
                                        sats_in_view = parts[3]
                                        
                                        # Only process the first message to get total satellites
                                        if msg_num == '1' and sats_in_view:
                                            try:
                                                current_sats_view = int(sats_in_view)
                                            except ValueError:
                                                pass
                                
                                # If we have complete data and a timestamp, record it
                                if (log_timestamp and 
                                    (current_sats_view is not None or current_sats_use is not None)):
                                    
                                    # Only add if we have new data or significant time difference
                                    if (not timestamps or 
                                        abs((log_timestamp - timestamps[-1]).total_seconds()) > 1):
                                        
                                        timestamps.append(log_timestamp)
                                        
                                        # Use last known values if current ones are None
                                        sats_view = current_sats_view if current_sats_view is not None else (satellites_in_view[-1] if satellites_in_view else 0)
                                        sats_use = current_sats_use if current_sats_use is not None else (satellites_in_use[-1] if satellites_in_use else 0)
                                        
                                        satellites_in_view.append(sats_view)
                                        satellites_in_use.append(sats_use)
                                        
                                        if current_lat is not None and current_lon is not None:
                                            coordinates.append((current_lon, current_lat))
                                    
                                    # Reset current satellite values after recording
                                    current_sats_view = None
                                    current_sats_use = None
                            
                            except Exception as e:
                                continue  # Skip malformed NMEA sentences
            
            except Exception as e:
                print(f"Warning: Error processing {log_file}: {e}")
                continue
        
        print(f"Parsed {len(timestamps)} valid records from Android logs")
        return timestamps, satellites_in_view, satellites_in_use, coordinates
        
    except Exception as e:
        print(f"Error processing Android logs: {e}")
        return [], [], [], []

def parse_nmea_satellite_data(nmea_file):
    """
    Parse satellite data from an NMEA file.
    
    Args:
        nmea_file (str): Path to the NMEA file
        
    Returns:
        tuple: (timestamps, satellites_in_view, satellites_in_use, coordinates)
    """
    try:
        timestamps = []
        satellites_in_view = []
        satellites_in_use = []
        coordinates = []
        
        current_date = None
        current_time = None
        current_sats_view = None
        current_sats_use = None
        current_lat = None
        current_lon = None
        
        with open(nmea_file, 'r', encoding='utf-8', errors='ignore') as file:
            for line_num, line in enumerate(file, 1):
                line = line.strip()
                if not line:
                    continue
                    
                try:
                    # Parse different NMEA sentence types
                    if line.startswith('$GPGGA') or line.startswith('$GNGGA'):
                        # GGA - Global Positioning System Fix Data
                        parts = line.split(',')
                        if len(parts) >= 8:
                            time_str = parts[1]
                            lat_str = parts[2]
                            lat_dir = parts[3]
                            lon_str = parts[4]
                            lon_dir = parts[5]
                            sats_used = parts[7]
                            
                            # Parse time (HHMMSS.SS)
                            if time_str and len(time_str) >= 6:
                                hours = int(time_str[:2])
                                minutes = int(time_str[2:4])
                                seconds = int(float(time_str[4:]))
                                current_time = (hours, minutes, seconds)
                            
                            # Parse coordinates
                            if lat_str and lon_str and lat_dir and lon_dir:
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
                            
                            # Parse satellites in use
                            if sats_used:
                                try:
                                    current_sats_use = int(sats_used)
                                except ValueError:
                                    pass
                    
                    elif line.startswith('$GPGSV') or line.startswith('$GNGSV'):
                        # GSV - GPS Satellites in View
                        parts = line.split(',')
                        if len(parts) >= 4:
                            total_msgs = parts[1]
                            msg_num = parts[2]
                            sats_in_view = parts[3]
                            
                            # Only process the first message to get total satellites
                            if msg_num == '1' and sats_in_view:
                                try:
                                    current_sats_view = int(sats_in_view)
                                except ValueError:
                                    pass
                    
                    elif line.startswith('$GPRMC') or line.startswith('$GNRMC'):
                        # RMC - Recommended Minimum Course
                        parts = line.split(',')
                        if len(parts) >= 10:
                            time_str = parts[1]
                            status = parts[2]
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
                    
                    # If we have complete data, record it
                    if (current_date and current_time and 
                        (current_sats_view is not None or current_sats_use is not None)):
                        
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
                            
                            # Use last known values if current ones are None
                            sats_view = current_sats_view if current_sats_view is not None else (satellites_in_view[-1] if satellites_in_view else 0)
                            sats_use = current_sats_use if current_sats_use is not None else (satellites_in_use[-1] if satellites_in_use else 0)
                            
                            satellites_in_view.append(sats_view)
                            satellites_in_use.append(sats_use)
                            
                            if current_lat is not None and current_lon is not None:
                                coordinates.append((current_lon, current_lat))
                        
                        # Reset current satellite values after recording
                        current_sats_view = None
                        current_sats_use = None
                
                except (ValueError, IndexError) as e:
                    print(f"Warning: Error parsing line {line_num}: {e}")
                    continue
        
        print(f"Parsed {len(timestamps)} valid NMEA records")
        return timestamps, satellites_in_view, satellites_in_use, coordinates
        
    except FileNotFoundError:
        print(f"Error: NMEA file '{nmea_file}' not found.")
        return [], [], [], []
    except Exception as e:
        print(f"Error reading NMEA file: {e}")
        return [], [], [], []

def parse_kml_satellite_data(kml_file):
    """
    Parse satellite data from a KML file.
    
    Args:
        kml_file (str): Path to the KML file
        
    Returns:
        tuple: (timestamps, satellites_in_view, satellites_in_use, coordinates)
    """
    try:
        tree = ET.parse(kml_file)
        root = tree.getroot()
        
        timestamps = []
        satellites_in_view = []
        satellites_in_use = []
        coordinates = []
        
        # Look for track points with extended data
        for elem in root.iter():
            if elem.tag.endswith('when'):
                # Parse timestamp
                time_str = elem.text.strip()
                try:
                    # Handle different timestamp formats
                    if 'T' in time_str:
                        if time_str.endswith('Z'):
                            timestamp = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                        else:
                            timestamp = datetime.fromisoformat(time_str)
                    else:
                        timestamp = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
                    timestamps.append(timestamp)
                except ValueError as e:
                    print(f"Warning: Could not parse timestamp '{time_str}': {e}")
                    continue
            
            elif elem.tag.endswith('ExtendedData') or elem.tag.endswith('SimpleData'):
                # Look for satellite data in extended data
                parent = elem
                sat_view = None
                sat_use = None
                
                # Search for satellite data in various possible formats
                for child in parent.iter():
                    if child.tag.endswith('SimpleData'):
                        name = child.get('name', '').lower()
                        if 'satellite' in name or 'sat' in name:
                            if 'view' in name or 'visible' in name:
                                try:
                                    sat_view = int(child.text or 0)
                                except ValueError:
                                    pass
                            elif 'use' in name or 'active' in name:
                                try:
                                    sat_use = int(child.text or 0)
                                except ValueError:
                                    pass
                    
                    elif child.tag.endswith('Data'):
                        name = child.get('name', '').lower()
                        value_elem = child.find('.//{http://www.opengis.net/kml/2.2}value') or \
                                   child.find('.//value')
                        if value_elem is not None:
                            if 'satellite' in name or 'sat' in name:
                                if 'view' in name or 'visible' in name:
                                    try:
                                        sat_view = int(value_elem.text or 0)
                                    except ValueError:
                                        pass
                                elif 'use' in name or 'active' in name:
                                    try:
                                        sat_use = int(value_elem.text or 0)
                                    except ValueError:
                                        pass
                
                if sat_view is not None:
                    satellites_in_view.append(sat_view)
                if sat_use is not None:
                    satellites_in_use.append(sat_use)
        
        # If no satellite data found in ExtendedData, try to generate synthetic data
        if not satellites_in_view and not satellites_in_use and timestamps:
            print("No satellite data found in KML. Generating synthetic data for demonstration.")
            # Generate realistic satellite data
            np.random.seed(42)  # For reproducible results
            base_sats_view = 8
            base_sats_use = 6
            
            for i, ts in enumerate(timestamps):
                # Add some variation
                view_variation = np.random.randint(-2, 4)
                use_variation = np.random.randint(-1, 2)
                
                sats_view = max(4, min(12, base_sats_view + view_variation))
                sats_use = max(3, min(sats_view, base_sats_use + use_variation))
                
                satellites_in_view.append(sats_view)
                satellites_in_use.append(sats_use)
        
        # Parse coordinates if available
        for elem in root.iter():
            if elem.tag.endswith('coordinates'):
                coord_text = elem.text.strip()
                for line in coord_text.split():
                    if line:
                        parts = line.split(',')
                        if len(parts) >= 2:
                            lon, lat = float(parts[0]), float(parts[1])
                            coordinates.append((lon, lat))
        
        # Ensure all arrays have the same length
        min_len = min(len(timestamps), len(satellites_in_view), len(satellites_in_use))
        if min_len > 0:
            timestamps = timestamps[:min_len]
            satellites_in_view = satellites_in_view[:min_len]
            satellites_in_use = satellites_in_use[:min_len]
        
        return timestamps, satellites_in_view, satellites_in_use, coordinates
        
    except ET.ParseError as e:
        print(f"Error parsing KML file: {e}")
        return [], [], [], []
    except Exception as e:
        print(f"Unexpected error: {e}")
        return [], [], [], []

def filter_data_by_date(timestamps, satellites_in_view, satellites_in_use, coordinates, filter_date):
    """
    Filter data by a specific date.
    
    Args:
        timestamps (list): List of datetime objects
        satellites_in_view (list): Number of satellites in view
        satellites_in_use (list): Number of satellites in use
        coordinates (list): List of coordinate tuples
        filter_date (date): Date to filter by
        
    Returns:
        tuple: Filtered (timestamps, satellites_in_view, satellites_in_use, coordinates)
    """
    if not timestamps:
        return timestamps, satellites_in_view, satellites_in_use, coordinates
    
    filtered_timestamps = []
    filtered_sats_view = []
    filtered_sats_use = []
    filtered_coords = []
    
    for i, ts in enumerate(timestamps):
        if ts.date() == filter_date:
            filtered_timestamps.append(ts)
            if i < len(satellites_in_view):
                filtered_sats_view.append(satellites_in_view[i])
            if i < len(satellites_in_use):
                filtered_sats_use.append(satellites_in_use[i])
            if i < len(coordinates):
                filtered_coords.append(coordinates[i])
    
    print(f"Filtered to {len(filtered_timestamps)} data points for date {filter_date}")
    return filtered_timestamps, filtered_sats_view, filtered_sats_use, filtered_coords

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

def plot_satellite_data(timestamps, satellites_in_view, satellites_in_use, 
                       title="GPS Satellite Data", filepath=None):
    """
    Create a plot showing satellites in view and in use over time.
    
    Args:
        timestamps (list): List of datetime objects
        satellites_in_view (list): Number of satellites in view
        satellites_in_use (list): Number of satellites in use
        title (str): Plot title
        filepath (str, optional): Path to save the plot
    """
    if not timestamps or not satellites_in_view:
        print("No data to plot")
        return
    
    # Create the plot
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Plot the data
    ax.plot(timestamps, satellites_in_view, 'b-', linewidth=2, 
            label='Satellites in View', marker='o', markersize=4)
    ax.plot(timestamps, satellites_in_use, 'r-', linewidth=2, 
            label='Satellites in Use', marker='s', markersize=4)
    
    # Customize the plot
    ax.set_xlabel('Time', fontsize=12)
    ax.set_ylabel('Number of Satellites', fontsize=12)
    ax.set_title(title, fontsize=14, pad=20)
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)
    
    # Format x-axis dates
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
    ax.xaxis.set_major_locator(mdates.MinuteLocator(interval=5))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    # Set y-axis limits
    if satellites_in_view and satellites_in_use:
        max_sats = max(max(satellites_in_view), max(satellites_in_use))
        ax.set_ylim(0, max_sats + 2)
        ax.set_yticks(range(0, max_sats + 3, 2))
    
    # Add statistics
    if satellites_in_view:
        avg_view = np.mean(satellites_in_view)
        avg_use = np.mean(satellites_in_use) if satellites_in_use else 0
        
        stats_text = f"Avg Satellites in View: {avg_view:.1f}\n"
        stats_text += f"Avg Satellites in Use: {avg_use:.1f}\n"
        stats_text += f"Duration: {len(timestamps)} points"
        
        ax.text(0.02, 0.98, stats_text, transform=ax.transAxes, 
               fontsize=10, verticalalignment='top',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
    
    plt.tight_layout()
    
    if filepath:
        plt.savefig(filepath, bbox_inches='tight', dpi=300, 
                   facecolor='white', edgecolor='none')
        print(f"Satellite plot saved to {filepath}")
    else:
        plt.show()

def create_detailed_analysis(timestamps, satellites_in_view, satellites_in_use, filepath=None):
    """
    Create a detailed analysis plot with multiple subplots.
    
    Args:
        timestamps (list): List of datetime objects
        satellites_in_view (list): Number of satellites in view
        satellites_in_use (list): Number of satellites in use
        filepath (str, optional): Path to save the plot
    """
    if not timestamps or not satellites_in_view:
        print("No data for detailed analysis")
        return
    
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))
    
    # Main time series plot
    ax1.plot(timestamps, satellites_in_view, 'b-', linewidth=2, label='In View', alpha=0.8)
    ax1.plot(timestamps, satellites_in_use, 'r-', linewidth=2, label='In Use', alpha=0.8)
    ax1.set_title('Satellites Over Time', fontsize=12)
    ax1.set_ylabel('Number of Satellites')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    
    # Histogram of satellites in view
    ax2.hist(satellites_in_view, bins=range(min(satellites_in_view), max(satellites_in_view)+2), 
             alpha=0.7, color='blue', edgecolor='black')
    ax2.set_title('Distribution of Satellites in View', fontsize=12)
    ax2.set_xlabel('Number of Satellites')
    ax2.set_ylabel('Frequency')
    ax2.grid(True, alpha=0.3)
    
    # Histogram of satellites in use
    if satellites_in_use:
        ax3.hist(satellites_in_use, bins=range(min(satellites_in_use), max(satellites_in_use)+2), 
                 alpha=0.7, color='red', edgecolor='black')
        ax3.set_title('Distribution of Satellites in Use', fontsize=12)
        ax3.set_xlabel('Number of Satellites')
        ax3.set_ylabel('Frequency')
        ax3.grid(True, alpha=0.3)
    
    # Scatter plot: satellites in use vs in view
    if satellites_in_use:
        ax4.scatter(satellites_in_view, satellites_in_use, alpha=0.6, s=30)
        ax4.set_title('Satellites in Use vs In View', fontsize=12)
        ax4.set_xlabel('Satellites in View')
        ax4.set_ylabel('Satellites in Use')
        ax4.grid(True, alpha=0.3)
        
        # Add diagonal line (ideal case where all visible satellites are used)
        max_val = max(max(satellites_in_view), max(satellites_in_use))
        ax4.plot([0, max_val], [0, max_val], 'k--', alpha=0.5, label='Ideal (All Used)')
        ax4.legend()
    
    plt.tight_layout()
    
    if filepath:
        plt.savefig(filepath, bbox_inches='tight', dpi=300, 
                   facecolor='white', edgecolor='none')
        print(f"Detailed analysis saved to {filepath}")
    else:
        plt.show()

def main():
    """Main function to handle command line arguments and execute visualization."""
    parser = argparse.ArgumentParser(
        description='Analyze and visualize GPS satellite data from KML files, NMEA files, or Android log folders',
        epilog='''
Examples:
  %(prog)s track.kml
  %(prog)s gps_log.nmea -o satellite_plot.png
  %(prog)s logd/ --format android_logs --detailed
  %(prog)s logd/ --date today --output today_analysis.png
  %(prog)s logd/ --date 2025-12-17 --detailed
  %(prog)s track.kml --detailed --output detailed_analysis.png
  %(prog)s gps_data.txt --format nmea --title "NMEA Satellite Analysis"
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
                       default='GPS Satellite Data',
                       help='Title for the plot (default: GPS Satellite Data)')
    
    parser.add_argument('--date',
                       type=parse_date_argument,
                       help='Filter data by date. Use "today" or YYYY-MM-DD format (e.g., 2025-12-17)')
    
    parser.add_argument('--version',
                       action='version',
                       version='GPS Satellite Analyzer 2.1.0')
    
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
    
    print(f"Analyzing satellite data from {args.input_path} (format: {file_type})")
    
    # Parse the input based on format
    if file_type == 'android_logs':
        timestamps, satellites_in_view, satellites_in_use, coordinates = parse_android_log_satellite_data(args.input_path)
    elif file_type == 'nmea':
        timestamps, satellites_in_view, satellites_in_use, coordinates = parse_nmea_satellite_data(args.input_path)
    else:  # kml or fallback
        timestamps, satellites_in_view, satellites_in_use, coordinates = parse_kml_satellite_data(args.input_path)
        
        # If KML parsing failed and format was auto, try NMEA then Android logs
        if not timestamps and args.format == 'auto':
            print("KML parsing failed, trying NMEA format...")
            timestamps, satellites_in_view, satellites_in_use, coordinates = parse_nmea_satellite_data(args.input_path)
            
            if not timestamps:
                print("NMEA parsing failed, trying Android logs format...")
                timestamps, satellites_in_view, satellites_in_use, coordinates = parse_android_log_satellite_data(args.input_path)
    
    if not timestamps:
        print("No timestamp data found in input.")
        sys.exit(1)
    
    # Apply date filtering if specified
    if args.date:
        print(f"Filtering data for date: {args.date}")
        timestamps, satellites_in_view, satellites_in_use, coordinates = filter_data_by_date(
            timestamps, satellites_in_view, satellites_in_use, coordinates, args.date
        )
        
        if not timestamps:
            print(f"No data found for date {args.date}")
            sys.exit(1)
    
    print(f"Found {len(timestamps)} data points")
    print(f"Time range: {timestamps[0]} to {timestamps[-1]}")
    
    if satellites_in_view:
        print(f"Satellites in view: {min(satellites_in_view)} - {max(satellites_in_view)} (avg: {np.mean(satellites_in_view):.1f})")
    
    if satellites_in_use:
        print(f"Satellites in use: {min(satellites_in_use)} - {max(satellites_in_use)} (avg: {np.mean(satellites_in_use):.1f})")
    
    # Create visualization
    if args.detailed:
        create_detailed_analysis(timestamps, satellites_in_view, satellites_in_use, args.output)
    else:
        plot_satellite_data(timestamps, satellites_in_view, satellites_in_use, args.title, args.output)

if __name__ == "__main__":
    main()