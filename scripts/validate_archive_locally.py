"""Validate a NOMAD archive YAML + data-file pair locally with nomad-lab.

Reproduces the server-side processing without a NOMAD instance: a staging
upload is created from the directory that contains the archive YAML, the
archive parser and all normalizers run (including HDF5Normalizer and
PlotSection), and the normalized archive is inspected:

- HDF5-referenced quantities must be filled,
- declared plots must exist as figures with x/y values,
- the full normalized archive is written as JSON for inspection.

Run inside the nomad-test pixi environment:
    pixi run -e nomad-test validate <path-to-archive.archive.yaml> [--json PATH]

The upload directory is taken to be the parent directory of the archive
YAML; the data file (e.g. the .h5) must sit next to it.
"""

import argparse
import json
import os
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

from nomad import files
from nomad.client import normalize_all, parse
from nomad.datamodel.context import ServerContext

UPLOAD_ID = "to_nomad_local_validation"


class _LocalUpload:
    """Minimal upload stand-in for ServerContext outside a NOMAD server."""

    def __init__(self, upload_files: object) -> None:
        """Store the staging upload files.

        Args:
            upload_files: A StagingUploadFiles instance.
        """
        self.upload_files = upload_files
        self.upload_id = upload_files.upload_id  # type: ignore[attr-defined]


def _attach_local_upload_context(archive: object, upload_files: object) -> None:
    """Give the archive a server-like context pointing at the staging upload.

    HDF5Normalizer resolves the data file through
    ``archive.m_context.upload_files``; the local parse attaches a
    ClientContext without upload files, so normalization would fail.

    Args:
        archive: A parsed EntryArchive.
        upload_files: The StagingUploadFiles created for validation.
    """
    archive.m_context = ServerContext(upload=_LocalUpload(upload_files))  # type: ignore[attr-defined]


def _walk_sections(section: object):
    """Yield the section and, recursively, all its sub-sections.

    Args:
        section: A metainfo section instance.
    """
    yield section
    for content in section.m_contents():  # type: ignore[attr-defined]
        if hasattr(content, "m_def"):
            yield from _walk_sections(content)


def _count_hdf_quantities(archive: object) -> tuple[int, int]:
    """Count filled and empty HDF5-referenced quantities in the archive.

    Args:
        archive: A normalized EntryArchive.

    Returns:
        Tuple of (filled, empty) quantity counts.
    """
    filled = 0
    empty = 0
    for section in _walk_sections(archive):
        for qname, qdef in section.m_def.all_quantities.items():  # type: ignore[attr-defined]
            try:
                annotation = qdef.m_get_annotations("hdf5", None)  # type: ignore[attr-defined]
            except Exception:
                annotation = None
            if not annotation:
                continue
            value = getattr(section, qname, None)
            if value is None:
                empty += 1
            else:
                filled += 1
    return filled, empty


def _run_with_captured_stderr(func: Callable[[], object]) -> tuple[object, str]:
    """Run a callable with stderr redirected into a temporary file.

    Args:
        func: Callable to execute.

    Returns:
        Tuple of the callable's return value and the captured stderr text.
        File-descriptor redirection is used so that loggers holding an
        older reference to sys.stderr are captured as well.
    """
    saved_fd = os.dup(2)
    capture = tempfile.TemporaryFile(mode="w+")
    try:
        os.dup2(capture.fileno(), 2)
        try:
            result = func()
        finally:
            os.dup2(saved_fd, 2)
            os.close(saved_fd)
        capture.seek(0)
        return result, capture.read()
    finally:
        capture.close()


def _warning_lines(stderr_text: str) -> list[str]:
    """Extract warning-like lines from captured stderr text.

    Args:
        stderr_text: Captured stderr output of parse/normalize.

    Returns:
        List of warning message lines (NOMAD normalizer warnings and
        Python warnings).
    """
    return [
        line.strip()
        for line in stderr_text.splitlines()
        if line.strip() and ("warning" in line.lower() or "(normalizer=" in line)
    ]


def validate(mainfile_path: Path, json_path: Path) -> int:
    """Parse, normalize, and check one archive YAML.

    Args:
        mainfile_path: Path to the .archive.yaml; its parent directory is
            used as the upload directory (the data file must sit next to it).
        json_path: Destination for the full normalized archive as JSON.

    Returns:
        Number of failed checks (0 means the archive validates).
    """
    upload_dir = str(mainfile_path.parent)
    mainfile = mainfile_path.name
    upload_files = files.StagingUploadFiles(upload_id=UPLOAD_ID, create=True)
    failures = 0
    try:
        upload_files.add_rawfiles(upload_dir)
        mainfile_os_path = upload_files.raw_file_object(mainfile).os_path

        def _parse_and_normalize() -> list[object]:
            """Run parse and normalize in the local staging upload."""
            parsed = parse(mainfile_os_path, parser_name="parsers/archive")
            for archive in parsed:
                _attach_local_upload_context(archive, upload_files)
                normalize_all(archive)
                archive.metadata.apply_archive_metadata(archive)  # type: ignore[attr-defined]
            return parsed

        archives, stderr_text = _run_with_captured_stderr(_parse_and_normalize)
        warning_list = _warning_lines(stderr_text)
        for archive in archives:
            report = archive.m_to_dict()  # type: ignore[attr-defined]
            figures = report.get("data", {}).get("figures", [])
            filled, empty = _count_hdf_quantities(archive)
            print(f"mainfile: {mainfile_path}")
            print(f"  hdf-referenced quantities: {filled} filled, {empty} empty")
            if empty:
                failures += empty
            print(f"  figures: {len(figures)}")
            for figure in figures:
                for trace in figure.get("figure", {}).get("data", []):
                    x = trace.get("x")
                    y = trace.get("y")
                    z = trace.get("z")
                    ok = (bool(x) and bool(y)) or bool(z)
                    if not ok:
                        failures += 1
                    print(
                        f"  trace: x values: {len(x) if x else 0}, "
                        f"y values: {len(y) if y else 0}, "
                        f"z values: {len(z) if z else 0}"
                        + ("" if ok else "  <-- EMPTY")
                    )
            with open(json_path, "w") as f:
                json.dump(report, f, indent=2, default=str)
            print(f"  normalized archive: {json_path}")
            print(f"  warnings ({len(warning_list)}):")
            counts: dict[str, int] = {}
            for line in warning_list:
                counts[line] = counts.get(line, 0) + 1
            if counts:
                for line, count in counts.items():
                    print(f"    [{count}x] {line}" if count > 1 else f"    {line}")
            else:
                print("    none")
    finally:
        try:
            upload_files.delete()
        except Exception:
            pass
    return failures


def main() -> None:
    """Run the validation from command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Validate a NOMAD archive YAML + data-file pair locally."
    )
    parser.add_argument(
        "mainfile_path",
        type=Path,
        help="Path to the .archive.yaml; the data file must sit next to it.",
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=None,
        help="Destination for the normalized archive JSON "
        "(default: <stem>.validated.json next to the archive).",
    )
    args = parser.parse_args()
    stem = args.mainfile_path.name
    if stem.endswith(".archive.yaml"):
        stem = stem[: -len(".archive.yaml")]
    json_path = args.json or args.mainfile_path.with_name(f"{stem}.validated.json")
    failures = validate(args.mainfile_path, json_path)
    print("VALIDATION OK" if failures == 0 else f"VALIDATION FAILED ({failures})")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
