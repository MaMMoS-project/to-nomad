"""Example: a sample collection with curves, images, and a structure.

Three samples (``sample_A``, ``sample_B``, ``sample_C``) are stored in
parallel, each combining:

- an M(H) magnetization curve (nested sub-collection, plotted per
  sample),
- an SEM micrograph (nested sub-collection, imshow figure per sample;
  the same image for all three samples in this first step),
- one shared crystal structure: ``structure_file`` embeds a single
  inline ``run`` section for the whole entry (correct here, since all
  samples share the same .cif).

Known limitation: ``to_nomad(..., structure_file=...)` creates ONE
structure per archive (entry level). Per-sample structures with
different .cif files would require a to-nomad extension.

IMPORTANT (workaround): NOMAD does not read the .cif server-side. The
structure preview comes from the run section that to_nomad embedded at
generation time. Changing the .cif and re-uploading only the .cif does
NOT change the preview — regenerate the archive with to_nomad(...).
No ``chemical_formula`` is passed: with an inline run section the
server-side chain derives the composition from the structure itself
(a formula would collide with it, see the repository README).

GUI trade-off (new NOMAD interface): the structure preview requires
``domain: dft``, and dft-domain entries render the DFT-style Overview —
which shows the Material/structure card but does NOT include the
generic Figures card. The 6 figures remain reachable under
Archive -> Data -> Figures. Archives WITHOUT a structure render their
figures in the Overview instead. Choose per archive which presentation
matters more.

The image values are exemplar data (same published SEM micrograph for
all three samples); the entity values are exemplar values.

Upload ``sample_collection.archive.yaml`` together with
``sample_collection.h5`` and the copied ``cif_structure_Co2Fe2H4.cif``.

Run with:
    pixi run python examples/from_sample_collection.py
"""

from pathlib import Path

import numpy as np
import tifffile

import mammos_entity as me

import to_nomad

out_dir = Path(__file__).parent / "output"
out_dir.mkdir(exist_ok=True)

cif_path = Path(__file__).parent / "input" / "cif_structure_Co2Fe2H4.cif"
tif_path = Path(__file__).parent / "input" / "22632_01_CBS.tif"
# TIFF rasters store row 0 at the visual top, while the NOMAD renderers
# draw row 0 at the bottom. Flip vertically so the stored array is in
# display orientation (same as examples/from_sem_image.py).
image = np.flipud(tifffile.imread(tif_path))


def make_sample(sample_id: str, ms: float, h0: float) -> me.EntityCollection:
    """Create one sample with a curve and an image.

    Args:
        sample_id: Identifier stored as plain value in the sample.
        ms: Saturation magnetization of the curve (A/m).
        h0: Characteristic field of the tanh curve (A/m).
    """
    h_field = np.linspace(-800e3, 800e3, 51)
    m_values = ms * np.tanh(h_field / h0)
    return me.EntityCollection(
        description=f"Sample {sample_id} (exemplar values)",
        sample_id=sample_id,
        magnetization_curve=me.EntityCollection(
            description="Magnetization vs Field Strength",
            H=me.Entity("MagneticFieldStrength", h_field, "A/m"),
            M=me.Entity("SpontaneousMagnetization", m_values, "A/m"),
        ),
        sem_image=me.EntityCollection(
            description="SEM micrograph (exemplar image)",
            image_data=image,  # plain numpy array: stored once per sample
        ),
    )


samples = me.EntityCollection(
    description="Several samples with curves, images and a shared structure",
    sample_A=make_sample("SAMPLE-A", 1.2e6, 200e3),
    sample_B=make_sample("SAMPLE-B", 0.9e6, 150e3),
    sample_C=make_sample("SAMPLE-C", 1.5e6, 300e3),
)

h5_path = out_dir / "sample_collection.h5"
yaml_path = out_dir / "sample_collection.archive.yaml"
samples.to_hdf5(h5_path)

to_nomad.to_nomad(
    h5_path,
    yaml_path,
    name="Sample Collection Demo",
    interactive=False,
    institute="MaMMoS Project",
    owner="Consortium Member",
    lab_id="DEMO-COLLECTION-001",
    hdf_reference_mode=True,
    structure_file=cif_path,
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
        {
            "target": "sample_A.sem_image",
            "img": "image_data",
            "method": "imshow",
            "label": "Sample A: SEM micrograph",
        },
        {
            "target": "sample_B.sem_image",
            "img": "image_data",
            "method": "imshow",
            "label": "Sample B: SEM micrograph",
        },
        {
            "target": "sample_C.sem_image",
            "img": "image_data",
            "method": "imshow",
            "label": "Sample C: SEM micrograph",
        },
    ],
)

print(f"HDF5 file with NeXus metadata: {h5_path}")
print(f"NOMAD Archive YAML with plots: {yaml_path}")
