"""Example: x-y plot in NOMAD for plain (non-mammos-entity) data.

This demo shows the full x-y-plot mechanism from the specification:

1. Two plain numpy arrays (no mammos-entity objects, no ontology labels)
   are written into an HDF5 file with ``h5py``. Each dataset carries only
   a ``unit`` attribute, so ``mammos_entity.from_hdf5`` reads them as plain
   quantities.
2. ``to_nomad.to_nomad(..., hdf_reference_mode=True)`` generates a NOMAD
   archive YAML whose quantities reference the HDF5 datasets via
   ``m_annotations.hdf5.path`` (filled by NOMAD's ``HDF5Normalizer``).
3. The plot declaration is injected into the generated archive: the entry
   section gains the ``nomad.datamodel.metainfo.plot.PlotSection`` base
   section and a ``plotly_express`` scatter annotation pairing the two
   quantities as x and y, so the NOMAD GUI renders the curve as an x-y
   plot instead of two separate vectors.

The plot injection is done here on the generated YAML (not yet inside
to-nomad) — the in-tool feature is the subject of the x-y-plot
specification.

Upload ``from_curve_plain.archive.yaml`` together with
``plain_curve_input.h5`` (same upload) and open the entry to see the plot.

Run with:
    pixi run python examples/from_curve_plot_plain.py
"""

from pathlib import Path

import h5py
import numpy as np
import yaml

import to_nomad
from to_nomad._io import save_archive_yaml

out_dir = Path(__file__).parent / "output"
out_dir.mkdir(exist_ok=True)

# Plain (non-mammos-entity) curve data: magnetization M versus field H.
h_field = np.linspace(-800e3, 800e3, 41)
m_values = 1.2e6 * np.tanh(h_field / 200e3)

hdf_input = out_dir / "plain_curve_input.h5"
with h5py.File(hdf_input, "w") as f:
    f.create_dataset("field_strength", data=h_field).attrs["unit"] = "A / m"
    f.create_dataset("magnetization", data=m_values).attrs["unit"] = "A / m"

archive_path = to_nomad.to_nomad(
    hdf_input,
    out_dir / "from_curve_plain.archive.yaml",
    name="Demo Plain XY Plot",
    interactive=False,
    institute="Demo Institute",
    owner="Demo User",
    lab_id="DEMO-004",
    description="Plain (non-mammos-entity) x-y curve referenced from HDF5.",
    hdf_reference_mode=True,
)

# Inject the x-y plot declaration into the generated NOMAD archive YAML.
archive = yaml.safe_load(Path(archive_path).read_text())
section_name = next(iter(archive["definitions"]["sections"]))
section = archive["definitions"]["sections"][section_name]
section["base_sections"] = list(section.get("base_sections", [])) + [
    "nomad.datamodel.metainfo.plot.PlotSection"
]
section["m_annotations"] = {
    "plotly_express": [
        {
            "method": "scatter",
            "x": "#field_strength",
            "y": "#magnetization",
            "title": "M(H) — plain (non-mammos-entity) data",
        }
    ]
}
final_path = save_archive_yaml(archive, archive_path)

# Verify the injected annotation.
check = yaml.safe_load(Path(final_path).read_text())
injected = check["definitions"]["sections"][section_name]["m_annotations"]
assert injected["plotly_express"][0]["x"] == "#field_strength"

print(f"Saved:     {hdf_input}")
print(f"Generated: {final_path} (with PlotSection x-y plot annotation)")
