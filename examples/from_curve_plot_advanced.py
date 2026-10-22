"""Example: x-y plots for several nested samples in NOMAD.

Demonstrates the advanced use of the ``plots`` parameter:

- a root collection holds several samples in parallel (``sample_A``,
  ``sample_B``, ``sample_C``), each with its own ``magnetization_curve``
  sub-collection (deeper nesting),
- one ``plots`` entry per sample targets the sub-collection via a dotted
  path, producing one overview figure per sample,
- the referenced HDF5 groups are tagged with NeXus ``NXdata`` attributes,
  so each curve also renders in the NOMAD H5Web file preview.

Upload ``advanced_curves.archive.yaml`` together with ``advanced_curves.h5``.

Run with:
    pixi run python examples/from_curve_plot_advanced.py
"""

from pathlib import Path

import numpy as np

import mammos_entity as me

import to_nomad

out_dir = Path(__file__).parent / "output"
out_dir.mkdir(exist_ok=True)


def make_sample(sample_id: str, ms: float, h0: float) -> me.EntityCollection:
    """Create one sample with an M(H) magnetization curve.

    Args:
        sample_id: Identifier stored as plain value in the sample.
        ms: Saturation magnetization of the curve (A/m).
        h0: Characteristic field of the tanh curve (A/m).
    """
    h_field = np.linspace(-800e3, 800e3, 51)
    m_values = ms * np.tanh(h_field / h0)
    return me.EntityCollection(
        description=f"Sample {sample_id}",
        sample_id=sample_id,
        magnetization_curve=me.EntityCollection(
            description="Magnetization vs Field Strength",
            H=me.Entity("MagneticFieldStrength", h_field, "A/m"),
            M=me.Entity("SpontaneousMagnetization", m_values, "A/m"),
        ),
    )


samples = me.EntityCollection(
    description="Several samples with M(H) curves",
    sample_A=make_sample("SAMPLE-A", 1.2e6, 200e3),
    sample_B=make_sample("SAMPLE-B", 0.9e6, 150e3),
    sample_C=make_sample("SAMPLE-C", 1.5e6, 300e3),
)

h5_path = out_dir / "advanced_curves.h5"
yaml_path = out_dir / "advanced_curves.archive.yaml"
samples.to_hdf5(h5_path)

to_nomad.to_nomad(
    h5_path,
    yaml_path,
    name="Advanced Curve Plot Demo",
    interactive=False,
    institute="MaMMoS Project",
    owner="Consortium Member",
    lab_id="DEMO-CURVE-002",
    chemical_formula="Nd2Fe14B",
    hdf_reference_mode=True,
    plots=[
        {
            "target": "sample_A.magnetization_curve",
            "x": "H",
            "y": "M",
            "label": "Sample A: M(H)",
        },
        {
            "target": "sample_B.magnetization_curve",
            "x": "H",
            "y": "M",
            "label": "Sample B: M(H)",
        },
        {
            "target": "sample_C.magnetization_curve",
            "x": "H",
            "y": "M",
            "label": "Sample C: M(H)",
        },
    ],
)

print(f"HDF5 file with NeXus metadata: {h5_path}")
print(f"NOMAD Archive YAML with plots: {yaml_path}")
