"""to-nomad: convert mammos-entity data to NOMAD archive YAML.

This package adds a NOMAD upload workflow on top of the
`mammos-entity <https://github.com/MaMMoS-project/mammos-entity>`_ library.
Starting from a :class:`~mammos_entity.EntityCollection` (or a single
:class:`~mammos_entity.Entity`) it automatically generates a NOMAD-compatible
``.archive.yaml`` file that includes:

* A **schema definition** (``definitions`` section) with NOMAD quantity
  declarations derived from the ontology labels and units stored in the
  entities.
* A **data section** (``data`` section) with the actual measured / simulated
  values plus standard NOMAD metadata (institute, owner, lab_id, description, …).

Any metadata that is not stored in mammos-entity itself (such as the institute
name or the data owner) is requested interactively when :func:`to_nomad` is
called without those keyword arguments.

Quick-start example
-------------------
::

    import mammos_entity as me
    import to_nomad

    col = me.EntityCollection(
        description="NdFeB sample at room temperature",
        Ms=me.Ms(1.28e6, "A/m"),
        Hc=me.Hc(875e3, "A/m"),
        Tc=me.Tc(585, "K"),
    )

    # Interactive: will prompt for any missing fields (institute, owner, …)
    path = to_nomad.to_nomad(col, "NdFeB_sample.archive.yaml")

    # Non-interactive: all metadata provided up-front
    path = to_nomad.to_nomad(
        col,
        "NdFeB_sample.archive.yaml",
        interactive=False,
        institute="My University",
        owner="Jane Doe",
        lab_id="MyUni-NdFeB-001",
        description=(
            "Intrinsic magnetic properties of a bulk NdFeB sample measured "
            "at 300 K within the MaMMoS project."
        ),
    )
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import TYPE_CHECKING

from to_nomad._io import create_upload_zip, save_archive_yaml
from to_nomad._prompt import collect_metadata
from to_nomad._schema import generate_archive

if TYPE_CHECKING:
    import mammos_entity

__all__ = [
    "to_nomad",
    "save_hdf_and_to_nomad",
    "save_hdf5_and_to_nomad",
    "generate_archive",
    "save_archive_yaml",
    "create_upload_zip",
    "collect_metadata",
]

# Expose sub-modules for power users
from to_nomad import _schema, _prompt, _io  # noqa: E402, F401


def _load_mammos_data_from_path(path: str | Path):
    """Load mammos-entity data from a supported file path.

    Supported formats:
    - MaMMoS YAML: ``.yaml`` / ``.yml`` (via ``mammos_entity.from_yaml``)
    - MaMMoS CSV: ``.csv`` (via ``mammos_entity.from_csv``)
    - HDF: ``.hdf`` / ``.h5`` / ``.hdf5`` (via ``mammos_entity.from_hdf5``)
    """
    import mammos_entity as me  # noqa: PLC0415

    p = Path(path)
    suffix = p.suffix.lower()

    if suffix in {".yaml", ".yml"}:
        return me.from_yaml(p)
    if suffix == ".csv":
        return me.from_csv(p)
    if suffix in {".hdf5", ".h5", ".hdf"}:
        return me.from_hdf5(p)

    raise ValueError(
        f"Unsupported input file suffix '{suffix}' for path {p}. "
        "Supported suffixes: .csv, .yaml, .yml, .hdf5, .h5, .hdf"
    )


def _extract_hdf_metadata(path: str | Path) -> dict:
    """Extract lightweight metadata from an HDF file for embedding in YAML.

    The returned dict contains two keys:
    - ``file_attributes``: mapping of root-level HDF file attributes
    - ``nodes``: list of dicts for groups/datasets with their path, type,
      attributes and dataset shape/dtype where applicable
    """
    import h5py  # noqa: PLC0415

    def _safe(v):
        if isinstance(v, bytes):
            return v.decode("utf-8", errors="replace")
        if hasattr(v, "tolist"):
            return v.tolist()
        if isinstance(v, (str, int, float, bool)) or v is None:
            return v
        return str(v)

    result: dict = {"file_attributes": {}, "nodes": []}
    with h5py.File(path, "r") as f:
        result["file_attributes"] = {k: _safe(v) for k, v in f.attrs.items()}

        def _visitor(name, obj):
            node = {
                "path": f"/{name}" if name else "/",
                "type": "dataset" if isinstance(obj, h5py.Dataset) else "group",
                "attributes": {k: _safe(v) for k, v in obj.attrs.items()},
            }
            if isinstance(obj, h5py.Dataset):
                node["shape"] = list(obj.shape)
                node["dtype"] = str(obj.dtype)
            result["nodes"].append(node)

        f.visititems(_visitor)
    return result


def _hdf_dataset_paths(path: str | Path) -> set[str]:
    """Return all dataset paths in the given HDF file (absolute paths)."""
    import h5py  # noqa: PLC0415

    out: set[str] = set()
    with h5py.File(path, "r") as f:

        def _visitor(name, obj):
            if isinstance(obj, h5py.Dataset):
                out.add(f"/{name}" if name else "/")

        f.visititems(_visitor)
    return out


def _infer_mammos_csv_header_row(
    path: str | Path,
    expected_names: list[str],
) -> int | None:
    """Infer the header row index for MaMMoS CSV files.

    Returns a 0-based line index that contains the expected short labels
    (e.g. ``Ms,T,Hc``), or ``None`` if no reliable match is found.
    """
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except Exception:
        return None

    expected = [name.strip() for name in expected_names if name.strip()]
    if not expected:
        return None

    for idx, line in enumerate(lines):
        # Ignore comments and blank lines while searching.
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = [part.strip() for part in line.split(",")]
        if parts[: len(expected)] == expected and len(parts) >= len(expected):
            return idx
    return None


def _safe_to_nomad_version() -> str:
    """Return installed to-nomad package version, or empty string."""
    try:
        return importlib_metadata.version("to-nomad")
    except importlib_metadata.PackageNotFoundError:
        return ""
    except Exception:
        return ""


def to_nomad(
    data: mammos_entity.EntityCollection | mammos_entity.Entity | str | Path,
    output: str | Path = "output.archive.yaml",
    *,
    interactive: bool = True,
    create_zip: bool = False,
    zip_data_files: list[str | Path] | None = None,
    include_hdf_metadata: bool = False,
    hdf_reference_mode: bool = False,
    file_reference_mode: bool = False,
    hdf_entity_names: list[str] | None = None,
    include_mammos_entities_metadata: bool | None = None,
    include_mammos_entity_version: bool = True,
    include_nomad_generation_metadata: bool = True,
    include_ontology_in_yaml: bool | None = None,
    **metadata: str,
) -> Path:
    """Convert mammos-entity data to a NOMAD-compatible ``.archive.yaml`` file.

    This is the main entry point of the ``to-nomad`` package.  The function:

    1. Collects any metadata that is needed for a meaningful NOMAD entry but
       is not stored inside the entity itself (institute, owner, lab_id,
       description).  Missing fields are solicited via ``input()`` when
       ``interactive=True``.
    2. Calls :func:`to_nomad._schema.generate_archive` to build the NOMAD
       archive dictionary.
    3. Writes the dictionary to *output* using
       :func:`to_nomad._io.save_archive_yaml`.
    4. Optionally bundles the archive YAML and any extra data files into a
       ``.zip`` for manual or API-based NOMAD upload.
     5. Optionally embeds metadata extracted from HDF internals into the
         ``data`` section (when ``include_hdf_metadata=True`` and *data* is an
         HDF path).
      6. Optionally creates HDF-backed quantity mappings using
          ``HDF5Normalizer`` (when ``hdf_reference_mode=True`` and *data* is an
          HDF path), so large arrays are not duplicated inline in YAML.

    Args:
                data:
                        Either:
                        - an :class:`~mammos_entity.EntityCollection`,
                        - a single :class:`~mammos_entity.Entity`, or
                        - a file path to MaMMoS data (`.csv`, `.yaml`, `.yml`, `.hdf`,
                            `.h5`) which is loaded using the corresponding
                            ``mammos_entity.from_*`` function.

        output:
            Destination path for the generated ``.archive.yaml`` file.
            The ``.archive.yaml`` suffix is the NOMAD convention.
            Defaults to ``"output.archive.yaml"`` in the current directory.

        interactive:
            When ``True`` (default), the function prompts the user via
            ``input()`` for any metadata fields that have not been passed as
            keyword arguments.  Set to ``False`` in scripts / notebooks where
            all metadata is provided programmatically.

        create_zip:
            When ``True``, also create a ``.zip`` file containing the archive
            YAML (and any files listed in *zip_data_files*).  The zip is
            placed next to the archive file with the same stem.

        zip_data_files:
            Additional files to include in the zip (e.g. the raw HDF
            measurement file that the archive YAML refers to).

        include_hdf_metadata:
            If ``True`` and *data* is an HDF path, include extracted internal
            HDF metadata in the generated YAML ``data`` section under
            ``hdf_source_path`` and ``hdf_metadata_json``.

        hdf_reference_mode:
            If ``True`` and *data* is an HDF path, configure quantities with
            ``m_annotations.hdf5.path`` and include ``data_file`` in data, while
            omitting inline entity values from the YAML ``data`` section.
        file_reference_mode:
            If ``True`` and *data* is a CSV/YAML path, avoid inlining values in
            YAML ``data`` and instead reference the uploaded source file via
            ``data_file``. For CSV, add tabular parser annotations so NOMAD can
            ingest values from the CSV content directly.
        hdf_entity_names:
            Optional list of top-level entity names to include when input is
            HDF. This allows the HDF file to contain more datasets than shown
            in NOMAD. If omitted, all top-level entities are used.
        include_mammos_entities_metadata:
            Controls whether the explicit ``mammos_entities`` subsection is
            included. In ``hdf_reference_mode`` the default is ``False`` to
            avoid duplication with HDF-stored attributes.
        include_mammos_entity_version:
            If ``True`` (default), include ``mammos_entity_version`` in the
            schema quantities and data block.
        include_nomad_generation_metadata:
            If ``True`` (default), include ``nomad_generation`` subsection with
            conversion provenance (UTC timestamp, source file/format, source and
            runtime mammos-entity versions, to-nomad version).
        include_ontology_in_yaml:
            Controls whether ontology label/IRI are repeated in quantity
            descriptions. In ``hdf_reference_mode`` the default is ``False``.

        **metadata:
            Pre-filled metadata fields.  All keyword arguments are passed
            through to :func:`to_nomad._prompt.collect_metadata` and then to
            :func:`to_nomad._schema.generate_archive`.

            Supported keys
            ~~~~~~~~~~~~~~
            ``name``
                Human-readable schema / entry name
                (default: ``"MaMMoS Data"``).
            ``section_name``
                Python identifier for the NOMAD section class.
                Derived from *name* automatically if omitted.
            ``institute``
                Name of the institute / organization (**required** for a
                complete NOMAD entry).
            ``owner``
                Data owner / contact person, comma-separated if multiple
                (**required**).
            ``lab_id``
                Lab or dataset identifier (**required**).
            ``description``
                Long description of the dataset (**required**).  Falls back
                to the ``description`` attribute of the EntityCollection.
            ``method``
                Measurement or simulation method (optional).
            ``short_name``
                Short name or label for the sample (optional).
            ``chemical_formula``
                Chemical formula of the sample, e.g. ``"Nd2Fe14B"``
                (optional; enables the NOMAD Chemical base section).
            ``default_entry_name``
                Default value for the NOMAD ``name`` field
                (default: ``"MaMMoS Data"``).

    Returns:
        The resolved path of the generated ``.archive.yaml`` file.

    Examples:
        Basic interactive usage::

            import mammos_entity as me
            import to_nomad

            col = me.EntityCollection(
                description="NdFeB sample at 300 K",
                Ms=me.Ms(1.28e6, "A/m"),
                Hc=me.Hc(875e3, "A/m"),
                Tc=me.Tc(585, "K"),
            )
            path = to_nomad.to_nomad(col, "NdFeB_sample.archive.yaml")

        Non-interactive with zip creation::

            path = to_nomad.to_nomad(
                col,
                "NdFeB_sample.archive.yaml",
                interactive=False,
                create_zip=True,
                zip_data_files=["raw_measurement.hdf"],
                institute="My University",
                owner="Jane Doe",
                lab_id="MyUni-NdFeB-001",
                description="NdFeB sample at room temperature.",
                method="VSM",
                chemical_formula="Nd2Fe14B",
            )

        Single entity::

            Ms = me.Ms(1.28e6, "A/m")
            path = to_nomad.to_nomad(
                Ms,
                "Ms_value.archive.yaml",
                interactive=False,
                institute="My Institute",
                owner="John Smith",
                lab_id="MI-Ms-001",
            )
    """
    output = Path(output)
    normalizer_suffixes = {".h5", ".hdf5", ".he5", ".h5part", ".nxs", ".mat", ".nc4"}

    # Retrieve the collection description for seeding the 'description' prompt
    import mammos_entity as me  # noqa: PLC0415

    source_path: Path | None = None
    source_suffix = ""
    if isinstance(data, (str, Path)):
        source_path = Path(data)
        source_suffix = source_path.suffix.lower()
        data = _load_mammos_data_from_path(data)

    if isinstance(data, me.EntityCollection):
        collection_description = data.description
    else:
        collection_description = getattr(data, "description", "")

    # Optional filtering for HDF inputs: include only selected top-level keys.
    if (
        hdf_entity_names is not None
        and source_path
        and source_suffix in {".hdf5", ".h5", ".hdf"}
    ):
        if not isinstance(data, me.EntityCollection):
            raise ValueError("hdf_entity_names can only be used for HDF collections.")
        missing = [name for name in hdf_entity_names if name not in data]
        if missing:
            available = [name for name, _ in data]
            raise ValueError(
                "Requested hdf_entity_names not found: "
                f"{missing}. Available top-level entities: {available}"
            )
        filtered = me.EntityCollection(description=data.description)
        for name in hdf_entity_names:
            filtered[name] = data[name]
        data = filtered

    # Collect / complete metadata
    meta = collect_metadata(
        collection_description=collection_description,
        interactive=interactive,
        **{k: v for k, v in metadata.items() if isinstance(v, str)},
    )

    # Build the archive dictionary.
    # 'section_name' is not collected via collect_metadata (it is an advanced
    # option); retrieve it directly from the original metadata kwargs so that
    # generate_archive can derive a sensible default from 'name'.
    schema_kwargs: dict = {
        k: meta.get(k, "")
        for k in (
            "name",
            "institute",
            "owner",
            "lab_id",
            "description",
            "method",
            "short_name",
            "chemical_formula",
            "default_entry_name",
        )
    }
    # Pass section_name only if explicitly provided (not empty), so that
    # generate_archive derives it from 'name' automatically.
    if metadata.get("section_name"):
        schema_kwargs["section_name"] = metadata["section_name"]
    extra_quantities: dict[str, dict] = {}
    extra_data: dict[str, str] = {}
    extra_base_sections: list[str] = []
    include_entity_values = True
    hdf_meta: dict | None = None
    source_mammos_entity_version = ""

    runtime_mammos_entity_version = ""
    if include_nomad_generation_metadata:
        runtime_mammos_entity_version = getattr(me, "__version__", "") or ""

    if source_path and source_suffix in {".hdf5", ".h5", ".hdf"}:
        # Read once and reuse for metadata embedding and top-level overrides.
        hdf_meta = _extract_hdf_metadata(source_path)
        file_attrs = (
            hdf_meta.get("file_attributes", {}) if isinstance(hdf_meta, dict) else {}
        )

        # Prefer the metadata that is truly stored in the HDF file.
        # This avoids reporting the converter package version when the source
        # file carries its own mammos_entity_version attribute.
        if isinstance(file_attrs.get("mammos_entity_version"), str):
            source_mammos_entity_version = file_attrs["mammos_entity_version"]
            if include_mammos_entity_version:
                extra_data["mammos_entity_version"] = file_attrs[
                    "mammos_entity_version"
                ]

        # If the caller did not provide description explicitly and no collection
        # description was recovered, use the HDF root description attribute.
        if not schema_kwargs.get("description") and isinstance(
            file_attrs.get("description"), str
        ):
            schema_kwargs["description"] = file_attrs["description"]

    if hdf_reference_mode and source_path and source_suffix in {".hdf5", ".h5", ".hdf"}:
        if source_suffix not in normalizer_suffixes:
            raise ValueError(
                "hdf_reference_mode requires a NOMAD HDF5Normalizer-supported file "
                f"suffix, got '{source_suffix}'. Use one of "
                f"{sorted(normalizer_suffixes)} (e.g. rename to '.h5')."
            )
        include_entity_values = False
        extra_base_sections.append(
            "nomad.datamodel.metainfo.basesections.HDF5Normalizer"
        )

        # Required by HDF5Normalizer to point to the uploaded HDF file.
        extra_quantities["data_file"] = {
            "type": "str",
            "description": "Path to the uploaded HDF file used as data source.",
            "m_annotations": {"eln": {"component": "FileEditQuantity"}},
        }
        # Use the file name so it resolves inside NOMAD upload context.
        extra_data["data_file"] = source_path.name

        dataset_paths = _hdf_dataset_paths(source_path)
        dataset_attrs_by_path: dict[str, dict] = {}
        if isinstance(hdf_meta, dict) and isinstance(hdf_meta.get("nodes"), list):
            for node in hdf_meta["nodes"]:
                if not isinstance(node, dict):
                    continue
                if node.get("type") != "dataset":
                    continue
                path = node.get("path")
                attrs = node.get("attributes")
                if isinstance(path, str) and isinstance(attrs, dict):
                    dataset_attrs_by_path[path] = attrs

        def _set_hdf_path_for_quantity(qname: str) -> None:
            path_candidate = f"/{qname}"
            if path_candidate in dataset_paths:
                qdef = extra_quantities.get(qname)
                if qdef is None:
                    qdef = {}
                anns = qdef.get("m_annotations", {})
                anns["hdf5"] = {"path": path_candidate}
                qdef["m_annotations"] = anns

                # Prefer ontology metadata directly from HDF dataset attributes.
                attrs = dataset_attrs_by_path.get(path_candidate, {})
                if isinstance(attrs, dict):
                    desc_parts: list[str] = []
                    raw_desc = attrs.get("description")
                    if isinstance(raw_desc, str) and raw_desc.strip():
                        desc_parts.append(raw_desc.strip())
                    raw_label = attrs.get("ontology_label")
                    if isinstance(raw_label, str) and raw_label.strip():
                        desc_parts.append(f"ontology: {raw_label.strip()}")
                    raw_iri = attrs.get("ontology_iri")
                    if isinstance(raw_iri, str) and raw_iri.strip():
                        desc_parts.append(f"IRI: {raw_iri.strip()}")
                    if desc_parts:
                        qdef["description"] = " | ".join(desc_parts)

                extra_quantities[qname] = qdef

        # Build annotations for all collection-derived quantity names
        if isinstance(data, me.EntityCollection):
            for ename, entity_like in data:
                if isinstance(entity_like, me.EntityCollection):
                    for sub_name, sub_entity in entity_like:
                        if isinstance(sub_entity, me.EntityCollection):
                            continue
                        _set_hdf_path_for_quantity(f"{ename}__{sub_name}")
                else:
                    _set_hdf_path_for_quantity(ename)
        elif isinstance(data, me.Entity):
            _set_hdf_path_for_quantity(data.ontology_label)

    if (
        file_reference_mode
        and source_path
        and source_suffix in {".csv", ".yaml", ".yml"}
    ):
        # CSV can be parsed by NOMAD tabular annotations, so values do not need
        # to be inlined. YAML has no equivalent built-in parser mapping here,
        # therefore keep inline values to avoid unresolved (grayed out) fields.
        include_entity_values = source_suffix in {".yaml", ".yml"}
        extra_quantities["data_file"] = {
            "type": "str",
            "description": "Path to the uploaded source data file.",
            "m_annotations": {"eln": {"component": "FileEditQuantity"}},
        }
        extra_data["data_file"] = source_path.name

        # For CSV we can map quantities directly from file columns.
        if source_suffix == ".csv":
            extra_base_sections.append("nomad.parsing.tabular.TableData")

            quantity_names: list[str] = []
            if isinstance(data, me.EntityCollection):
                for ename, entity_like in data:
                    if isinstance(entity_like, me.EntityCollection):
                        for sub_name, sub_entity in entity_like:
                            if isinstance(sub_entity, me.EntityCollection):
                                continue
                            quantity_names.append(f"{ename}__{sub_name}")
                    else:
                        quantity_names.append(ename)
            elif isinstance(data, me.Entity):
                quantity_names.append(data.ontology_label)

            header_row = _infer_mammos_csv_header_row(source_path, quantity_names)

            data_file_annotations: dict = extra_quantities["data_file"].setdefault(
                "m_annotations", {}
            )
            tabular_parser: dict = {}
            if header_row is not None:
                tabular_parser["parsing_options"] = {"skiprows": header_row}
            else:
                tabular_parser["parsing_options"] = {"comment": "#"}
            data_file_annotations["tabular_parser"] = tabular_parser

            for qname in quantity_names:
                qdef = extra_quantities.get(qname, {})
                anns = qdef.get("m_annotations", {})
                anns["tabular"] = {"name": qname}
                qdef["m_annotations"] = anns
                extra_quantities[qname] = qdef

    if include_mammos_entities_metadata is None:
        include_mammos_entities_metadata = not hdf_reference_mode
    if include_ontology_in_yaml is None:
        include_ontology_in_yaml = not hdf_reference_mode

    if include_hdf_metadata and hdf_meta is not None:
        # Keep only NOMAD-portable metadata fields in reference mode.
        # Absolute source paths from local machines are not valid on NOMAD workers.
        if not hdf_reference_mode:
            extra_quantities["hdf_source_path"] = {
                "type": "str",
                "description": "Source HDF file path used for conversion.",
            }
            extra_data["hdf_source_path"] = str(source_path)

        # Avoid duplicating metadata already promoted to top-level fields.
        hdf_meta_for_json = dict(hdf_meta)
        file_attrs_json = dict(hdf_meta_for_json.get("file_attributes", {}))
        file_attrs_json.pop("description", None)
        file_attrs_json.pop("mammos_entity_version", None)
        if file_attrs_json:
            hdf_meta_for_json["file_attributes"] = file_attrs_json
        else:
            hdf_meta_for_json.pop("file_attributes", None)

        # In HDF reference mode, keep JSON structural to avoid repeating
        # ontology/unit metadata that is already available in the HDF datasets.
        if hdf_reference_mode and isinstance(hdf_meta_for_json.get("nodes"), list):
            cleaned_nodes = []
            allowed_paths: set[str] | None = None
            if hdf_entity_names:
                allowed_paths = {f"/{name}" for name in hdf_entity_names}
            for node in hdf_meta_for_json["nodes"]:
                if not isinstance(node, dict):
                    continue
                node_copy = dict(node)
                if (
                    allowed_paths is not None
                    and node_copy.get("path") not in allowed_paths
                ):
                    continue
                attrs = dict(node_copy.get("attributes", {}))
                for k in (
                    "ontology_iri",
                    "ontology_label",
                    "unit",
                    "description",
                    "mammos_entity_version",
                ):
                    attrs.pop(k, None)
                if attrs:
                    node_copy["attributes"] = attrs
                else:
                    node_copy.pop("attributes", None)
                cleaned_nodes.append(node_copy)
            hdf_meta_for_json["nodes"] = cleaned_nodes

        extra_quantities["hdf_metadata_json"] = {
            "type": "str",
            "description": "JSON dump of extracted HDF internal metadata (without duplicated top-level fields).",
        }
        extra_data["hdf_metadata_json"] = json.dumps(
            hdf_meta_for_json, ensure_ascii=False
        )

    archive = generate_archive(
        data,
        extra_quantities=extra_quantities or None,
        extra_data=extra_data or None,
        extra_base_sections=extra_base_sections or None,
        include_entity_values=include_entity_values,
        include_mammos_entities_metadata=include_mammos_entities_metadata,
        include_mammos_entity_version=include_mammos_entity_version,
        include_nomad_generation_metadata=include_nomad_generation_metadata,
        nomad_generation_metadata={
            "created_datetime_utc": datetime.now(timezone.utc).isoformat(),
            "source_file": source_path.name if source_path else "",
            "source_format": source_suffix.lstrip(".") if source_suffix else "",
            "source_mammos_entity_version": source_mammos_entity_version,
            "runtime_mammos_entity_version": runtime_mammos_entity_version,
            "to_nomad_version": _safe_to_nomad_version(),
        },
        include_ontology_in_yaml=include_ontology_in_yaml,
        **schema_kwargs,
    )

    # Write to file
    out_path = save_archive_yaml(archive, output)
    print(f"Generated NOMAD archive: {out_path}")

    # Optionally create upload zip
    if create_zip:
        # Strip '.archive.yaml' or '.yaml' extension for the zip stem
        stem = out_path.name
        for suffix in (".archive.yaml", ".yaml"):
            if stem.endswith(suffix):
                stem = stem[: -len(suffix)]
                break
        zip_path = out_path.parent / f"{stem}.zip"

        files_to_zip: list[Path] = [out_path]
        if zip_data_files:
            files_to_zip.extend(Path(f) for f in zip_data_files)

        create_upload_zip(*files_to_zip, output_path=zip_path)
        print(f"Upload zip created:      {zip_path}")

    return out_path


def save_hdf_and_to_nomad(
    data: mammos_entity.EntityCollection | mammos_entity.Entity,
    hdf_path: str | Path,
    output: str | Path,
    *,
    interactive: bool = True,
    create_zip: bool = False,
    zip_data_files: list[str | Path] | None = None,
    hdf_group_name: str | None = None,
    **metadata: str,
) -> tuple[Path, Path]:
    """Save mammos data as HDF and generate a NOMAD archive YAML from it.

    This helper is useful when users want a file-based workflow:
    1. Persist an in-memory EntityCollection/Entity as `.hdf`
    2. Create the NOMAD `.archive.yaml` from that HDF file

    Args:
        data:
            An :class:`~mammos_entity.EntityCollection` or a single
            :class:`~mammos_entity.Entity`.
        hdf_path:
            Output path of the HDF file to be written.
        output:
            Output path of the NOMAD archive YAML.
        interactive:
            Forwarded to :func:`to_nomad`.
        create_zip:
            Forwarded to :func:`to_nomad`.
        zip_data_files:
            Forwarded to :func:`to_nomad`.
        hdf_group_name:
            Optional top-level group name when saving an EntityCollection.
            If omitted, entities are written at the root level.
        **metadata:
            Forwarded to :func:`to_nomad`.

    Returns:
        ``(hdf_path, yaml_path)`` as resolved absolute paths.
    """
    import mammos_entity as me  # noqa: PLC0415

    hdf_path = Path(hdf_path)
    hdf_path.parent.mkdir(parents=True, exist_ok=True)

    if isinstance(data, me.EntityCollection):
        data.to_hdf5(hdf_path, name=hdf_group_name)
    elif isinstance(data, me.Entity):
        dset_name = hdf_group_name or data.ontology_label or "entity"
        data.to_hdf5(hdf_path, name=dset_name)
    else:
        raise TypeError(
            "data must be a mammos_entity.EntityCollection or mammos_entity.Entity, "
            f"got {type(data).__name__}."
        )

    yaml_path = to_nomad(
        hdf_path,
        output,
        interactive=interactive,
        create_zip=create_zip,
        zip_data_files=zip_data_files,
        **metadata,
    )
    return hdf_path.resolve(), yaml_path


def save_hdf5_and_to_nomad(
    data: mammos_entity.EntityCollection | mammos_entity.Entity,
    hdf5_path: str | Path,
    output: str | Path,
    *,
    interactive: bool = True,
    create_zip: bool = False,
    zip_data_files: list[str | Path] | None = None,
    hdf5_group_name: str | None = None,
    **metadata: str,
) -> tuple[Path, Path]:
    """Backward-compatible alias for :func:`save_hdf_and_to_nomad`.

    Prefer using :func:`save_hdf_and_to_nomad` in new code.
    """
    return save_hdf_and_to_nomad(
        data,
        hdf5_path,
        output,
        interactive=interactive,
        create_zip=create_zip,
        zip_data_files=zip_data_files,
        hdf_group_name=hdf5_group_name,
        **metadata,
    )
