#!/usr/bin/env python3
"""
This script reads UBX files from u-blox GNSS receivers and creates
graphs showing Signal-to-Noise Ratio (SNR) for satellites over time.
Each satellite is plotted with a different color.
"""

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import argparse
import sys
import os
import numpy as np
from collections import defaultdict

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

def parse_ubx_file(filename):
    """
    Parse UBX file and extract satellite SNR data using pyubx2.

    Args:
        filename (str): Path to the UBX file

    Returns:
        tuple: (timestamps, satellite_data)
        satellite_data is a dict with satellite IDs as keys and lists of (timestamp, snr) tuples as values
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
                        # Extract satellite data
                        for i in range(1, num_sats + 1):
                            gnss_id_attr = f'gnssId_{i:02d}'
                            sv_id_attr = f'svId_{i:02d}'
                            cno_attr = f'cno_{i:02d}'

                            if (hasattr(parsed_data, gnss_id_attr) and
                                hasattr(parsed_data, sv_id_attr) and
                                hasattr(parsed_data, cno_attr)):

                                gnss_id = getattr(parsed_data, gnss_id_attr)
                                sv_id = getattr(parsed_data, sv_id_attr)
                                cno = getattr(parsed_data, cno_attr)  # C/N0 in dB-Hz

                                # Only include satellites with valid SNR
                                if cno > 0:
                                    sat_id = get_satellite_id(gnss_id, sv_id)
                                    satellite_data[sat_id].append((timestamp, cno))

                                    if timestamp not in timestamps:
                                        timestamps.append(timestamp)

                if message_count % 1000 == 0:
                    print(f"Processed {message_count} messages...")

        print(f"Parsing complete:")
        print(f"  Total messages: {message_count}")
        print(f"  Parse errors: {parse_errors}")
        print(f"  NAV-PVT messages: {nav_pvt_count}")
        print(f"  NAV-SAT messages: {nav_sat_count}")
        print(f"  Unique timestamps: {len(set(timestamps))}")
        print(f"  Satellites found: {len(satellite_data)}")

        return sorted(set(timestamps)), dict(satellite_data)

    except FileNotFoundError:
        print(f"Error: UBX file '{filename}' not found.")
        return [], {}
    except Exception as e:
        print(f"Error reading UBX file: {e}")
        import traceback
        traceback.print_exc()
        return [], {}

def plot_snr_data(timestamps, satellite_data, title="Satellite SNR Over Time", filepath=None, constellation_filter=None):
    """
    Create a plot showing satellite SNR over time.

    Args:
        timestamps (list): List of datetime objects
        satellite_data (dict): Dictionary with satellite IDs as keys and (timestamp, snr) lists as values
        title (str): Plot title
        filepath (str, optional): Path to save the plot
        constellation_filter (list, optional): List of constellation names to filter (e.g., ['GPS', 'Galileo'])
    """
    if not satellite_data:
        print("No satellite SNR data to plot")
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

            times, snrs = zip(*data_points)
            color = colors[i] if len(sat_list) > 1 else colors

            ax.plot(times, snrs, 'o-', color=color, label=sat_id,
                    linewidth=1, markersize=2, alpha=0.7)

    # Customize the plot
    ax.set_xlabel('Time', fontsize=12)
    ax.set_ylabel('Signal Strength (dB-Hz)', fontsize=12)
    ax.set_title(title, fontsize=14, pad=20)
    ax.grid(True, alpha=0.3)

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

    # Set y-axis limits
    all_snrs = [snr for data in satellite_data.values() for _, snr in data]
    if all_snrs:
        min_snr = min(all_snrs)
        max_snr = max(all_snrs)
        ax.set_ylim(max(0, min_snr - 5), max_snr + 5)

    # Add legend (organized by constellation)
    handles, labels = ax.get_legend_handles_labels()
    if len(labels) > 30:  # Too many satellites for readable legend
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

        ax.legend(constellation_handles, constellation_labels,
                 bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=9)
    else:
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', ncol=1, fontsize=8)

    # Add statistics
    stats_text = f"Satellites: {len(satellite_data)}\n"
    if constellation_filter:
        stats_text += f"Constellations: {', '.join(constellation_filter)}\n"
    else:
        stats_text += f"Constellations: {len(constellation_sats)}\n"

    if timestamps:
        duration = timestamps[-1] - timestamps[0]
        stats_text += f"Duration: {duration}\n"
    if all_snrs:
        stats_text += f"SNR Range: {min(all_snrs):.1f} - {max(all_snrs):.1f} dB-Hz\n"
        stats_text += f"Avg SNR: {np.mean(all_snrs):.1f} dB-Hz"

    ax.text(0.02, 0.98, stats_text, transform=ax.transAxes,
           fontsize=9, verticalalignment='top',
           bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8))

    plt.tight_layout()

    if filepath:
        plt.savefig(filepath, bbox_inches='tight', dpi=300,
                   facecolor='white', edgecolor='none')
        print(f"SNR plot saved to {filepath}")
    else:
        plt.show()

def main():
    """Main function to handle command line arguments and execute visualization."""
    parser = argparse.ArgumentParser(
        description='Parse UBX files and visualize satellite SNR data over time using pyubx2',
        epilog='''
Examples:
  %(prog)s gps_data.ubx
  %(prog)s gps_data.ubx -o snr_plot.png
  %(prog)s gps_data.ubx --title "Satellite SNR Analysis"
  %(prog)s gps_data.ubx --constellation GPS Galileo
  %(prog)s gps_data.ubx --constellation GPS -o gps_only_snr.png
        ''',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('ubx_file',
                       help='Path to the UBX file containing satellite data')

    parser.add_argument('-o', '--output',
                       help='Output file path for saving the plot (PNG format)')

    parser.add_argument('--title',
                       default='Satellite SNR Over Time',
                       help='Title for the plot (default: Satellite SNR Over Time)')

    parser.add_argument('--constellation',
                       nargs='*',
                       choices=['GPS', 'Galileo', 'GLONASS', 'BeiDou', 'QZSS', 'SBAS'],
                       help='Filter by constellation(s) (e.g., --constellation GPS Galileo)')

    parser.add_argument('--version',
                       action='version',
                       version='UBX SNR Analyzer 2.0.0 (pyubx2)')

    args = parser.parse_args()

    # Check if input file exists
    if not os.path.exists(args.ubx_file):
        print(f"Error: UBX file '{args.ubx_file}' not found.")
        sys.exit(1)

    print(f"Analyzing satellite SNR data from {args.ubx_file}")
    if args.constellation:
        print(f"Filtering constellations: {', '.join(args.constellation)}")

    # Parse the UBX file
    timestamps, satellite_data = parse_ubx_file(args.ubx_file)

    if not satellite_data:
        print("No satellite SNR data found in UBX file.")
        sys.exit(1)

    print(f"Found SNR data for {len(satellite_data)} satellites")
    if timestamps:
        print(f"Time range: {timestamps[0]} to {timestamps[-1]}")

    # Create visualization
    plot_snr_data(timestamps, satellite_data, args.title, args.output, args.constellation)

if __name__ == "__main__":
    main()