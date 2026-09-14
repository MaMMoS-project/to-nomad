# to-nomad

Convert [mammos-entity](https://github.com/MaMMoS-project/mammos-entity) data to
[NOMAD](https://nomad-lab.eu/)-compatible upload archives.
See also https://arxiv.org/abs/2609.11464 .

## Overview

`to-nomad` is an add-on for the `mammos-entity` library.  Given a
`mammos_entity.EntityCollection` (or a single `Entity`) it automatically:

1. **Generates a NOMAD archive YAML** – the `definitions` section (schema) is
   derived from the ontology labels, IRIs, and units stored in the entities;
   the `data` section contains the actual values together with standard NOMAD
   metadata fields.
2. **Prompts for missing metadata** – fields that are needed for a meaningful
   NOMAD entry (institute, owner, lab_id, description) but are not stored
   inside the entity are requested interactively when not supplied
   programmatically.
3. **Creates a zip for upload** – optionally bundles the archive YAML together
   with raw data files (HDF, CSV, ...) into a `.zip` ready for manual or
   API-based NOMAD upload.
4. **Reads MaMMoS files directly** – you can pass a `.csv`, `.yaml`/`.yml`,
   or `.hdf`/`.h5`/`.hdf5` path directly to `to_nomad.to_nomad(...)`; internally it
   uses the corresponding `mammos-entity` file readers.
5. **Stores generation provenance explicitly** – each generated archive includes
  a `nomad_generation` subsection with conversion metadata, and can also
  include a `mammos_entities` subsection with per-quantity metadata (`name`,
  `ontology_label`, `ontology_iri`, `unit`, `description`, `source_type`).

## Installation

```bash
# with pixi (recommended)
pixi install
pixi run install    # installs the local package in editable mode

# or plain pip inside the pixi shell
pip install -e .
```

## Quick start

```python
import mammos_entity as me
import to_nomad

# Build your data collection (or load from file with mammos-entity readers)
col = me.EntityCollection(
    description="NdFeB bulk sample at room temperature",
    Ms=me.Ms(1.28e6, "A/m"),
    Hc=me.Hc(875e3, "A/m"),
    Tc=me.Tc(585, "K"),
    K1=me.K1(4.5e6, "J/m^3"),
    A=me.A(7.7e-12, "J/m"),
)

# Non-interactive: provide all metadata upfront
path = to_nomad.to_nomad(
    col,
    "NdFeB_sample.archive.yaml",
    interactive=False,
    name="NdFeB Intrinsic Properties",
    institute="My University",
    owner="Jane Doe",
    lab_id="MyUni-NdFeB-001",
    description="Intrinsic properties of a NdFeB bulk sample within MaMMoS.",
    method="VSM",
    chemical_formula="Nd2Fe14B",
    elemental_composition=[
      {"element": "Nd", "atomic_fraction": 2 / 17},
      {"element": "Fe", "atomic_fraction": 14 / 17},
      {"element": "B", "atomic_fraction": 1 / 17},
    ],
)

# Interactive: omit metadata fields and the user will be asked for them
path = to_nomad.to_nomad(col, "NdFeB_sample.archive.yaml")

# Directly from a MaMMoS file created with mammos-entity
path = to_nomad.to_nomad(
  "example.yaml",  # or example.csv / example.hdf
  "example_from_file.archive.yaml",
  interactive=False,
  file_reference_mode=True,
  institute="My University",
  owner="Jane Doe",
  lab_id="MyUni-001",
  description="Converted from a MaMMoS file.",
)

# Optional: embed metadata extracted from inside the HDF file
path = to_nomad.to_nomad(
  "example.h5",
  "example_from_hdf.archive.yaml",
  interactive=False,
  hdf_reference_mode=True,
  include_hdf_metadata=True,
  hdf_entity_names=["Ms", "T"],
  institute="My University",
  owner="Jane Doe",
  lab_id="MyUni-001",
  description="Converted from HDF with embedded metadata.",
)

# Save an in-memory collection as HDF and immediately build the NOMAD YAML
hdf_path, yaml_path = to_nomad.save_hdf_and_to_nomad(
  col,
  "example_data.h5",
  "example_from_hdf.archive.yaml",
  interactive=False,
  institute="My University",
  owner="Jane Doe",
  lab_id="MyUni-001",
  description="Converted from HDF generated via mammos-entity.",
)
```

Run the ready-made quickstart example:

```bash
pixi run example
```

The generated YAML follows the structure used by the MaMMoS partners – see the
[nomad](https://github.com/MaMMoS-project/nomad) upload examples for reference.

## Generated archive YAML structure

```yaml
definitions:
  name: NdFeB Intrinsic Properties
  sections:
    NdFeB_Intrinsic_Properties:
      base_sections:
        - nomad.datamodel.metainfo.eln.Chemical
        - nomad.datamodel.data.EntryData
      quantities:
        name: {type: str, default: MaMMoS Data}
        description: {type: str}
        lab_id: {type: str}
        short_name: {type: str}
        owner: {type: str}
        Ms:
          type: np.float64
          unit: A / m
          description: 'ontology: SpontaneousMagnetization | IRI: …'
        …

data:
  m_def: NdFeB_Intrinsic_Properties
  institute: My University
  lab_id: MyUni-NdFeB-001
  owner: Jane Doe
  chemical_formula: Nd2Fe14B
  description: Intrinsic properties of a NdFeB bulk sample …
  Ms: 1280000.0
  Hc: 875000.0
  Tc: 585.0
  …
```

## API

| Function / class | Description |
|---|---|
| `to_nomad.to_nomad(data, output, ...)` | Main entry point. Accepts a collection or single entity, writes the `.archive.yaml`, optionally creates a zip. |
| `to_nomad.save_hdf_and_to_nomad(data, hdf_path, output, ...)` | Convenience helper: writes `.hdf` from entities and then creates `.archive.yaml` from that file. |
| `to_nomad.generate_archive(data, ...)` | Low-level: returns the archive as a Python dict (no file I/O). |
| `to_nomad.save_archive_yaml(archive, path)` | Write an archive dict to file. |
| `to_nomad.create_upload_zip(*files, output_path)` | Bundle files into a NOMAD upload zip. |
| `to_nomad.collect_metadata(...)` | Interactive or headless metadata collection. |

When `data` is an HDF path, `to_nomad(..., include_hdf_metadata=True)` adds
`hdf_source_path` and `hdf_metadata_json` to the YAML `data` section.

By default, `to_nomad(...)` now writes a dedicated `nomad_generation`
subsection with conversion provenance, including:
- `created_datetime_utc`
- `source_file` and `source_format`
- `source_mammos_entity_version` (from input file attrs, when available)
- `runtime_mammos_entity_version`
- `to_nomad_version`

Set `include_nomad_generation_metadata=False` to disable this subsection.
Set `include_mammos_entity_version=True` only if you still want the older
top-level `mammos_entity_version` field in addition to `nomad_generation`.

Optional chemical composition metadata can be provided with:
- `chemical_formula="Nd2Fe14B"`
- `elemental_composition=[{"element": "Nd", "atomic_fraction": 0.1176}, ...]`

When `data` is a CSV/YAML path, `to_nomad(..., file_reference_mode=True)`
stores `data_file` and avoids inlining entity values into YAML `data`.
For CSV, tabular annotations are added so NOMAD reads column data directly from
the uploaded file.

When `data` is an HDF path, `to_nomad(..., hdf_reference_mode=True)` uses
`HDF5Normalizer` annotations and writes `data_file` in YAML instead of inlining
large numeric arrays in the `data` section.

Use `hdf_entity_names=[...]` to select exactly which top-level datasets/entities
from the HDF file should appear in NOMAD definitions/data. This allows your HDF
file to contain more data than shown in the NOMAD overview.

In `hdf_reference_mode`, duplicated ontology metadata is minimized by default:
- no explicit `mammos_entities` subsection
- no ontology IRI text repeated in quantity descriptions
- HDF metadata JSON is structural (paths/shapes/dtypes)

Important: In `hdf_reference_mode`, upload the `.archive.yaml` together with
the referenced HDF file (same upload/zip), otherwise NOMAD cannot resolve
`data_file`.

Note: NOMAD `HDF5Normalizer` supports extensions like `.h5` and `.hdf5` (not
`.hdf`). If you use `hdf_reference_mode=True`, prefer `.h5`/`.hdf5` filenames.

## Examples

- [examples/quickstart.py](examples/quickstart.py) – basic non-interactive usage.
- More examples are in [examples/output/](examples/output/) after running `pixi run example`.

## Acknowledgements

This software has been developed as part of the
[MaMMoS](https://mammos-project.github.io/) project (EU Horizon Europe grant
No. 101135546).

