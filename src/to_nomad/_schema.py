"""Generate NOMAD archive YAML dictionaries from mammos-entity data.

The NOMAD archive YAML format used here has two top-level sections:

- ``definitions``: the schema definition (section class, quantities with types /
  units / descriptions).
- ``data``: the actual data values together with standard metadata fields
  (institute, owner, lab_id, description, …).

Both sections are derived automatically from an
:class:`~mammos_entity.EntityCollection` or a single
:class:`~mammos_entity.Entity`.  Missing metadata that is required for a
meaningful NOMAD entry (institute, owner, lab_id, description) can be supplied
via keyword arguments or collected interactively via
:func:`to_nomad._prompt.collect_metadata`.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    import mammos_entity


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _section_name_from(name: str) -> str:
    """Derive a valid Python identifier from a human-readable schema name."""
    s = re.sub(r"[^a-zA-Z0-9]", "_", name)
    s = re.sub(r"_+", "_", s).strip("_")
    if s and s[0].isdigit():
        s = "_" + s
    return s or "MaMMoSData"


def _nomad_type(value: Any) -> str:
    """Return the NOMAD type string for a scalar-or-array value."""
    try:
        arr = np.asanyarray(value)
        if np.issubdtype(arr.dtype, np.integer):
            return "int"
        if np.issubdtype(arr.dtype, np.floating) or np.issubdtype(
            arr.dtype, np.complexfloating
        ):
            return "np.float64"
        # strings / objects
        return "str"
    except Exception:
        return "str"


def _unit_str(entity_like: Any) -> str | None:
    """Return the unit string of an entity-like, or None if dimensionless."""
    unit = getattr(entity_like, "unit", None)
    if unit is None:
        return None
    s = _normalize_unit_for_nomad(str(unit))
    return s if s else None


def _normalize_unit_for_nomad(unit_str: str) -> str:
    """Convert Astropy-style unit strings to NOMAD/Pint compatible notation.

    Astropy may render powers as implicit suffixes (e.g. ``m3`` or ``m-2``),
    while Pint in NOMAD expects explicit exponents (e.g. ``m^3`` or ``m^-2``).
    """
    # Convert tokens like `m3`, `cm-2`, `s+1` to `m^3`, `cm^-2`, `s^1`.
    normalized = re.sub(r"\b([A-Za-z]+)([+-]?\d+)\b", r"\1^\2", unit_str)
    # Keep a single consistent spacing around division signs.
    normalized = re.sub(r"\s*/\s*", " / ", normalized)
    return normalized.strip()


def _is_array(value: Any) -> bool:
    """Return True for array-valued entities (more than one element)."""
    if isinstance(value, str):
        return False
    try:
        arr = np.asanyarray(value)
        return arr.ndim > 0 and arr.size > 1
    except Exception:
        return False


def _to_serializable(value: Any) -> Any:
    """Convert numpy scalars / arrays to plain Python objects for YAML."""
    try:
        arr = np.asanyarray(value)
        if arr.ndim == 0:
            return arr.item()
        return arr.tolist()
    except Exception:
        return value


def _quantity_def(
    name: str,
    entity_like: Any,
    *,
    include_ontology_context: bool = True,
) -> dict:
    """Build a single NOMAD quantity definition dict for one entity-like."""
    # Import here to keep the module importable even without mammos_entity
    import mammos_entity as me  # noqa: PLC0415

    q: dict[str, Any] = {}

    if isinstance(entity_like, me.Entity):
        q["type"] = _nomad_type(entity_like.value)
        unit = _unit_str(entity_like)
        if unit:
            q["unit"] = unit
        if _is_array(entity_like.value):
            q["shape"] = ["*"]

        # Build a structured description combining ontology info
        desc_parts: list[str] = []
        if entity_like.description:
            desc_parts.append(entity_like.description)
        if include_ontology_context and entity_like.ontology_label:
            desc_parts.append(f"ontology: {entity_like.ontology_label}")
        if include_ontology_context and entity_like.ontology_iri:
            desc_parts.append(f"IRI: {entity_like.ontology_iri}")
        if desc_parts:
            q["description"] = " | ".join(desc_parts)

    elif hasattr(entity_like, "unit"):  # mammos_units Quantity
        q["type"] = "np.float64"
        unit = _unit_str(entity_like)
        if unit:
            q["unit"] = unit
        val = getattr(entity_like, "value", entity_like)
        if _is_array(val):
            q["shape"] = ["*"]

    elif isinstance(entity_like, str):
        q["type"] = "str"

    elif isinstance(entity_like, bool):
        q["type"] = "bool"

    elif isinstance(entity_like, (int, np.integer)):
        q["type"] = "int"

    elif isinstance(entity_like, (float, np.floating)):
        q["type"] = "np.float64"

    else:
        # Try to infer from the numpy representation
        try:
            arr = np.asanyarray(entity_like)
            q["type"] = _nomad_type(arr)
            if _is_array(arr):
                q["shape"] = ["*"]
        except Exception:
            q["type"] = "str"

    return q


def _mammos_entity_record(name: str, entity_like: Any) -> dict[str, str]:
    """Build retrieval-focused metadata for one entry from the source collection."""
    import mammos_entity as me  # noqa: PLC0415

    record: dict[str, str] = {
        "name": name,
        "value_key": name,
        "source_type": type(entity_like).__name__,
        "ontology_label": "",
        "ontology_iri": "",
        "unit": "",
        "description": "",
    }

    if isinstance(entity_like, me.Entity):
        record["ontology_label"] = entity_like.ontology_label or ""
        record["ontology_iri"] = entity_like.ontology_iri or ""
        record["unit"] = _unit_str(entity_like) or ""
        record["description"] = entity_like.description or ""
    elif hasattr(entity_like, "unit"):
        record["unit"] = _unit_str(entity_like) or ""

    return record


def _normalize_elemental_composition(
    elemental_composition: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Normalize elemental composition entries for YAML serialization."""
    if not elemental_composition:
        return []

    normalized: list[dict[str, Any]] = []
    for entry in elemental_composition:
        if not isinstance(entry, dict):
            continue
        element = entry.get("element")
        if not isinstance(element, str) or not element.strip():
            continue
        out: dict[str, Any] = {"element": element.strip()}
        if entry.get("atomic_fraction") is not None:
            out["atomic_fraction"] = float(entry["atomic_fraction"])
        if entry.get("mass_fraction") is not None:
            out["mass_fraction"] = float(entry["mass_fraction"])
        normalized.append(out)
    return normalized


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_archive(
    data: mammos_entity.EntityCollection | mammos_entity.Entity,
    *,
    name: str = "MaMMoS Data",
    section_name: str | None = None,
    institute: str = "",
    owner: str = "",
    lab_id: str = "",
    description: str = "",
    method: str = "",
    short_name: str = "",
    chemical_formula: str = "",
    elemental_composition: list[dict[str, Any]] | None = None,
    default_entry_name: str = "MaMMoS Data",
    extra_quantities: dict[str, dict[str, Any]] | None = None,
    extra_data: dict[str, Any] | None = None,
    extra_base_sections: list[str] | None = None,
    include_entity_values: bool = True,
    include_mammos_entities_metadata: bool = True,
    include_mammos_entity_version: bool = False,
    include_nomad_generation_metadata: bool = False,
    nomad_generation_metadata: dict[str, Any] | None = None,
    include_ontology_in_yaml: bool = True,
) -> dict:
    """Generate a NOMAD archive dictionary from mammos-entity data.

    The returned dictionary can be written to a ``.archive.yaml`` file with
    :func:`to_nomad._io.save_archive_yaml`.

    Args:
        data:
            An :class:`~mammos_entity.EntityCollection` or a single
            :class:`~mammos_entity.Entity`.
        name:
            Human-readable name for the NOMAD schema (used as the ``definitions
            .name`` field and as the default ``section_name``).
        section_name:
            Python identifier used as the NOMAD section class name.  Derived
            from *name* automatically if not provided.
        institute:
            Name of the institute / organization that produced the data.
        owner:
            Data owner / primary contact person (comma-separated if multiple).
        lab_id:
            Laboratory or dataset identifier.
        description:
            Long description of the dataset (what was measured / simulated,
            conditions, references, …).  Falls back to the collection's own
            ``description`` attribute.
        method:
            Measurement or simulation method (e.g. ``"VSM"``, ``"micromagnetics"``).
        short_name:
            Short name or label for the sample.
        chemical_formula:
            Chemical formula of the sample (e.g. ``"Nd2Fe14B"``).  When
            provided, ``nomad.datamodel.metainfo.eln.Chemical`` is added as a
            base section so that NOMAD can display the formula properly.
        elemental_composition:
            Optional list of elemental composition entries. Each item should
            contain ``element`` and may also provide ``atomic_fraction`` and
            ``mass_fraction``.
        default_entry_name:
            Default value for the ``name`` field in the generated NOMAD entry.
        extra_quantities:
            Optional additional quantity definitions to append to the generated
            section quantities. Keys are quantity names, values are quantity
            definition dictionaries (NOMAD schema format).
        extra_data:
            Optional additional key/value pairs to append to the ``data``
            section.
        extra_base_sections:
            Optional additional base sections appended to the generated section
            definition.
        include_entity_values:
            If ``True`` (default), entity values are written to the ``data``
            section. Set to ``False`` when values should be resolved by a
            normalizer (e.g. HDF annotations).
        include_mammos_entities_metadata:
            If ``True`` (default), include the ``mammos_entities`` subsection
            and corresponding data records.
        include_mammos_entity_version:
            If ``True``, include legacy top-level ``mammos_entity_version``
            quantity and value.
        include_nomad_generation_metadata:
            If ``True``, include a dedicated ``nomad_generation`` subsection
            describing how this NOMAD archive was produced.
        nomad_generation_metadata:
            Values written to ``data.nomad_generation`` when
            ``include_nomad_generation_metadata=True``.
        include_ontology_in_yaml:
            If ``True`` (default), include ontology label/IRI in quantity
            descriptions.

    Returns:
        A nested dictionary ready for YAML serialization in NOMAD archive
        format.

    Raises:
        TypeError:
            If *data* is neither an :class:`~mammos_entity.EntityCollection`
            nor an :class:`~mammos_entity.Entity`.

    Examples:
        >>> import mammos_entity as me
        >>> from to_nomad._schema import generate_archive
        >>> col = me.EntityCollection(
        ...     description="NdFeB sample at room temperature",
        ...     Ms=me.Ms(1.28e6, "A/m"),
        ...     Hc=me.Hc(875e3, "A/m"),
        ...     Tc=me.Tc(585, "K"),
        ... )
        >>> archive = generate_archive(
        ...     col,
        ...     name="NdFeB Intrinsic Properties",
        ...     institute="My University",
        ...     owner="Jane Doe",
        ...     lab_id="MyUni-001",
        ... )
        >>> list(archive.keys())
        ['definitions', 'data']
    """
    import mammos_entity as me  # noqa: PLC0415

    # Normalise: wrap a bare Entity into an EntityCollection
    if isinstance(data, me.Entity):
        col: mammos_entity.EntityCollection = me.EntityCollection(
            description=data.description
        )
        col[data.ontology_label] = data
    elif isinstance(data, me.EntityCollection):
        col = data
    else:
        raise TypeError(
            "data must be a mammos_entity.EntityCollection or mammos_entity.Entity, "
            f"got {type(data).__name__}."
        )

    if section_name is None:
        section_name = _section_name_from(name)

    # ------------------------------------------------------------------
    # Build the quantities block of the schema definition.
    # Standard NOMAD ELN fields are always included; entity quantities
    # are appended after them.
    # ------------------------------------------------------------------
    quantities: dict[str, dict] = {
        "name": {"type": "str", "default": default_entry_name},
        "description": {"type": "str"},
        "lab_id": {"type": "str"},
        "short_name": {"type": "str"},
        "owner": {"type": "str"},
    }
    if include_mammos_entity_version:
        quantities["mammos_entity_version"] = {
            "type": "str",
            "description": "Version of mammos-entity used by the input data.",
        }

    mammos_entity_records: list[dict[str, str]] = []

    for ename, entity_like in col:
        if isinstance(entity_like, me.EntityCollection):
            # Nested collections cannot be represented as a flat quantity.
            # Flatten one level deep by prefixing the key.
            for sub_name, sub_entity in entity_like:
                if isinstance(sub_entity, me.EntityCollection):
                    import warnings  # noqa: PLC0415

                    warnings.warn(
                        f"Nested EntityCollection '{ename}.{sub_name}' is more "
                        "than one level deep and will be skipped.",
                        stacklevel=2,
                    )
                    continue
                flat_key = f"{ename}__{sub_name}"
                quantities[flat_key] = _quantity_def(
                    flat_key,
                    sub_entity,
                    include_ontology_context=include_ontology_in_yaml,
                )
                mammos_entity_records.append(
                    _mammos_entity_record(flat_key, sub_entity)
                )
        else:
            quantities[ename] = _quantity_def(
                ename,
                entity_like,
                include_ontology_context=include_ontology_in_yaml,
            )
            mammos_entity_records.append(_mammos_entity_record(ename, entity_like))

    if extra_quantities:
        for qname, qextra in extra_quantities.items():
            if qname in quantities and isinstance(quantities[qname], dict):
                merged = dict(quantities[qname])
                if "m_annotations" in qextra and "m_annotations" in merged:
                    ann = dict(merged["m_annotations"])
                    ann.update(qextra["m_annotations"])
                    merged["m_annotations"] = ann
                    qextra = {k: v for k, v in qextra.items() if k != "m_annotations"}
                merged.update(qextra)
                quantities[qname] = merged
            else:
                quantities[qname] = qextra

    elemental_composition_data = _normalize_elemental_composition(elemental_composition)

    # Base sections: add Chemical if composition metadata is given
    base_sections: list[str] = ["nomad.datamodel.data.EntryData"]
    if chemical_formula or elemental_composition_data:
        base_sections = [
            "nomad.datamodel.metainfo.eln.Chemical",
            "nomad.datamodel.data.EntryData",
        ]
    if extra_base_sections:
        for bs in extra_base_sections:
            if bs not in base_sections:
                base_sections.append(bs)

    sub_sections: dict[str, Any] = {}
    if include_mammos_entities_metadata:
        sub_sections["mammos_entities"] = {
            "repeats": True,
            "section": {
                "quantities": {
                    "name": {"type": "str"},
                    "value_key": {"type": "str"},
                    "source_type": {"type": "str"},
                    "ontology_label": {"type": "str"},
                    "ontology_iri": {"type": "str"},
                    "unit": {"type": "str"},
                    "description": {"type": "str"},
                }
            },
        }

    if include_nomad_generation_metadata:
        sub_sections["nomad_generation"] = {
            "section": {
                "quantities": {
                    "created_datetime_utc": {"type": "Datetime"},
                    "source_file": {"type": "str"},
                    "source_format": {"type": "str"},
                    "source_mammos_entity_version": {"type": "str"},
                    "runtime_mammos_entity_version": {"type": "str"},
                    "to_nomad_version": {"type": "str"},
                }
            }
        }

    if elemental_composition_data:
        sub_sections["elemental_composition"] = {
            "repeats": True,
            "section": {
                "quantities": {
                    "element": {"type": "str"},
                    "atomic_fraction": {"type": "np.float64"},
                    "mass_fraction": {"type": "np.float64"},
                }
            },
        }

    definitions: dict = {
        "name": name,
        "sections": {
            section_name: {
                "base_sections": base_sections,
                "quantities": quantities,
                "sub_sections": sub_sections,
            }
        },
    }

    # ------------------------------------------------------------------
    # Build the data block.
    # ------------------------------------------------------------------
    data_block: dict[str, Any] = {"m_def": section_name}

    # Standard metadata fields (only written if non-empty)
    _opt_fields: list[tuple[str, str]] = [
        ("institute", institute),
        ("lab_id", lab_id),
        ("owner", owner),
        ("short_name", short_name),
        ("method", method),
        ("chemical_formula", chemical_formula),
    ]
    for field_name, field_value in _opt_fields:
        if field_value:
            data_block[field_name] = field_value

    # Description: prefer explicit argument, fall back to collection description
    data_block["description"] = description or col.description
    if include_mammos_entity_version:
        data_block["mammos_entity_version"] = me.__version__
    if include_mammos_entities_metadata:
        data_block["mammos_entities"] = mammos_entity_records
    if include_nomad_generation_metadata:
        generation_data = {
            k: v
            for k, v in (nomad_generation_metadata or {}).items()
            if v is not None and v != ""
        }
        if generation_data:
            data_block["nomad_generation"] = generation_data
    if elemental_composition_data:
        data_block["elemental_composition"] = elemental_composition_data
    if extra_data:
        data_block.update(extra_data)

    # Entity values (optional; can be omitted in reference-based workflows)
    if include_entity_values:
        for ename, entity_like in col:
            if isinstance(entity_like, me.EntityCollection):
                for sub_name, sub_entity in entity_like:
                    if isinstance(sub_entity, me.EntityCollection):
                        continue
                    flat_key = f"{ename}__{sub_name}"
                    val = getattr(sub_entity, "value", sub_entity)
                    data_block[flat_key] = _to_serializable(val)
            else:
                val = getattr(entity_like, "value", entity_like)
                data_block[ename] = _to_serializable(val)

    return {"definitions": definitions, "data": data_block}
