"""Example: safe upload of generated files into a NOMAD project.

Demonstrates the programmatic use of
``to_nomad.upload_to_nomad.upload_files``. This example runs in
DRY-RUN mode: no token is needed and nothing is sent over the
network. For the real transfer call it with ``dry_run=False`` (see
the README section "Uploading via the API" for the safety model and
the personal access token setup) or use the command line:

    pixi run upload <files...> --project-id <id>           # dry-run
    pixi run upload <files...> --project-id <id> --yes     # real upload
    pixi run upload --project-id <id> --status             # read-only status

Run with:
    pixi run python examples/upload_example.py
"""

from pathlib import Path

from to_nomad.upload_to_nomad import upload_files

out_dir = Path(__file__).parent / "output"

# A project id is ALWAYS required and must name YOUR existing,
# unpublished project (the central instance limits the number of
# projects; files can be added to an existing one at any time).
project_id = "your-project-id-here"

# Example file set: the output of examples/from_cif_structure.py.
files = [
    out_dir / "cif_structure.archive.yaml",
    out_dir / "cif_structure.h5",
    out_dir / "Co2Fe2H4_structure.cif",
]
existing = [path for path in files if path.is_file()]
if not existing:
    raise SystemExit(
        "No example files found in examples/output/. "
        "Run examples/from_cif_structure.py first."
    )

# dry_run=True (the default): prints the plan (file list with sizes
# and SHA-256 checksums, target project, API URL) without reading a
# token and without any network access.
report = upload_files(
    existing,
    project_id,
    dry_run=True,
)

# For the real upload, use the CLI with --yes (recommended) or call:
# upload_files(existing, project_id, dry_run=False, wait=True)
# The real run reads the token from NOMAD_CLIENT_ACCESS_TOKEN or
# ~/.config/to_nomad/token (chmod 600), never from arguments.
print(f"\nreport: {len(report['files'])} file(s) planned for upload")
