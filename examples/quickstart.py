"""Quickstart example: convert a mammos-entity EntityCollection to NOMAD archive YAML.

Run with:
    python examples/quickstart.py
or via pixi:
    pixi run example
"""

from pathlib import Path

import mammos_entity as me

import to_nomad

# ---------------------------------------------------------------------------
# 1. Build a simple EntityCollection with intrinsic magnetic properties
# ---------------------------------------------------------------------------
col = me.EntityCollection(
    description=(
        "Intrinsic magnetic properties of a NdFeB bulk sample measured at "
        "300 K within the MaMMoS project.  "
        "A Jupyter notebook showing how to handle the data can be found next "
        "to the raw data."
    ),
    Ms=me.Ms(31.28e6, "A/m"),
    Hc=me.Hc(875e3, "A/m"),
    Tc=me.Tc(585, "K"),
    K1=me.K1(4.5e6, "J/m^3"),
    A=me.A(7.7e-12, "J/m"),
)

# ---------------------------------------------------------------------------
# 2. Convert to NOMAD archive YAML (non-interactive, all metadata given)
# ---------------------------------------------------------------------------
output_dir = Path(__file__).parent / "output"
output_dir.mkdir(exist_ok=True)

path = to_nomad.to_nomad(
    col,
    output_dir / "NdFeB_intrinsic_properties.archive.yaml",
    interactive=False,  # don't prompt; all metadata supplied below
    name="NdFeB Intrinsic Properties",
    institute="My University / My Institute",
    owner="Jane Doe, John Smith",
    lab_id="MyUni-NdFeB-001",
    description=col.description,
    method="VSM + magnetometry",
    chemical_formula="Nd2Fe14B",
    short_name="NdFeB-bulk-001",
)

# ---------------------------------------------------------------------------
# 3. Inspect the generated file
# ---------------------------------------------------------------------------
print("\n--- Generated archive YAML ---")
print(path.read_text())
