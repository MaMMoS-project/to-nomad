"""Example: x-y plot in NOMAD for plain (non-mammos-entity) data.

This demo shows the full x-y-plot mechanism from the specification:

1. Two plain numpy arrays (no mammos-entity objects, no ontology labels)
   are written into an HDF5 file with ``h5py``. Each dataset carries only
   a ``unit`` attribute, so ``mammos_entity.from_hdf5`` reads them as plain
   quantities. A third dataset holds the curve as a table (matrix) with H
   and M as columns next to each other; it is excluded from the NOMAD
   quantities via ``hdf_entity_names`` and shows up as a matrix in the
   NOMAD HDF5 file preview.
2. ``to_nomad.to_nomad(..., hdf_reference_mode=True)`` generates a NOMAD
   archive YAML whose quantities reference the HDF5 datasets via
   ``m_annotations.hdf5.path`` (filled by NOMAD's ``HDF5Normalizer``).
3. The plot declaration is injected into the generated archive: the entry
   section gains the ``nomad.datamodel.metainfo.plot.PlotSection`` base
   section and a ``plotly_express`` scatter annotation pairing the two
   quantities as x and y. The annotation's ``layout`` block titles the plot
   and both axes with their physical meaning and units (taken from the
   quantity definitions), so the NOMAD GUI renders a labelled x-y curve
   instead of two separate vectors.

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
    # Table (matrix) view of the curve: H and M as columns next to each
    # other. Excluded from the NOMAD archive via hdf_entity_names below;
    # visible as a matrix in the NOMAD HDF5 file preview.
    table = f.create_dataset(
        "magnetization_curve_table", data=np.column_stack((h_field, m_values))
    )
    table.attrs["columns"] = [
        "field_strength (A / m)",
        "magnetization (A / m)",
    ]

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
    hdf_entity_names=["field_strength", "magnetization"],
)

# Inject the x-y plot declaration into the generated NOMAD archive YAML.
# PlotSection must be listed BEFORE the data-filling base section
# (HDF5Normalizer): if the data-filling section comes first, the plotly
# figures are created before the HDF data is read and the plot stays empty
# (nomad-FAIR issue #2717).
archive = yaml.safe_load(Path(archive_path).read_text())
section_name = next(iter(archive["definitions"]["sections"]))
section = archive["definitions"]["sections"][section_name]


def unit_of(quantity_name: str) -> str:
    """Return the unit string of an entry-section quantity from the archive."""
    quantity_defs = section.get("quantities", {})
    return quantity_defs.get(quantity_name, {}).get("unit", "dimensionless")


base = list(section.get("base_sections", []))
plot_base = "nomad.datamodel.metainfo.plot.PlotSection"
if plot_base not in base:
    idx = next(
        (i for i, b in enumerate(base) if "HDF5Normalizer" in b),
        len(base),
    )
    base.insert(idx, plot_base)
section["base_sections"] = base
section["m_annotations"] = {
    "plotly_express": [
        {
            "method": "scatter",
            "x": "#field_strength",
            "y": "#magnetization",
            "label": "M(H) curve",
            "layout": {
                "title": {"text": "Magnetization vs Field"},
                "xaxis": {
                    "title": {
                        "text": f"Magnetic Field Strength ({unit_of('field_strength')})"
                    }
                },
                "yaxis": {
                    "title": {"text": f"Magnetization ({unit_of('magnetization')})"}
                },
            },
        }
    ]
}
final_path = save_archive_yaml(archive, archive_path)

# Verify the injected annotation.
check = yaml.safe_load(Path(final_path).read_text())
injected = check["definitions"]["sections"][section_name]["m_annotations"]
trace = injected["plotly_express"][0]
assert trace["x"] == "#field_strength"
assert "A / m" in trace["layout"]["xaxis"]["title"]["text"]
assert "A / m" in trace["layout"]["yaxis"]["title"]["text"]

print(f"Saved:     {hdf_input}")
print(f"Generated: {final_path} (with PlotSection x-y plot annotation)")
