# to-nomad

This repository provides a working demonstrator (March 2026) showing how data represented with [mammos-entity](https://github.com/MaMMoS-project/mammos-entity) can be transformed into [NOMAD](https://nomad-lab.eu/)-compatible upload archives . It was developed primarily as a reference implementation and demonstration of how the mammos-entity data model can be used to generate well-documented NOMAD uploads enriched with ontology-based metadata and semantic labels.

The code is intended to illustrate the workflow and concepts presented in the MaMMoS project, while also serving as a functional example that users can adapt and extend for their own applications.

See the mammos-entity documentation and examples: https://mammos-project.github.io/mammos/examples/mammos-entity/index.html

For further information on the ontology and its use-case with mammos-entity see also https://arxiv.org/abs/2609.11464 .

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

## Terminology: two kinds of YAML

This package deals with two distinct YAML formats — do not confuse them:

| | NOMAD archive YAML | mammos-entity collection YAML |
|---|---|---|
| Typical filename | `*.archive.yaml` | `*.yaml` / `*.yml` |
| Role | Upload artifact for NOMAD: `definitions` (schema) + `data` (entry values). Uploaded in parallel to the raw data files, but can hold values inline. | MaMMoS *data file* written by `EntityCollection.to_yaml` and read with `mammos_entity.from_yaml`. An **input** to `to-nomad`, never a NOMAD artifact. |
| Created by | `to_nomad.to_nomad(...)` | `mammos_entity` itself |

**NOMAD upload package composition.** A NOMAD upload consists of the
`*.archive.yaml` plus its raw data files. With `hdf_reference_mode=True`
(the `HDF5Normalizer` workflow), the data file is always an HDF file
(`.h5`/`.hdf5`) written by `EntityCollection.to_hdf5` — never a
mammos-entity collection YAML data file. A `*.yaml` written by
`EntityCollection.to_yaml` is an intermediate input to
`to_nomad.to_nomad(...)` only: it cannot be uploaded as the data file next
to an `.archive.yaml`.

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

## Name and Unit Normalization (MaMMoS / Astropy → NOMAD / Pint)

NOMAD uses strict Metainfo validation and Pint-based unit parsing. `to-nomad` automatically handles identifier sanitization and unit translation to guarantee upload compatibility:

### 1. Identifier Sanitization (NOMAD Metainfo Compatibility)
NOMAD Metainfo requires section and quantity definition keys to be valid Python identifiers matching `^[a-zA-Z_][a-zA-Z0-9_]*$`. When transforming arbitrary collection keys or column headers (e.g. from experimental CSV/HDF datasets), `to-nomad` automatically normalizes names:
- `/` is translated to `_per_` (e.g. `Hc_A/m_gb1nm` → `Hc_A_per_m_gb1nm`, `A_J/m` → `A_J_per_m`)
- `%` is translated to `_pct_` (e.g. `Rwp_%ESRF` → `Rwp_pct_ESRF`)
- `.`, `^`, `-`, spaces, and special symbols are replaced by `_` (e.g. `Js_gb_0.05` → `Js_gb_0_05`, `K_1_J/m^3` → `K_1_J_per_m_3`)
- Leading digits are prefixed with `_`
- Consecutive underscores are collapsed and trimmed

> **Traceability**: The original entity/column name is always preserved in the `mammos_entities` metadata section under `name`, with `value_key` pointing to the sanitized schema identifier in `data` and `definitions`.

### 2. Unit Translation (Astropy Units → Pint / NOMAD)
`mammos-entity` utilizes Astropy Units (`astropy.units`), whereas NOMAD uses Pint (`pint`) for unit definition and validation. `to-nomad` bridges the syntax differences automatically:
- **Temperature aliases**: Astropy's `deg_C`, `deg_F`, `deg_R` are mapped to Pint's `degC`, `degF`, `degR`.
- **Implicit exponents**: Exponents without carets (e.g. `m3`, `cm-2`, `s+1`, `Am2/kg`) are converted to explicit exponents (e.g. `m^3`, `cm^-2`, `s^1`, `A m^2 / kg`).
- **Casing & Symbol mapping**: `Angstrom` → `angstrom`, `micron` → `micrometer`, `amu` → `unified_atomic_mass_unit`.
- **Division spacing**: Normalized to consistent ` / ` syntax (e.g. `J / (kg * K)`).

### 3. CSV Column Naming for HDF5 Reference Mode
When using `hdf_reference_mode=True`, column names from CSV files are used as HDF5 dataset names.
Column names containing certain characters (notably `/`) create nested HDF5 group structures that are
incompatible with NOMAD's HDF5Normalizer. To prevent this:

**Prevent nested groups by avoiding `/` in CSV column names.** The characters `/`, `%`, `.`, `^`, `-`,
spaces, and other special symbols are automatically sanitized in the generated NOMAD archive,
but this sanitization happens *after* the HDF5 file is created, causing a mismatch between
HDF5 dataset paths and quantity names.

**Recommended practice for CSV files:**
- Use only letters, digits, and underscores in column names
- Replace `/` with `_per_` (e.g., `A_J/m` → `A_J_per_m`)
- Replace `%` with `_pct_` (e.g., `Rwp_%` → `Rwp_pct_`)
- Replace other special characters with `_`
- Prefix leading digits with `_`

**Sanitization is optional:** If your CSV column names already follow these rules,
sanitization is not needed. The `prepare_csv_for_nomad()` function and its CLI script
provide an optional `--no-sanitize` flag to copy CSV files without modification.

**Helper script:** The `prepare_csv_for_nomad` function is available in the to-nomad package:

```python
from to_nomad import prepare_csv_for_nomad
prepare_csv_for_nomad("input.csv", "output.csv")  # With sanitization (default)
prepare_csv_for_nomad("input.csv", "output.csv", sanitize=False)  # Without sanitization
```

Or via CLI:
```bash
# With sanitization (default):
python -m to_nomad.prepare_csv_for_nomad input.csv output.csv

# Without sanitization:
python -m to_nomad.prepare_csv_for_nomad input.csv output.csv --no-sanitize
```

Note: For simple cases, you can also load the CSV with `mammos_entity.from_csv()`,
then use entity names directly (programmatic entities don't have special characters).

## Nested EntityCollections

**Creating nested collections** is plain Python — no file is involved:

```python
sub = me.EntityCollection(description="Intrinsic properties", Ms=..., ...)
sample = me.EntityCollection(description="Sample", intrinsic=sub)
```

**Saving and loading nested data** (the *data-file* level, independent of NOMAD):

| Format | Nested sub-collections | Reader |
|---|---|---|
| HDF5 (`.h5`) | Yes — nested groups | `me.from_hdf5` |
| MaMMoS YAML (`.yaml`) | Yes — recursive collection nodes (v2 format) | `me.from_yaml` |
| CSV (`.csv`) | No — flat, single table | `me.from_csv` |

**In the NOMAD archive YAML** nested collections become sub-sections
(`definitions`) and nested dictionaries (`data`).

**Value storage in the NOMAD archive YAML:**

- Inline mode (default): entity values are written into the `data` section.
- `hdf_reference_mode=True`: the input *must* be an HDF file path, because
  NOMAD's `HDF5Normalizer` reads the uploaded `.h5` file. Every quantity —
  entity or plain value, at any nesting depth — is annotated with
  `m_annotations.hdf5.path` pointing to its HDF5 dataset, and values are
  omitted from the archive. Plain values inside sub-collections are
  additionally kept inline. Upload the archive YAML together with the `.h5`
  file (see also the `hdf_reference_mode` notes in the API section).

See `examples/from_nested_collection.py` for a runnable demonstration.

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

