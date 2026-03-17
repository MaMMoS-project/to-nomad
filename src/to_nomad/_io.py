"""File I/O utilities: writing ``.archive.yaml`` files and creating upload zips.

This module provides two thin wrappers:

* :func:`save_archive_yaml` — serialise a NOMAD archive dictionary to a
  ``.archive.yaml`` file using PyYAML with formatting that matches the style
  of existing MaMMoS NOMAD example uploads.
* :func:`create_upload_zip` — bundle one or more files (e.g. the generated
  archive YAML plus raw data files) into a ``.zip`` file ready for manual or
  API-based upload to NOMAD.
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any

import yaml


# ---------------------------------------------------------------------------
# Custom YAML dumper
# ---------------------------------------------------------------------------


class _NomadDumper(yaml.SafeDumper):
    """PyYAML dumper tuned to the style used in MaMMoS NOMAD upload archives.

    * Sequences (lists / tuples) are rendered in *flow style*, e.g.
      ``[1.0, 2.0, 3.0]``.
    * Multi-line strings are rendered in *block literal* style (``|``).
    * Single-line strings use the default plain style.
    """


def _represent_sequence(dumper: yaml.Dumper, value: list | tuple) -> yaml.Node:
    return dumper.represent_sequence("tag:yaml.org,2002:seq", value, flow_style=True)


def _represent_str(dumper: yaml.Dumper, value: str) -> yaml.Node:
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


_NomadDumper.add_representer(list, _represent_sequence)
_NomadDumper.add_representer(tuple, _represent_sequence)
_NomadDumper.add_representer(str, _represent_str)


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def save_archive_yaml(archive: dict[str, Any], output_path: str | Path) -> Path:
    """Write a NOMAD archive dictionary to a ``.archive.yaml`` file.

    Parent directories are created automatically if they do not exist.

    Args:
        archive:
            The archive dict returned by
            :func:`to_nomad._schema.generate_archive`.
        output_path:
            Destination file path.  The ``.archive.yaml`` suffix is
            conventional for NOMAD but not enforced by this function.

    Returns:
        The *resolved* (absolute) path of the written file.

    Examples:
        >>> from pathlib import Path
        >>> from to_nomad._io import save_archive_yaml
        >>> path = save_archive_yaml({"definitions": {}, "data": {}}, "/tmp/test.archive.yaml")
        >>> path.exists()
        True
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as fh:
        yaml.dump(
            archive,
            stream=fh,
            Dumper=_NomadDumper,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        )

    return output_path.resolve()


def create_upload_zip(
    *files: str | Path,
    output_path: str | Path,
) -> Path:
    """Bundle files into a ``.zip`` file for NOMAD upload.

    Each file is placed at the *root* of the zip archive (no sub-directories
    are created).

    Args:
        *files:
            Paths to files that should be included in the zip.  Typically
            this is the ``.archive.yaml`` file and any associated raw data
            files (HDF, CSV, ...).
        output_path:
            Path for the output zip file.  Parent directories are created
            automatically.

    Returns:
        The *resolved* path of the created zip file.

    Raises:
        FileNotFoundError:
            If any of the input *files* does not exist.

    Examples:
        >>> from pathlib import Path
        >>> from to_nomad._io import create_upload_zip, save_archive_yaml
        >>> yaml_path = save_archive_yaml({}, "/tmp/test.archive.yaml")
        >>> zip_path = create_upload_zip(yaml_path, output_path="/tmp/test_upload.zip")
        >>> zip_path.exists()
        True
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            p = Path(f)
            if not p.exists():
                raise FileNotFoundError(f"File not found: {p}")
            zf.write(p, arcname=p.name)

    return output_path.resolve()
