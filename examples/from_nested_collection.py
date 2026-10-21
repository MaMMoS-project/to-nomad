"""Example: convert a nested MaMMoS EntityCollection to a NOMAD archive.

Terminology used in this example:

- **mammos-entity collection YAML data file** (``nested_input.yaml``): a
  MaMMoS data file written by ``EntityCollection.to_yaml`` and read back with
  ``mammos_entity.from_yaml``. It is an *input* format, not a NOMAD artifact.
- **NOMAD archive YAML** (``*.archive.yaml``): the upload artifact for NOMAD
  with a ``definitions`` (schema) and a ``data`` section, uploaded together
  with the raw data files.

The nested collection is exported as HDF5 (data source for the NOMAD archive)
and as a mammos-entity collection YAML data file (round-trip via
``me.from_yaml``). With ``hdf_reference_mode=True``:

- every quantity (entities and plain values alike) is annotated with
  ``m_annotations.hdf5.path`` pointing into the HDF5 file, so values are not
  duplicated in the NOMAD archive YAML;
- plain values inside sub-collections are additionally kept inline in the
  NOMAD archive YAML ``data`` section (here: ``data.general_info``).

Entities are constructed with ``me.Entity(label, value, unit)`` instead of
shorthand constructors like ``me.Ms``: the shorthands are removed from the
mammos-entity main branch (PR #270) and no longer exist in upcoming versions.

Run with:
    pixi run python examples/from_nested_collection.py
"""

from pathlib import Path

import mammos_entity as me

import to_nomad

out_dir = Path(__file__).parent / "output"
out_dir.mkdir(exist_ok=True)

# Nested collection: sample -> general_info / intrinsic / hysteresis.
general_info = me.EntityCollection(
    description="General sample information",
    sample_id="demo-001",  # plain value: HDF5-referenced and kept inline
    is_simulation=False,  # plain boolean: HDF5-referenced and kept inline
)

intrinsic = me.EntityCollection(
    description="Intrinsic magnetic properties",
    Ms=me.Entity("SpontaneousMagnetization", [600, 680, 700], "kA/m"),
    T=me.Entity("ThermodynamicTemperature", [100, 250, 300], "K"),
    Hc=me.Entity("Coercivity", [700e3, 650e3, 800e3], "A/m"),
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
    general_info=general_info,
    intrinsic_properties=intrinsic,
    hysteresis_properties=hysteresis,
)

# Export the nested collection: HDF5 (data source for the NOMAD archive)
# and a mammos-entity collection YAML data file (portable round-trip format).
hdf_input = out_dir / "nested_input.h5"
yaml_input = out_dir / "nested_input.yaml"
sample.to_hdf5(hdf_input)
sample.to_yaml(yaml_input)

# Round-trip through the mammos-entity collection YAML data file to show that
# nested sub-collections survive the save/load cycle.
loaded = me.from_yaml(yaml_input)
assert float(loaded.intrinsic_properties.Ms.value[0]) == float(
    sample.intrinsic_properties.Ms.value[0]
)

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

# Save as HDF and generate the NOMAD archive YAML in one call.
hdf_saved, hdf_helper_out = to_nomad.save_hdf_and_to_nomad(
    sample,
    out_dir / "nested_input_helper.h5",
    out_dir / "from_nested_helper.archive.yaml",
    name="Demo From Nested HDF Helper",
    hdf_reference_mode=True,
    **common_meta,
)

print(f"Saved:     {hdf_input}")
print(f"Saved:     {yaml_input} (mammos-entity round-trip verified)")
print(f"Generated: {hdf_out}")
print(f"Saved:     {hdf_saved}")
print(f"Generated: {hdf_helper_out}")
