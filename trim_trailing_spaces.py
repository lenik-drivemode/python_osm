#!/usr/bin/env python3
"""
Script to trim trailing spaces from all Python files in the current directory.
"""

import os
import glob

def trim_trailing_spaces_from_file(filepath):
    """
    Remove trailing spaces from all lines in a file.

    Args:
        filepath (str): Path to the file to process

    Returns:
        bool: True if file was modified, False otherwise
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            lines = file.readlines()

        # Check if any lines have trailing spaces
        modified = False
        trimmed_lines = []

        for line in lines:
            trimmed_line = line.rstrip() + '\n' if line.endswith('\n') else line.rstrip()
            trimmed_lines.append(trimmed_line)
            if trimmed_line != line:
                modified = True

        # Only write back if file was modified
        if modified:
            with open(filepath, 'w', encoding='utf-8') as file:
                file.writelines(trimmed_lines)
            return True

        return False

    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return False

def main():
    """Find all Python files and trim trailing spaces."""
    # Get all Python files in current directory
    python_files = glob.glob('*.py')

    if not python_files:
        print("No Python files found in current directory.")
        return

    print(f"Found {len(python_files)} Python files to check...")

    modified_count = 0

    for py_file in sorted(python_files):
        print(f"Checking {py_file}...", end=' ')

        if trim_trailing_spaces_from_file(py_file):
            print("✓ Modified (trailing spaces removed)")
            modified_count += 1
        else:
            print("✓ Clean (no trailing spaces)")

    print(f"\nSummary: {modified_count} files modified, {len(python_files) - modified_count} files were already clean.")

if __name__ == "__main__":
    main()