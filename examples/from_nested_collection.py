"""Example: convert a nested MaMMoS EntityCollection to a NOMAD archive.

Demonstrates ``hdf_reference_mode`` with an EntityCollection that contains
nested sub-collections:
- the collection is saved once as an HDF5 file,
- the NOMAD archive YAML references every quantity via ``m_annotations.hdf5.path``
  pointing into that HDF5 file (values are not duplicated in the YAML),
- plain values (strings, booleans) remain inline in the YAML ``data`` section.

Run with:
    pixi run python examples/from_nested_collection.py
"""

from pathlib import Path

import mammos_entity as me

import to_nomad

out_dir = Path(__file__).parent / "output"
out_dir.mkdir(exist_ok=True)

# Nested collection: sample -> intrinsic / hysteresis sub-collections.
intrinsic = me.EntityCollection(
    description="Intrinsic magnetic properties",
    Ms=me.Ms([600, 680, 700], "kA/m"),
    T=me.T([100, 250, 300], "K"),
    Hc=me.Hc([700e3, 650e3, 800e3], "A/m"),
)

hysteresis = me.EntityCollection(
    description="Hysteresis-loop properties",
    remanence=me.Entity("Remanence", 950e3, "A/m"),
    maximum_energy_product=me.Entity(
        "MaximumEnergyProduct", 320e3, "J/m**3"
    ),
)

sample = me.EntityCollection(
    description="Example nested NdFeB sample",
    sample_id="demo-001",  # plain value: stays inline in the YAML
    is_simulation=False,  # plain boolean: stays inline in the YAML
    intrinsic_properties=intrinsic,
    hysteresis_properties=hysteresis,
)

hdf_input = out_dir / "nested_input.h5"
sample.to_hdf5(hdf_input)

common_meta = dict(
    interactive=False,
    institute="Demo Institute",
    owner="Demo User",
    lab_id="DEMO-002",
    description="Converted from a nested MaMMoS EntityCollection.",
    chemical_formula="Nd2Fe14B",
    elemental_composition=[
        {"element": "Nd", "atomic_fraction": 2 / 17},
        {"element": "Fe", "atomic_fraction": 14 / 17},
        {"element": "B", "atomic_fraction": 1 / 17},
    ],
)

# Convert from the HDF file: quantities reference HDF datasets by path.
hdf_out = to_nomad.to_nomad(
    hdf_input,
    out_dir / "from_nested.archive.yaml",
    name="Demo From Nested HDF",
    hdf_reference_mode=True,
    **common_meta,
)

# Save as HDF and generate the NOMAD YAML in one call.
hdf_saved, hdf_helper_out = to_nomad.save_hdf_and_to_nomad(
    sample,
    out_dir / "nested_input_helper.h5",
    out_dir / "from_nested_helper.archive.yaml",
    name="Demo From Nested HDF Helper",
    hdf_reference_mode=True,
    **common_meta,
)

print(f"Saved:     {hdf_saved}")
print(f"Generated: {hdf_out}")
print(f"Saved:     {hdf_helper_out}")
print(f"Generated: {hdf_helper_out}")
