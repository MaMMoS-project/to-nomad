"""Interactive metadata collection for NOMAD uploads.

When converting an :class:`~mammos_entity.EntityCollection` to a NOMAD archive,
several metadata fields are required (institute, owner, lab_id, description)
that are not stored inside the entity itself.  This module handles prompting
the user for those values when they have not been provided programmatically.
"""

from __future__ import annotations

import sys

# ---------------------------------------------------------------------------
# Field definitions
# ---------------------------------------------------------------------------

# (key, label, required)
_REQUIRED_FIELDS: list[tuple[str, str]] = [
    ("institute", "Institute / organization name"),
    ("owner", "Data owner / contact person (comma-separated if multiple)"),
    ("lab_id", "Lab or dataset identifier (lab_id)"),
    ("description", "Dataset description"),
]

# (key, label, default_value)
_OPTIONAL_FIELDS: list[tuple[str, str, str]] = [
    ("name", "Schema / entry name", "MaMMoS Data"),
    ("short_name", "Short name for the sample", ""),
    ("method", "Measurement / simulation method", ""),
    ("chemical_formula", "Chemical formula (leave blank if not applicable)", ""),
    ("default_entry_name", "Default NOMAD entry name", "MaMMoS Data"),
]

# All field keys handled by this module
ALL_FIELD_KEYS: frozenset[str] = frozenset(
    [k for k, _ in _REQUIRED_FIELDS] + [k for k, _, _ in _OPTIONAL_FIELDS]
)


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------


def _ask(prompt: str, default: str = "") -> str:
    """Prompt the user, showing *default* in brackets, and return the answer."""
    hint = f" [{default}]" if default else ""
    full_prompt = f"  {prompt}{hint}: "
    try:
        answer = input(full_prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return default
    return answer if answer else default


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def collect_metadata(
    collection_description: str = "",
    *,
    interactive: bool = True,
    **provided: str,
) -> dict[str, str]:
    """Collect NOMAD metadata, prompting the user for any missing required fields.

    Args:
        collection_description:
            Description string from the source
            :class:`~mammos_entity.EntityCollection`.  Used as a seed value
            for the ``description`` field if the user has not provided one.
        interactive:
            When ``True`` (the default), missing required fields are requested
            via ``input()`` on *stdin*.  When ``False``, only *provided*
            values and defaults are used; missing required fields are left
            empty (a warning is printed).
        **provided:
            Pre-filled metadata values.  Any key from :data:`ALL_FIELD_KEYS`
            is accepted.  Values that are empty strings are treated as absent.

    Returns:
        A dictionary with at least the keys found in :data:`ALL_FIELD_KEYS`.
        Required fields that are truly absent (not provided and not collected
        interactively) are stored as empty strings.

    Examples:
        Non-interactive usage::

            meta = collect_metadata(
                interactive=False,
                institute="My University",
                owner="Jane Doe",
                lab_id="MyUni-001",
                description="NdFeB sample at 300 K",
            )
    """
    # Seed with provided values that are non-empty strings
    meta: dict[str, str] = {
        k: v for k, v in provided.items() if isinstance(v, str) and v
    }

    # Pre-populate description from the collection if not already given
    if "description" not in meta and collection_description:
        meta["description"] = collection_description

    if not interactive:
        # Fill defaults for optional fields that were not provided
        for key, _label, default in _OPTIONAL_FIELDS:
            meta.setdefault(key, default)

        # Warn about absent required fields
        missing = [k for k, _ in _REQUIRED_FIELDS if not meta.get(k)]
        if missing:
            print(
                f"Warning: the following required NOMAD metadata fields are "
                f"missing: {', '.join(missing)}.  The generated archive YAML "
                "may be incomplete.",
                file=sys.stderr,
            )
        return meta

    # ------------------------------------------------------------------
    # Interactive mode
    # ------------------------------------------------------------------
    missing_required = [(k, lbl) for k, lbl in _REQUIRED_FIELDS if not meta.get(k)]
    missing_optional = [
        (k, lbl, dflt) for k, lbl, dflt in _OPTIONAL_FIELDS if not meta.get(k)
    ]

    if missing_required or missing_optional:
        print("\n--- NOMAD upload metadata ---")

    if missing_required:
        print("Please provide the required fields below.")
        print("(These are needed for a meaningful NOMAD entry.)\n")
        for key, label in missing_required:
            value = _ask(label)
            if value:
                meta[key] = value

    if missing_optional:
        print("\nOptional fields (press Enter to use the default / skip):")
        for key, label, default in missing_optional:
            value = _ask(label, default)
            meta[key] = value

    if missing_required or missing_optional:
        print()

    return meta
