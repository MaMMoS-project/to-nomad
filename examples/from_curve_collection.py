"""Example: store a curve (array-valued entities) for viewing in NOMAD.

A magnetization-versus-field curve ``M(H)`` is stored as array-valued
entities inside a nested collection. In ``hdf_reference_mode``:

- the arrays are written once into the HDF5 file (raw data file of the
  NOMAD upload, inspectable in the NOMAD interface),
- the NOMAD archive YAML references both arrays via
  ``m_annotations.hdf5.path`` and declares them with ``shape: ['*']``,
  so the normalized entry holds the full curve as array quantities.

Run with:
    pixi run python examples/from_curve_collection.py
"""

from pathlib import Path

import numpy as np

import mammos_entity as me

import to_nomad

out_dir = Path(__file__).parent / "output"
out_dir.mkdir(exist_ok=True)

# Magnetization curve M(H): simple anhysteretic loop for demonstration.
h_field = np.linspace(-800e3, 800e3, 41)
m_values = 1.2e6 * np.tanh(h_field / 200e3)

magnetization_curve = me.EntityCollection(
    description="Magnetization versus magnetic field strength",
    H=me.Entity("MagneticFieldStrength", h_field, "A/m"),
    M=me.Entity("SpontaneousMagnetization", m_values, "A/m"),
)

sample = me.EntityCollection(
    description="Example sample with a magnetization curve",
    sample_id="curve-demo-001",  # plain value: HDF5-referenced and kept inline
    magnetization_curve=magnetization_curve,
)

hdf_input = out_dir / "curve_input.h5"
sample.to_hdf5(hdf_input)

curve_out = to_nomad.to_nomad(
    hdf_input,
    out_dir / "from_curve.archive.yaml",
    name="Demo Curve From HDF",
    interactive=False,
    institute="Demo Institute",
    owner="Demo User",
    lab_id="DEMO-003",
    description="Magnetization curve referenced from an HDF5 file.",
    chemical_formula="Nd2Fe14B",
    hdf_reference_mode=True,
)

print(f"Saved:     {hdf_input}")
print(f"Generated: {curve_out}")
