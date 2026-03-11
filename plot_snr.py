#!/usr/bin/env python3
"""
This script reads UBX files from u-blox GNSS receivers and creates
graphs showing Signal-to-Noise Ratio (SNR) for satellites over time.
Each satellite is plotted with a different color.
Supports both UBX binary messages and NMEA text messages as fallback.
"""

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import argparse
import sys
import os
import numpy as np
from collections import defaultdict
import re

try:
    from pyubx2 import UBXReader, POLL
except ImportError:
    print("Error: pyubx2 library not found. Please install it with:")
    print("pip install pyubx2")
    sys.exit(1)

def get_gnss_name(gnss_id):
    """Get GNSS constellation name from ID."""
    gnss_names = {
        0: 'GPS',
        1: 'SBAS',
        2: 'Galileo',
        3: 'BeiDou',
        4: 'IMES',
        5: 'QZSS',
        6: 'GLONASS'
    }
    return gnss_names.get(gnss_id, f'GNSS{gnss_id}')

def get_satellite_id(gnss_id, sv_id):
    """Get unique satellite identifier."""
    gnss_name = get_gnss_name(gnss_id)
    return f"{gnss_name}-{sv_id:02d}"

def parse_nmea_satellite_data(filename):
    """
    Parse NMEA messages from UBX file to extract satellite SNR data.
    Looks for GSV (Satellites in View) messages.

    Args:
        filename (str): Path to the UBX file

    Returns:
        tuple: (timestamps, satellite_data)
    """
    satellite_data = defaultdict(list)
    timestamps = []
    current_time = None

    print("Falling back to NMEA message parsing...")

    try:
        with open(filename, 'rb') as file:
            content = file.read()

        # Look for NMEA sentences in the binary data
        # NMEA sentences start with $ and end with \r\n
        nmea_pattern = re.compile(rb'\$[A-Z0-9,.*\r\n]+', re.MULTILINE)
        nmea_sentences = nmea_pattern.findall(content)

        print(f"Found {len(nmea_sentences)} potential NMEA sentences")

        for sentence_bytes in nmea_sentences:
            try:
                sentence = sentence_bytes.decode('ascii', errors='ignore').strip()
                if not sentence:
                    continue

                # Parse RMC messages for time reference
                if sentence.startswith('$GPRMC') or sentence.startswith('$GNRMC'):
                    parts = sentence.split(',')
                    if len(parts) >= 10:
                        time_str = parts[1]  # HHMMSS.SS
                        date_str = parts[9]  # DDMMYY

                        if time_str and date_str and len(time_str) >= 6 and len(date_str) == 6:
                            try:
                                # Parse time
                                hours = int(time_str[:2])
                                minutes = int(time_str[2:4])
                                seconds = int(float(time_str[4:]))

                                # Parse date
                                day = int(date_str[:2])
                                month = int(date_str[2:4])
                                year = 2000 + int(date_str[4:6])

                                current_time = datetime(year, month, day, hours, minutes, seconds)
                            except (ValueError, IndexError):
                                continue

                # Parse GSV messages for satellite data
                elif sentence.startswith('$GPGSV') or sentence.startswith('$GNGSV') or sentence.startswith('$GLGSV') or sentence.startswith('$GAGSV') or sentence.startswith('$GBGSV'):
                    if current_time is None:
                        continue

                    parts = sentence.split(',')
                    if len(parts) < 4:
                        continue

                    # Determine constellation from talker ID
                    talker = sentence[:6]
                    if talker.startswith('$GPGSV'):
                        gnss_id = 0  # GPS
                    elif talker.startswith('$GLGSV'):
                        gnss_id = 6  # GLONASS
                    elif talker.startswith('$GAGSV'):
                        gnss_id = 2  # Galileo
                    elif talker.startswith('$GBGSV'):
                        gnss_id = 3  # BeiDou
                    elif talker.startswith('$GNGSV'):
                        gnss_id = 0  # Mixed, assume GPS
                    else:
                        gnss_id = 0  # Default to GPS

                    try:
                        total_messages = int(parts[1])
                        message_number = int(parts[2])
                        total_satellites = int(parts[3])

                        # Parse satellite information (4 satellites max per message)
                        sat_start_idx = 4
                        for i in range(4):  # Up to 4 satellites per GSV message
                            base_idx = sat_start_idx + (i * 4)
                            if base_idx + 3 >= len(parts):
                                break

                            sat_id_str = parts[base_idx]
                            elevation_str = parts[base_idx + 1]
                            azimuth_str = parts[base_idx + 2]
                            snr_str = parts[base_idx + 3]

                            # Remove checksum from last field if present
                            if '*' in snr_str:
                                snr_str = snr_str.split('*')[0]

                            if sat_id_str and snr_str and snr_str != '':
                                try:
                                    sat_id = int(sat_id_str)
                                    snr = int(snr_str)

                                    if snr > 0:  # Valid SNR
                                        sat_identifier = get_satellite_id(gnss_id, sat_id)
                                        satellite_data[sat_identifier].append((current_time, snr))

                                        if current_time not in timestamps:
                                            timestamps.append(current_time)

                                except ValueError:
                                    continue

                    except (ValueError, IndexError):
                        continue

            except UnicodeDecodeError:
                continue

    except Exception as e:
        print(f"Error parsing NMEA data: {e}")
        return [], {}

    print(f"NMEA parsing found {len(satellite_data)} satellites with SNR data")
    return sorted(set(timestamps)), dict(satellite_data)

def parse_ubx_file(filename):
    """
    Parse UBX file and extract satellite signal level data using pyubx2.
    Supports both NAV-SAT and NAV-SVINFO messages.
    Falls back to NMEA parsing if no UBX satellite data is found.

    Args:
        filename (str): Path to the UBX file

    Returns:
        tuple: (timestamps, satellite_data)
        satellite_data is a dict with satellite IDs as keys and lists of (timestamp, signal_level) tuples as values
    """
    satellite_data = defaultdict(list)
    timestamps = []
    current_time_ref = {}  # iTOW -> datetime mapping

    try:
        print(f"Parsing UBX file: {filename}")

        with open(filename, 'rb') as stream:
            ubr = UBXReader(stream)

            message_count = 0
            nav_sat_count = 0
            nav_svinfo_count = 0
            nav_pvt_count = 0
            parse_errors = 0

            for (raw_data, parsed_data) in ubr:
                if parsed_data is None:
                    parse_errors += 1
                    continue

                message_count += 1

                # Process NAV-PVT messages for time reference
                if hasattr(parsed_data, 'identity') and parsed_data.identity == 'NAV-PVT':
                    nav_pvt_count += 1

                    # Check if date/time is valid
                    if hasattr(parsed_data, 'validDate') and hasattr(parsed_data, 'validTime'):
                        if parsed_data.validDate and parsed_data.validTime:
                            try:
                                timestamp = datetime(
                                    parsed_data.year,
                                    parsed_data.month,
                                    parsed_data.day,
                                    parsed_data.hour,
                                    parsed_data.min,
                                    parsed_data.second
                                )
                                current_time_ref[parsed_data.iTOW] = timestamp
                            except (ValueError, AttributeError):
                                continue

                # Process NAV-SAT messages for satellite data
                elif hasattr(parsed_data, 'identity') and parsed_data.identity == 'NAV-SAT':
                    nav_sat_count += 1

                    if not hasattr(parsed_data, 'iTOW') or not hasattr(parsed_data, 'numSvs'):
                        continue

                    iTOW = parsed_data.iTOW
                    num_sats = parsed_data.numSvs

                    # Find closest time reference
                    timestamp = None
                    if iTOW in current_time_ref:
                        timestamp = current_time_ref[iTOW]
                    else:
                        # Find closest iTOW
                        closest_iTOW = None
                        min_diff = float('inf')
                        for ref_iTOW in current_time_ref:
                            diff = abs(iTOW - ref_iTOW)
                            if diff < min_diff and diff < 10000:  # Within 10 seconds
                                min_diff = diff
                                closest_iTOW = ref_iTOW

                        if closest_iTOW is not None:
                            # Interpolate timestamp
                            base_time = current_time_ref[closest_iTOW]
                            time_diff = (iTOW - closest_iTOW) / 1000.0  # Convert ms to seconds
                            timestamp = base_time + timedelta(seconds=time_diff)

                    if timestamp:
                        # Extract satellite data from NAV-SAT
                        for i in range(1, num_sats + 1):
                            gnss_id_attr = f'gnssId_{i:02d}'
                            sv_id_attr = f'svId_{i:02d}'
                            cno_attr = f'cno_{i:02d}'
                            quality_attr = f'qualityInd_{i:02d}'  # Quality indicator

                            if (hasattr(parsed_data, gnss_id_attr) and
                                hasattr(parsed_data, sv_id_attr) and
                                hasattr(parsed_data, cno_attr)):

                                gnss_id = getattr(parsed_data, gnss_id_attr)
                                sv_id = getattr(parsed_data, sv_id_attr)
                                cno = getattr(parsed_data, cno_attr)  # C/N0 in dB-Hz (signal level)

                                # Try to get quality indicator for better signal assessment
                                if hasattr(parsed_data, quality_attr):
                                    quality = getattr(parsed_data, quality_attr)
                                    # Quality indicator: 0=no signal, 1-4=increasing quality
                                    if quality == 0:
                                        continue  # Skip satellites with no signal

                                # Only include satellites with valid signal level
                                if cno > 0:
                                    sat_id = get_satellite_id(gnss_id, sv_id)
                                    satellite_data[sat_id].append((timestamp, cno))

                                    if timestamp not in timestamps:
                                        timestamps.append(timestamp)

                # Process NAV-SVINFO messages for satellite data (older format)
                elif hasattr(parsed_data, 'identity') and parsed_data.identity == 'NAV-SVINFO':
                    nav_svinfo_count += 1

                    if not hasattr(parsed_data, 'iTOW') or not hasattr(parsed_data, 'numCh'):
                        continue

                    iTOW = parsed_data.iTOW
                    num_channels = parsed_data.numCh

                    # Find closest time reference
                    timestamp = None
                    if iTOW in current_time_ref:
                        timestamp = current_time_ref[iTOW]
                    else:
                        # Find closest iTOW
                        closest_iTOW = None
                        min_diff = float('inf')
                        for ref_iTOW in current_time_ref:
                            diff = abs(iTOW - ref_iTOW)
                            if diff < min_diff and diff < 10000:  # Within 10 seconds
                                min_diff = diff
                                closest_iTOW = ref_iTOW

                        if closest_iTOW is not None:
                            # Interpolate timestamp
                            base_time = current_time_ref[closest_iTOW]
                            time_diff = (iTOW - closest_iTOW) / 1000.0  # Convert ms to seconds
                            timestamp = base_time + timedelta(seconds=time_diff)

                    if timestamp:
                        # Extract satellite data from NAV-SVINFO
                        for i in range(1, num_channels + 1):
                            chn_attr = f'chn_{i:02d}'  # Channel number
                            svid_attr = f'svid_{i:02d}'  # Satellite ID
                            flags_attr = f'flags_{i:02d}'  # Flags
                            quality_attr = f'quality_{i:02d}'  # Quality
                            cno_attr = f'cno_{i:02d}'  # Signal strength

                            if (hasattr(parsed_data, svid_attr) and
                                hasattr(parsed_data, cno_attr) and
                                hasattr(parsed_data, flags_attr)):

                                sv_id = getattr(parsed_data, svid_attr)
                                cno = getattr(parsed_data, cno_attr)  # Signal strength in dB-Hz
                                flags = getattr(parsed_data, flags_attr)

                                # Get quality if available
                                quality = 1  # Default quality
                                if hasattr(parsed_data, quality_attr):
                                    quality = getattr(parsed_data, quality_attr)

                                # Extract GNSS constellation from satellite ID and flags
                                # NAV-SVINFO uses different satellite ID ranges for different constellations
                                if sv_id >= 1 and sv_id <= 32:
                                    gnss_id = 0  # GPS
                                elif sv_id >= 65 and sv_id <= 96:
                                    gnss_id = 6  # GLONASS
                                    sv_id = sv_id - 64  # Normalize GLONASS ID
                                elif sv_id >= 120 and sv_id <= 158:
                                    gnss_id = 1  # SBAS
                                elif sv_id >= 193 and sv_id <= 197:
                                    gnss_id = 5  # QZSS
                                elif sv_id >= 201 and sv_id <= 235:
                                    gnss_id = 3  # BeiDou
                                elif sv_id >= 301 and sv_id <= 336:
                                    gnss_id = 2  # Galileo
                                    sv_id = sv_id - 300  # Normalize Galileo ID
                                else:
                                    # Unknown satellite, assign to GPS for compatibility
                                    gnss_id = 0

                                # Check if satellite is being tracked (bit 0 of flags)
                                is_tracking = (flags & 0x01) != 0

                                # Only include satellites that are being tracked with valid signal level
                                if is_tracking and cno > 0 and quality > 0:
                                    sat_id = get_satellite_id(gnss_id, sv_id)
                                    satellite_data[sat_id].append((timestamp, cno))

                                    if timestamp not in timestamps:
                                        timestamps.append(timestamp)

                if message_count % 1000 == 0:
                    print(f"Processed {message_count} messages...")

        print(f"UBX parsing complete:")
        print(f"  Total messages: {message_count}")
        print(f"  Parse errors: {parse_errors}")
        print(f"  NAV-PVT messages: {nav_pvt_count}")
        print(f"  NAV-SAT messages: {nav_sat_count}")
        print(f"  NAV-SVINFO messages: {nav_svinfo_count}")
        print(f"  Unique timestamps: {len(set(timestamps))}")
        print(f"  Satellites found: {len(satellite_data)}")

        # Print which message format was primarily used
        if nav_sat_count > nav_svinfo_count:
            print(f"  Primary format: NAV-SAT (modern)")
        elif nav_svinfo_count > 0:
            print(f"  Primary format: NAV-SVINFO (legacy)")
        else:
            print(f"  Warning: No UBX satellite data messages found")

        # If no satellite data found in UBX messages, try NMEA fallback
        if not satellite_data:
            print("No satellite data found in UBX messages, trying NMEA fallback...")
            return parse_nmea_satellite_data(filename)

        return sorted(set(timestamps)), dict(satellite_data)

    except FileNotFoundError:
        print(f"Error: UBX file '{filename}' not found.")
        return [], {}
    except Exception as e:
        print(f"Error reading UBX file: {e}")
        import traceback
        traceback.print_exc()
        return [], {}

def plot_signal_data(timestamps, satellite_data, title="Satellite Signal Levels Over Time", filepath=None, constellation_filter=None):
    """
    Create a plot showing satellite signal levels over time.

    Args:
        timestamps (list): List of datetime objects
        satellite_data (dict): Dictionary with satellite IDs as keys and lists of (timestamp, signal_level) lists as values
        title (str): Plot title
        filepath (str, optional): Path to save the plot
        constellation_filter (list, optional): List of constellation names to filter (e.g., ['GPS', 'Galileo'])
    """
    if not satellite_data:
        print("No satellite signal data to plot")
        return

    # Filter by constellation if specified
    if constellation_filter:
        filtered_data = {}
        for sat_id, data_points in satellite_data.items():
            constellation = sat_id.split('-')[0]
            if constellation in constellation_filter:
                filtered_data[sat_id] = data_points
        satellite_data = filtered_data

        if not satellite_data:
            print(f"No satellites found for constellations: {constellation_filter}")
            return

    fig, ax = plt.subplots(figsize=(14, 8))

    # Group satellites by constellation for better color organization
    constellation_sats = defaultdict(list)
    for sat_id in sorted(satellite_data.keys()):
        constellation = sat_id.split('-')[0]
        constellation_sats[constellation].append(sat_id)

    # Generate colors for each constellation
    constellation_colors = {
        'GPS': plt.cm.Blues,
        'Galileo': plt.cm.Greens,
        'GLONASS': plt.cm.Reds,
        'BeiDou': plt.cm.Oranges,
        'QZSS': plt.cm.Purples,
        'SBAS': plt.cm.Greys
    }

    # Plot each satellite
    for constellation, sat_list in constellation_sats.items():
        if constellation in constellation_colors:
            colormap = constellation_colors[constellation]
            colors = colormap(np.linspace(0.3, 0.9, len(sat_list)))
        else:
            colors = plt.cm.viridis(np.linspace(0, 1, len(sat_list)))

        for i, sat_id in enumerate(sat_list):
            data_points = satellite_data[sat_id]
            if not data_points:
                continue

            times, signal_levels = zip(*data_points)
            color = colors[i] if len(sat_list) > 1 else colors

            ax.plot(times, signal_levels, 'o-', color=color, label=sat_id,
                    linewidth=1, markersize=2, alpha=0.7)

    # Customize the plot
    ax.set_xlabel('Time', fontsize=12)
    ax.set_ylabel('Signal Level (dB-Hz)', fontsize=12)
    ax.set_title(title, fontsize=14, pad=20)
    ax.grid(True, alpha=0.3)

    # Add signal quality reference lines
    ax.axhline(y=35, color='red', linestyle='--', alpha=0.5, label='Minimum for navigation')
    ax.axhline(y=40, color='orange', linestyle='--', alpha=0.5, label='Good signal')
    ax.axhline(y=45, color='green', linestyle='--', alpha=0.5, label='Excellent signal')

    # Format x-axis dates
    if timestamps:
        duration = timestamps[-1] - timestamps[0]
        if duration.total_seconds() > 3600:  # More than 1 hour
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            ax.xaxis.set_major_locator(mdates.MinuteLocator(interval=10))
        elif duration.total_seconds() > 1800:  # More than 30 minutes
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
            ax.xaxis.set_major_locator(mdates.MinuteLocator(interval=5))
        else:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
            ax.xaxis.set_major_locator(mdates.MinuteLocator(interval=1))

    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')

    # Set y-axis limits with focus on typical signal ranges
    all_signals = [signal for data in satellite_data.values() for _, signal in data]
    if all_signals:
        min_signal = max(0, min(all_signals) - 5)  # Don't go below 0
        max_signal = max(all_signals) + 5
        # Ensure we show at least the 25-55 dB-Hz range (typical for GNSS)
        min_signal = min(min_signal, 25)
        max_signal = max(max_signal, 55)
        ax.set_ylim(min_signal, max_signal)

    # Add legend (organized by constellation)
    handles, labels = ax.get_legend_handles_labels()

    # Separate reference lines from satellite data in legend
    reference_handles = handles[-3:]  # Last 3 are the reference lines
    reference_labels = labels[-3:]
    sat_handles = handles[:-3]
    sat_labels = labels[:-3]

    if len(sat_labels) > 25:  # Too many satellites for readable legend
        # Create constellation legend instead
        constellation_handles = []
        constellation_labels = []
        for constellation in constellation_sats.keys():
            if constellation in constellation_colors:
                color = constellation_colors[constellation](0.7)
            else:
                color = 'gray'
            handle = plt.Line2D([0], [0], color=color, linewidth=3, alpha=0.7)
            constellation_handles.append(handle)
            constellation_labels.append(f"{constellation} ({len(constellation_sats[constellation])} sats)")

        # Combine constellation and reference legends
        all_handles = constellation_handles + reference_handles
        all_labels = constellation_labels + reference_labels
        ax.legend(all_handles, all_labels,
                 bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=9)
    else:
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', ncol=1, fontsize=8)

    # Add statistics with signal quality assessment
    stats_text = f"Satellites: {len(satellite_data)}\n"
    if constellation_filter:
        stats_text += f"Constellations: {', '.join(args.constellation)}\n"
    else:
        stats_text += f"Constellations: {len(constellation_sats)}\n"

    if timestamps:
        duration = timestamps[-1] - timestamps[0]
        stats_text += f"Duration: {duration}\n"

    if all_signals:
        min_sig = min(all_signals)
        max_sig = max(all_signals)
        avg_sig = np.mean(all_signals)

        stats_text += f"Signal Range: {min_sig:.1f} - {max_sig:.1f} dB-Hz\n"
        stats_text += f"Avg Signal: {avg_sig:.1f} dB-Hz\n"

        # Signal quality assessment
        excellent_count = sum(1 for s in all_signals if s >= 45)
        good_count = sum(1 for s in all_signals if 40 <= s < 45)
        fair_count = sum(1 for s in all_signals if 35 <= s < 40)
        poor_count = sum(1 for s in all_signals if s < 35)
        total_count = len(all_signals)

        stats_text += f"\nSignal Quality:\n"
        stats_text += f"Excellent (≥45): {excellent_count/total_count*100:.1f}%\n"
        stats_text += f"Good (40-44): {good_count/total_count*100:.1f}%\n"
        stats_text += f"Fair (35-39): {fair_count/total_count*100:.1f}%\n"
        stats_text += f"Poor (<35): {poor_count/total_count*100:.1f}%"

    ax.text(0.02, 0.02, stats_text, transform=ax.transAxes,
           fontsize=8, verticalalignment='bottom',
           bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8))

    plt.tight_layout()

    if filepath:
        plt.savefig(filepath, bbox_inches='tight', dpi=300,
                   facecolor='white', edgecolor='none')
        print(f"Signal level plot saved to {filepath}")
    else:
        plt.show()

def main():
    """Main function to handle command line arguments and execute visualization."""
    parser = argparse.ArgumentParser(
        description='Parse UBX files and visualize satellite signal levels over time using pyubx2. Falls back to NMEA parsing if no UBX satellite data found.',
        epilog='''
Examples:
  %(prog)s gps_data.ubx
  %(prog)s gps_data.ubx -o signal_plot.png
  %(prog)s gps_data.ubx --title "Satellite Signal Analysis"
  %(prog)s gps_data.ubx --constellation GPS Galileo
  %(prog)s gps_data.ubx --constellation GPS -o gps_only_signals.png
        ''',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('ubx_file',
                       help='Path to the UBX file containing satellite data')

    parser.add_argument('-o', '--output',
                       help='Output file path for saving the plot (PNG format)')

    parser.add_argument('--title',
                       default='Satellite Signal Levels Over Time',
                       help='Title for the plot (default: Satellite Signal Levels Over Time)')

    parser.add_argument('--constellation',
                       nargs='*',
                       choices=['GPS', 'Galileo', 'GLONASS', 'BeiDou', 'QZSS', 'SBAS'],
                       help='Filter by constellation(s) (e.g., --constellation GPS Galileo)')

    parser.add_argument('--version',
                       action='version',
                       version='UBX Signal Level Analyzer 2.1.0 (pyubx2 + NMEA fallback)')

    args = parser.parse_args()

    # Check if input file exists
    if not os.path.exists(args.ubx_file):
        print(f"Error: UBX file '{args.ubx_file}' not found.")
        sys.exit(1)

    print(f"Analyzing satellite signal levels from {args.ubx_file}")
    if args.constellation:
        print(f"Filtering constellations: {', '.join(args.constellation)}")

    # Parse the UBX file
    timestamps, satellite_data = parse_ubx_file(args.ubx_file)

    if not satellite_data:
        print("No satellite signal data found in file.")
        sys.exit(1)

    print(f"Found signal data for {len(satellite_data)} satellites")
    if timestamps:
        print(f"Time range: {timestamps[0]} to {timestamps[-1]}")

    # Create visualization
    plot_signal_data(timestamps, satellite_data, args.title, args.output, args.constellation)

if __name__ == "__main__":
    main()