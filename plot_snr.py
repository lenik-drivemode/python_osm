#!/usr/bin/env python3
"""
This script reads UBX files from u-blox GNSS receivers and creates
graphs showing Signal-to-Noise Ratio (SNR) for satellites over time.
Each satellite is plotted with a different color.
"""

import struct
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import argparse
import sys
import os
import numpy as np
from collections import defaultdict

class UBXParser:
    """Parser for UBX binary format files."""

    def __init__(self, filename):
        self.filename = filename
        self.file = None

    def __enter__(self):
        self.file = open(self.filename, 'rb')
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.file:
            self.file.close()

    def read_uint8(self):
        """Read unsigned 8-bit integer."""
        data = self.file.read(1)
        if len(data) != 1:
            return None
        return struct.unpack('<B', data)[0]

    def read_uint16(self):
        """Read unsigned 16-bit integer."""
        data = self.file.read(2)
        if len(data) != 2:
            return None
        return struct.unpack('<H', data)[0]

    def read_uint32(self):
        """Read unsigned 32-bit integer."""
        data = self.file.read(4)
        if len(data) != 4:
            return None
        return struct.unpack('<L', data)[0]

    def read_int8(self):
        """Read signed 8-bit integer."""
        data = self.file.read(1)
        if len(data) != 1:
            return None
        return struct.unpack('<b', data)[0]

    def read_int16(self):
        """Read signed 16-bit integer."""
        data = self.file.read(2)
        if len(data) != 2:
            return None
        return struct.unpack('<h', data)[0]

    def read_int32(self):
        """Read signed 32-bit integer."""
        data = self.file.read(4)
        if len(data) != 4:
            return None
        return struct.unpack('<l', data)[0]

    def find_sync(self):
        """Find UBX sync pattern (0xB5 0x62)."""
        while True:
            b1 = self.read_uint8()
            if b1 is None:
                return False
            if b1 == 0xB5:
                b2 = self.read_uint8()
                if b2 is None:
                    return False
                if b2 == 0x62:
                    return True

    def parse_message(self):
        """Parse a single UBX message."""
        if not self.find_sync():
            return None

        # Read message class and ID
        msg_class = self.read_uint8()
        msg_id = self.read_uint8()
        length = self.read_uint16()

        if msg_class is None or msg_id is None or length is None:
            return None

        # Read payload
        payload = self.file.read(length)
        if len(payload) != length:
            return None

        # Read checksum
        ck_a = self.read_uint8()
        ck_b = self.read_uint8()

        if ck_a is None or ck_b is None:
            return None

        # Verify checksum
        calc_ck_a = 0
        calc_ck_b = 0

        # Include class, id, and length in checksum
        for byte in [msg_class, msg_id, length & 0xFF, (length >> 8) & 0xFF]:
            calc_ck_a = (calc_ck_a + byte) & 0xFF
            calc_ck_b = (calc_ck_b + calc_ck_a) & 0xFF

        # Include payload in checksum
        for byte in payload:
            calc_ck_a = (calc_ck_a + byte) & 0xFF
            calc_ck_b = (calc_ck_b + calc_ck_a) & 0xFF

        if calc_ck_a != ck_a or calc_ck_b != ck_b:
            print(f"Checksum error: expected {ck_a:02X} {ck_b:02X}, got {calc_ck_a:02X} {calc_ck_b:02X}")
            return None

        return {
            'class': msg_class,
            'id': msg_id,
            'length': length,
            'payload': payload
        }

def parse_nav_sat(payload):
    """Parse UBX-NAV-SAT message for satellite information."""
    if len(payload) < 8:
        return None

    # Parse header
    iTOW = struct.unpack('<L', payload[0:4])[0]  # GPS time of week (ms)
    version = payload[4]
    num_svs = payload[5]
    reserved = payload[6:8]

    satellites = []
    offset = 8

    for i in range(num_svs):
        if offset + 12 > len(payload):
            break

        # Parse satellite info (12 bytes per satellite)
        gnss_id = payload[offset]
        sv_id = payload[offset + 1]
        cno = payload[offset + 2]  # Signal strength (dB-Hz)
        elev = struct.unpack('<b', payload[offset + 3:offset + 4])[0]  # Elevation (deg)
        azim = struct.unpack('<h', payload[offset + 4:offset + 6])[0]  # Azimuth (deg)
        pr_res = struct.unpack('<h', payload[offset + 6:offset + 8])[0]  # Pseudorange residual (0.1m)
        flags = struct.unpack('<L', payload[offset + 8:offset + 12])[0]

        # Extract quality indicator and health flags
        quality = flags & 0x7
        sv_used = (flags & 0x8) != 0
        health = (flags >> 4) & 0x3

        satellites.append({
            'gnss_id': gnss_id,
            'sv_id': sv_id,
            'cno': cno,
            'elevation': elev,
            'azimuth': azim,
            'pr_residual': pr_res * 0.1,  # Convert to meters
            'quality': quality,
            'used': sv_used,
            'health': health
        })

        offset += 12

    return {
        'iTOW': iTOW,
        'version': version,
        'num_satellites': num_svs,
        'satellites': satellites
    }

def parse_nav_pvt(payload):
    """Parse UBX-NAV-PVT message for timestamp information."""
    if len(payload) < 84:
        return None

    iTOW = struct.unpack('<L', payload[0:4])[0]
    year = struct.unpack('<H', payload[4:6])[0]
    month = payload[6]
    day = payload[7]
    hour = payload[8]
    minute = payload[9]
    second = payload[10]
    valid = payload[11]

    # Check if date/time is valid
    if (valid & 0x04) == 0:  # validDate bit
        return None
    if (valid & 0x02) == 0:  # validTime bit
        return None

    try:
        timestamp = datetime(year, month, day, hour, minute, second)
        return {
            'iTOW': iTOW,
            'timestamp': timestamp
        }
    except ValueError:
        return None

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
    Parse UBX file and extract satellite SNR data.

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
        with UBXParser(filename) as parser:
            message_count = 0
            nav_sat_count = 0
            nav_pvt_count = 0

            print(f"Parsing UBX file: {filename}")

            while True:
                message = parser.parse_message()
                if message is None:
                    break

                message_count += 1

                # Process NAV-PVT messages for time reference
                if message['class'] == 0x01 and message['id'] == 0x07:  # NAV-PVT
                    nav_pvt_count += 1
                    pvt_data = parse_nav_pvt(message['payload'])
                    if pvt_data:
                        current_time_ref[pvt_data['iTOW']] = pvt_data['timestamp']

                # Process NAV-SAT messages for satellite data
                elif message['class'] == 0x01 and message['id'] == 0x35:  # NAV-SAT
                    nav_sat_count += 1
                    sat_data = parse_nav_sat(message['payload'])
                    if sat_data:
                        iTOW = sat_data['iTOW']

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
                            for sat in sat_data['satellites']:
                                sat_id = get_satellite_id(sat['gnss_id'], sat['sv_id'])
                                snr = sat['cno']  # C/N0 in dB-Hz

                                # Only include satellites with valid SNR
                                if snr > 0:
                                    satellite_data[sat_id].append((timestamp, snr))

                                    if timestamp not in timestamps:
                                        timestamps.append(timestamp)

                if message_count % 1000 == 0:
                    print(f"Processed {message_count} messages...")

            print(f"Parsing complete:")
            print(f"  Total messages: {message_count}")
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
        return [], {}

def plot_snr_data(timestamps, satellite_data, title="Satellite SNR Over Time", filepath=None):
    """
    Create a plot showing satellite SNR over time.

    Args:
        timestamps (list): List of datetime objects
        satellite_data (dict): Dictionary with satellite IDs as keys and (timestamp, snr) lists as values
        title (str): Plot title
        filepath (str, optional): Path to save the plot
    """
    if not satellite_data:
        print("No satellite SNR data to plot")
        return

    fig, ax = plt.subplots(figsize=(14, 8))

    # Generate colors for satellites
    colors = plt.cm.tab10(np.linspace(0, 1, min(len(satellite_data), 10)))
    if len(satellite_data) > 10:
        # Use tab20 for more satellites
        colors = plt.cm.tab20(np.linspace(0, 1, min(len(satellite_data), 20)))
    if len(satellite_data) > 20:
        # Use viridis for even more satellites
        colors = plt.cm.viridis(np.linspace(0, 1, len(satellite_data)))

    # Plot each satellite
    for i, (sat_id, data_points) in enumerate(sorted(satellite_data.items())):
        if not data_points:
            continue

        times, snrs = zip(*data_points)
        color = colors[i % len(colors)]

        ax.plot(times, snrs, 'o-', color=color, label=sat_id,
                linewidth=1, markersize=3, alpha=0.7)

    # Customize the plot
    ax.set_xlabel('Time', fontsize=12)
    ax.set_ylabel('Signal Strength (dB-Hz)', fontsize=12)
    ax.set_title(title, fontsize=14, pad=20)
    ax.grid(True, alpha=0.3)

    # Format x-axis dates
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
    ax.xaxis.set_major_locator(mdates.MinuteLocator(interval=1))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')

    # Set y-axis limits
    all_snrs = [snr for data in satellite_data.values() for _, snr in data]
    if all_snrs:
        min_snr = min(all_snrs)
        max_snr = max(all_snrs)
        ax.set_ylim(max(0, min_snr - 5), max_snr + 5)

    # Add legend (with maximum columns to prevent overcrowding)
    ncol = min(4, len(satellite_data))
    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', ncol=1, fontsize=8)

    # Add statistics
    stats_text = f"Satellites: {len(satellite_data)}\n"
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
        description='Parse UBX files and visualize satellite SNR data over time',
        epilog='''
Examples:
  %(prog)s gps_data.ubx
  %(prog)s gps_data.ubx -o snr_plot.png
  %(prog)s gps_data.ubx --title "Satellite SNR Analysis"
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

    parser.add_argument('--version',
                       action='version',
                       version='UBX SNR Analyzer 1.0.0')

    args = parser.parse_args()

    # Check if input file exists
    if not os.path.exists(args.ubx_file):
        print(f"Error: UBX file '{args.ubx_file}' not found.")
        sys.exit(1)

    print(f"Analyzing satellite SNR data from {args.ubx_file}")

    # Parse the UBX file
    timestamps, satellite_data = parse_ubx_file(args.ubx_file)

    if not satellite_data:
        print("No satellite SNR data found in UBX file.")
        sys.exit(1)

    print(f"Found SNR data for {len(satellite_data)} satellites")
    if timestamps:
        print(f"Time range: {timestamps[0]} to {timestamps[-1]}")

    # Create visualization
    plot_snr_data(timestamps, satellite_data, args.title, args.output)

if __name__ == "__main__":
    main()