"""Example: structure preview from a CIF file plus an ME collection.

The published Co2Fe2H4 structure
(``examples/input/cif_structure_Co2Fe2H4.cif``,
from the ``MaMMoS_DFT_MC_Atomistic+Spindynamic-calculations_UU`` upload on
the central NOMAD instance) is combined with an EntityCollection of
ontology-backed quantities:

- the .cif is shipped in the upload next to the archive YAML,
- to-nomad parses the structure locally with ASE and embeds it as an
  inline ``run`` section; the standard NOMAD normalizer chain then
  populates the material/optimade results server-side, so the entry
  overview shows a 3-D structure preview (the
  ``ElnWithStructureFile`` base section is deliberately NOT used —
  it fails on nomad-lab 2.0.0 during archive persistence),
- IMPORTANT (workaround): NOMAD does not read the .cif server-side.
  The structure preview comes from the run section that to_nomad
  embedded at generation time. Changing the .cif and re-uploading
  only the .cif does NOT change the preview — regenerate the archive
  with to_nomad(...) so the updated structure is parsed and embedded,
- the entity values live once in the HDF5 file and are referenced from the
  archive YAML (``hdf_reference_mode=True``).

Run with:
    pixi run python examples/from_cif_structure.py
"""

from pathlib import Path

import mammos_entity as me

import to_nomad

out_dir = Path(__file__).parent / "output"
out_dir.mkdir(exist_ok=True)

cif_path = Path(__file__).parent / "input" / "cif_structure_Co2Fe2H4.cif"

# Ontology-backed sample properties stored next to the structure.
# NOTE: the values below are exemplar values for demonstration purposes,
# not the actual calculated values of the source dataset.
properties = me.EntityCollection(
    description="Co2Fe2H4 sample properties (exemplar values)",
    Ms=me.Entity("SpontaneousMagnetization", 1.05e6, "A/m"),
    # MagnetocrystallineAnisotropy is deliberately NOT included: the
    # mammos-entity ontology defines it as a dimensionless (normalized)
    # quantity, so a value in J/m^3 is rejected (mammos-entity
    # constructs entities with plain "" for dimensionless values).
    Tc=me.Entity("CurieTemperature", 673, "K"),
)

h5_path = out_dir / "cif_structure.h5"
yaml_path = out_dir / "cif_structure.archive.yaml"
properties.to_hdf5(h5_path)

to_nomad.to_nomad(
    h5_path,
    yaml_path,
    interactive=False,
    institute="MaMMoS Project",
    owner="Consortium Member",
    lab_id="DEMO-CIF-001",
    name="Co2Fe2H4 Structure Demo",
    description="Structure preview from a CIF file with HDF-referenced entities.",
    # No chemical_formula here: with an inline run section the server-side
    # chain derives the composition from the structure itself. Passing
    # chemical_formula would add the Chemical base section, whose
    # formula-derived composition collides with the system-derived one
    # ("Could not populate compositional data as elements is already
    # defined", logged as ERROR by the results chain, and the entry
    # loses structural_type/dimensionality).
    hdf_reference_mode=True,
    structure_file=cif_path,
)

print(f"CIF:       {cif_path}")
print(f"Saved:     {h5_path}")
print(f"Generated: {yaml_path}")
