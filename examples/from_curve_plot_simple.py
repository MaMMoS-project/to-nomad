"""Simple example: plot a curve in NOMAD from a MaMMoS EntityCollection.

Uses Method 2 in `to_nomad` to automatically:
1. Tag the HDF5 group with NeXus NXdata attributes (for NOMAD H5Web viewer).
2. Inject PlotSection & plotly_express into the YAML schema (for NOMAD entry overview).
"""

from pathlib import Path
import numpy as np
import mammos_entity as me
import to_nomad

out_dir = Path(__file__).parent / "output"
out_dir.mkdir(exist_ok=True)

# 1. Create curve data with units
h_field = np.linspace(-800e3, 800e3, 51)
m_values = 1.2e6 * np.tanh(h_field / 200e3)

col = me.EntityCollection(
    description="Sample with M(H) curve",
    sample_id="SAMPLE-CURVE-001",
    magnetization_curve=me.EntityCollection(
        description="Magnetization vs Field Strength",
        H=me.Entity("MagneticFieldStrength", h_field, "A/m"),
        M=me.Entity("SpontaneousMagnetization", m_values, "A/m"),
    ),
)

h5_path = out_dir / "simple_curve.h5"
yaml_path = out_dir / "simple_curve.archive.yaml"

# 2. Save collection to HDF5
col.to_hdf5(h5_path)

# 3. Call to_nomad with Method 2: one call configures H5Web + Entry Plotly overview
to_nomad.to_nomad(
    h5_path,
    yaml_path,
    name="Simple Curve Plot Demo",
    interactive=False,
    institute="MaMMoS Project",
    owner="Consortium Member",
    lab_id="DEMO-CURVE-001",
    chemical_formula="Nd2Fe14B",
    hdf_reference_mode=True,
    plots=[
        {
            "target": "magnetization_curve",
            "x": "H",
            "y": "M",
            "label": "M(H) curve",
        }
    ],
)

print(f"HDF5 file with NeXus metadata: {h5_path}")
print(f"NOMAD Archive YAML with plot:  {yaml_path}")

