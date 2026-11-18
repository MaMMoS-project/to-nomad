"""Example: store an SEM image (TIFF) in a MaMMoS EntityCollection.

A published SEM micrograph from the MaMMoS_IFW_SEM upload on the central
NOMAD instance (``examples/input/22632_01_CBS.tif``, 1536x1094 grayscale)
is read as a numpy array, stored in a nested EntityCollection, and
exported with ``hdf_reference_mode=True``:

- the image data lives once in the HDF5 file (as a plain dataset),
- the NOMAD archive YAML references it via ``m_annotations.hdf5.path``,
- the collection nests the image next to plain metadata values.

Run with:
    pixi run python examples/from_sem_image.py
"""

from pathlib import Path

import numpy as np
import tifffile

import mammos_entity as me

import to_nomad

out_dir = Path(__file__).parent / "output"
out_dir.mkdir(exist_ok=True)

# The image file is NOT committed to the repository (see .gitignore); it is
# fetched from the published MaMMoS_IFW_SEM upload via the NOMAD raw API:
# /uploads/6NzAe8uWS5SCsuKNvl7EUw/raw/IFW_SEM_RawData/22632_01_CBS.tif
tif_path = Path(__file__).parent / "input" / "22632_01_CBS.tif"
# TIFF rasters store row 0 at the visual top, while the NOMAD renderers
# (H5Web matrix view and the PlotSection figure, which rebuilds the figure
# from the trace and loses imshow's reversed y-axis) draw row 0 at the
# bottom. Flip vertically so the stored array is in display orientation.
image = np.flipud(tifffile.imread(tif_path))

sem_image = me.EntityCollection(
    description="Scanning electron microscope image",
    image_data=image,  # plain numpy array: stored once in the HDF5 file
)

# Ontology-backed measurement context stored alongside the image.
# NOTE: the values below are exemplar values for demonstration purposes,
# not the actual imaging conditions of the source micrograph.
measurement_conditions = me.EntityCollection(
    description="Measurement conditions during imaging (exemplar values)",
    temperature=me.Entity("ThermodynamicTemperature", 295, "K"),
    magnetic_field=me.Entity("MagneticFieldStrength", 0.0, "A/m"),
)

sample = me.EntityCollection(
    description="Sample with an SEM micrograph",
    sample_id="SEM-DEMO-001",  # plain value: HDF5-referenced and kept inline
    measurement_conditions=measurement_conditions,
    sem_image=sem_image,
)

h5_path = out_dir / "sem_image.h5"
yaml_path = out_dir / "sem_image.archive.yaml"
sample.to_hdf5(h5_path)

to_nomad.to_nomad(
    h5_path,
    yaml_path,
    name="SEM Image Demo",
    interactive=False,
    institute="MaMMoS Project",
    owner="Consortium Member",
    lab_id="DEMO-SEM-001",
    description="SEM micrograph referenced from an HDF5 file.",
    chemical_formula="Nd2Fe14B",
    hdf_reference_mode=True,
    plots=[
        {
            "target": "sem_image",
            "img": "image_data",
            "method": "imshow",
            "label": "SEM micrograph",
        }
    ],
)

print(f"Image:     {tif_path} shape={image.shape} dtype={image.dtype}")
print(f"Saved:     {h5_path}")
print(f"Generated: {yaml_path}")
