"""Prepare MaMMoS CSV column names for NOMAD upload.

This module provides utilities for preparing MaMMoS CSV files for NOMAD upload,
particularly when using HDF5 reference mode. Column names with certain characters
(notably '/') can cause issues with NOMAD's HDF5Normalizer.

Data values are preserved exactly - only column names are optionally changed.

Sanitization rules (matching to_nomad's identifier sanitization in _nomad_quantity_name):
- / -> _per_   (prevents nested HDF5 groups)
- % -> _pct_   (NOMAD Metainfo compatibility)
- ., ^, -, spaces -> _  (valid Python identifier requirement)
- Leading digits prefixed with _ (valid Python identifier requirement)
- Consecutive underscores collapsed
- Leading/trailing underscores trimmed
"""

import csv
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


def sanitize_column_name(name: str) -> str:
    """Sanitize a column name to be NOMAD-compatible.
    
    This matches the logic in to_nomad._schema._nomad_quantity_name()
    to ensure consistency between CSV column names and NOMAD quantity names.
    
    Args:
        name: The original column name to sanitize.
        
    Returns:
        The sanitized column name, or 'quantity' if the name is empty after sanitization.
    """
    # Step 1: Replace special characters with safe alternatives
    s = name.replace("%", "_pct_").replace("/", "_per_").replace("^", "_")
    
    # Step 2: Replace remaining unsafe characters with underscore
    s = re.sub(r"[^a-zA-Z0-9_]", "_", s)
    
    # Step 3: Collapse consecutive underscores
    s = re.sub(r"_+", "_", s).strip("_")
    
    # Step 4: Prefix leading digits
    if s and s[0].isdigit():
        s = "_" + s
    
    # Step 5: Return sanitized name or fallback
    return s if s else "quantity"


def find_header_rows(csv_path: Path) -> tuple[int, int, int, int]:
    """Find the header rows in a MaMMoS CSV file.
    
    Returns:
        A tuple of (descriptive_names_row, iri_row, units_row, short_labels_row)
        
    MaMMoS CSV v3 format:
    - Row 0-3: Comments (start with #)
    - Row 4: Descriptive names (e.g., "Length", "Length", ...)
    - Row 5: Empty
    - Row 6: Ontology IRIs
    - Row 7: Units
    - Row 8: Short labels (actual column names)
    """
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows = []
        for i, row in enumerate(reader):
            rows.append(row)
            # Stop after we find the data rows (when we see actual numbers)
            if i > 10:  # Look at first 11 rows to find headers
                # Check if this looks like a data row (starts with numbers)
                if row and row[0].strip() and (row[0].strip()[0].isdigit() or 
                    row[0].strip().lstrip('-').replace('.', '').isdigit()):
                    break
    
    # Find the pattern: comment, comment, comment, comment, descriptive, empty, IRI, units, short_labels
    header_indices = {
        'descriptive': None,
        'iri': None,
        'units': None,
        'short_labels': None,
    }
    
    for i, row in enumerate(rows[:15]):
        if not row:
            continue
        first_cell = row[0].strip() if row else ""
        
        # Descriptive names row: contains words like "Length", "Temperature", etc.
        if header_indices['descriptive'] is None and first_cell and not first_cell.startswith('#') and first_cell not in ['', 'mm', 'nm', 'K']:
            # Check if this looks like descriptive names (alphabetic with spaces/caps)
            if any(c.isalpha() for c in first_cell) and first_cell not in ['https:', 'http:']:
                header_indices['descriptive'] = i
        
        # IRI row: starts with https://
        if header_indices['iri'] is None and first_cell.startswith('https://'):
            header_indices['iri'] = i
        
        # Units row: contains units like mm, nm, K, T, etc.
        if header_indices['units'] is None and first_cell in ['mm', 'nm', 'K', 'T', 's', 'A/m', 'J/m', '%', 'deg_C']:
            header_indices['units'] = i
        
        # Short labels row: comes after units row
        if header_indices['units'] is not None and header_indices['short_labels'] is None and i == header_indices['units'] + 1:
            # Check if this looks like short labels (contains underscores, lowercase)
            if '_' in row[0] or row[0].replace('-', '').replace('.', '').isalnum():
                header_indices['short_labels'] = i
    
    # If we couldn't find all, use default positions for MaMMoS CSV v3
    if any(v is None for v in header_indices.values()):
        # Default positions for standard MaMMoS CSV v3
        header_indices = {
            'descriptive': 4,
            'iri': 6,
            'units': 7,
            'short_labels': 8,
        }
    
    return (header_indices['descriptive'], 
            header_indices['iri'], 
            header_indices['units'], 
            header_indices['short_labels'])


def prepare_csv_for_nomad(
    input_path: str | Path,
    output_path: str | Path,
    sanitize: bool = True,
) -> None:
    """Prepare a MaMMoS CSV file for NOMAD upload.
    
    This function reads a MaMMoS CSV file and creates a new version that is
    compatible with NOMAD's HDF5 reference mode. When sanitize=True (default),
    column names are sanitized to prevent nested HDF5 group structures.
    
    Args:
        input_path: Path to the input MaMMoS CSV file.
        output_path: Path where the prepared CSV file will be written.
        sanitize: If True, column names are sanitized to be NOMAD-compatible.
            If False, the CSV is copied without modifying column names.
            Default is True.
    
    Example:
        >>> from to_nomad.prepare_csv_for_nomad import prepare_csv_for_nomad
        >>> prepare_csv_for_nomad("input.csv", "output.csv")
        >>> # Or without sanitization:
        >>> prepare_csv_for_nomad("input.csv", "output.csv", sanitize=False)
    """
    input_path = Path(input_path)
    output_path = Path(output_path)
    
    with open(input_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows = list(reader)
    
    # Find header rows
    desc_row, iri_row, units_row, labels_row = find_header_rows(input_path)
    
    if sanitize:
        # Sanitize the short labels (actual column names)
        original_labels = [cell.strip() for cell in rows[labels_row]]
        sanitized_labels = [sanitize_column_name(name) for name in original_labels]
        
        # Create a mapping for verification
        print(f"Identified header rows:")
        print(f"  Descriptive names: row {desc_row}")
        print(f"  IRIs:             row {iri_row}")
        print(f"  Units:            row {units_row}")
        print(f"  Short labels:     row {labels_row}")
        
        print(f"\nColumn name changes:")
        changes = False
        for orig, new in zip(original_labels, sanitized_labels):
            if orig != new:
                print(f"  '{orig}' -> '{new}'")
                changes = True
        
        if not changes:
            print("  No changes needed - all column names are already clean")
        
        # Replace the short labels row with sanitized names
        rows[labels_row] = sanitized_labels
    else:
        print(f"Sanitization disabled - copying CSV without modifying column names")
    
    # Write to output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(rows)
    
    print(f"\nPrepared CSV written to: {output_path}")
    print(f"Original: {input_path}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Prepare MaMMoS CSV files for NOMAD upload"
    )
    parser.add_argument(
        "input",
        help="Input CSV file path"
    )
    parser.add_argument(
        "output",
        help="Output CSV file path"
    )
    parser.add_argument(
        "--no-sanitize",
        action="store_true",
        help="Disable column name sanitization (copy CSV as-is)"
    )
    
    args = parser.parse_args()
    
    prepare_csv_for_nomad(
        args.input,
        args.output,
        sanitize=not args.no_sanitize
    )
