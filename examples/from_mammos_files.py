"""Example: convert MaMMoS YAML/CSV/HDF files to NOMAD archive YAML.

This follows the mammos-entity docs for YAML/CSV/HDF I/O:
- me.from_yaml(...)
- me.from_csv(...)
- HDF reader from mammos-entity

Run with:
    pixi run python examples/from_mammos_files.py
"""

from pathlib import Path

import mammos_entity as me

import to_nomad

out_dir = Path(__file__).parent / "output"
out_dir.mkdir(exist_ok=True)

# Create a sample collection and write MaMMoS files
collection = me.EntityCollection(
    description="Example NdFeB data to demonstrate file-based conversion.",
    Ms=me.Ms([600, 680, 700], "kA/m"),
    T=me.T([100, 250, 300], "K"),
    Hc=me.Hc([700e3, 650e3, 800e3], "A/m"),
)

yaml_input = out_dir / "example_input.yaml"
csv_input = out_dir / "example_input.csv"
hdf_input = out_dir / "example_input.h5"
collection.to_yaml(yaml_input)
collection.to_csv(csv_input)
collection.to_hdf5(hdf_input)

common_meta = dict(
    interactive=False,
    institute="Demo Institute",
    owner="Demo User",
    lab_id="DEMO-001",
    description="Converted from MaMMoS file examples.",
    chemical_formula="Nd2Fe14B",
    elemental_composition=[
        {"element": "Nd", "atomic_fraction": 2 / 17},
        {"element": "Fe", "atomic_fraction": 14 / 17},
        {"element": "B", "atomic_fraction": 1 / 17},
    ],
)

# Convert directly from YAML file path
yaml_out = to_nomad.to_nomad(
    yaml_input,
    out_dir / "from_yaml.archive.yaml",
    name="Demo From YAML",
    file_reference_mode=True,
    **common_meta,
)

# Convert directly from CSV file path
csv_out = to_nomad.to_nomad(
    csv_input,
    out_dir / "from_csv.archive.yaml",
    name="Demo From CSV",
    file_reference_mode=True,
    **common_meta,
)

# Convert directly from HDF file path
hdf_out = to_nomad.to_nomad(
    hdf_input,
    out_dir / "from_hdf.archive.yaml",
    name="Demo From HDF",
    hdf_reference_mode=True,
    include_hdf_metadata=True,
    hdf_entity_names=["Ms", "T"],
    **common_meta,
)

# Save as HDF and generate NOMAD YAML in one call
hdf_saved, hdf_helper_out = to_nomad.save_hdf_and_to_nomad(
    collection,
    out_dir / "example_input_helper.h5",
    out_dir / "from_hdf_helper.archive.yaml",
    name="Demo From HDF Helper",
    **common_meta,
)

print(f"Generated: {yaml_out}")
print(f"Generated: {csv_out}")
print(f"Generated: {hdf_out}")
print(f"Saved:     {hdf_saved}")
print(f"Generated: {hdf_helper_out}")
