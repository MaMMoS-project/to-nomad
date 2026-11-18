"""Safe NOMAD API upload for existing files (dry-run by default).

Uploads files into an EXISTING project (NOMAD upload) via the NOMAD
REST API. Safety model (see the README section "Uploading via the
API"):

- authentication via a personal access token (PAT) read ONLY from the
  environment (``NOMAD_CLIENT_ACCESS_TOKEN``) or a token file OUTSIDE
  the repository (default ``~/.config/to-nomad/token``); never from a
  command-line argument, never logged;
- dry-run is the default; the real transfer requires ``--yes``;
- the target project is given explicitly by ID; published projects are
  read-only (write attempts are refused);
- existing server-side files are never overwritten without
  ``--allow-overwrite``;
- no delete/publish/edit endpoint is used anywhere;
- no automatic retries: on failure the tool reports state; PUT to the
  same path is idempotent, so a checked manual rerun is safe;
- streaming upload with explicit Content-Length (constant memory for
  GB-range files).

Run as a module:
    python -m to_nomad.upload_to_nomad <files...> --project-id <id>      # dry-run
    python -m to_nomad.upload_to_nomad <files...> --project-id <id> --yes # upload
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_API_URL = "https://nomad-lab.eu/prod/v1/api/v1"
TOKEN_ENV_VAR = "NOMAD_CLIENT_ACCESS_TOKEN"
DEFAULT_TOKEN_FILE = Path("~/.config/to-nomad/token")

STATUS_COLOR = {"SUCCESS": "ok", "FAILURE": "FAILED", "RUNNING": "running"}


def load_token(token_file: str | Path | None = None) -> str:
    """Load the NOMAD personal access token (PAT).

    The token is read from the environment variable
    ``NOMAD_CLIENT_ACCESS_TOKEN`` or from a token file outside the
    repository. It is never accepted as a command-line argument and
    must never be logged.

    Args:
        token_file: Optional explicit path to a token file outside the
            repository. Defaults to ``~/.config/to-nomad/token``.

    Returns:
        The token string.

    Raises:
        SystemExit: If no token is available or the token file is
            readable by others.
    """
    env_token = os.environ.get(TOKEN_ENV_VAR, "").strip()
    if env_token:
        return env_token
    path = Path(token_file).expanduser() if token_file else DEFAULT_TOKEN_FILE.expanduser()
    if path.is_file():
        mode = stat.S_IMODE(path.stat().st_mode)
        if mode & 0o077:
            raise SystemExit(
                f"Token file {path} is too permissive ({oct(mode)}). "
                "Restrict it with: chmod 600 <file>"
            )
        token = path.read_text(encoding="utf-8").strip()
        if token:
            return token
    raise SystemExit(
        f"No NOMAD token found. Set the environment variable {TOKEN_ENV_VAR} "
        f"or create the token file {DEFAULT_TOKEN_FILE} (chmod 600). "
        "Never store the token inside this repository."
    )


def _request_json(
    method: str,
    url: str,
    token: str,
    *,
    timeout: float = 300.0,
) -> dict[str, Any]:
    """Perform an authenticated JSON request and return the response.

    Args:
        method: HTTP method (GET).
        url: Full URL.
        token: Bearer token.
        timeout: Socket timeout in seconds.

    Returns:
        The parsed JSON response.

    Raises:
        SystemExit: On connection errors or unexpected HTTP status.
    """
    request = urllib.request.Request(url, method=method)
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")[:500]
        raise SystemExit(
            f"HTTP {error.code} for {url}: {body}"
        ) from error
    except (urllib.error.URLError, OSError) as error:
        raise SystemExit(f"Connection error for {url}: {error}") from error


def get_project_info(
    api_url: str,
    project_id: str,
    token: str,
    *,
    timeout: float = 300.0,
) -> dict[str, Any]:
    """Fetch the metadata of a project (upload).

    Args:
        api_url: Base URL of the NOMAD API.
        project_id: The upload/project id.
        token: Bearer token.
        timeout: Socket timeout in seconds.

    Returns:
        The 'data' dict of the upload response.

    Raises:
        SystemExit: If the project is not accessible with the token
            (wrong/expired token, not the owner, unknown id).
    """
    url = f"{api_url}/uploads/{project_id}"
    response = _request_json("GET", url, token, timeout=timeout)
    return response["data"]


def _file_exists_on_server(
    api_url: str,
    project_id: str,
    name: str,
    token: str,
    *,
    timeout: float = 300.0,
) -> bool:
    """Check whether a raw file already exists in the project.

    Args:
        api_url: Base URL of the NOMAD API.
        project_id: The upload/project id.
        name: Upload-relative file name.
        token: Bearer token.
        timeout: Socket timeout in seconds.

    Returns:
        True if the file exists, False if it does not.

    Raises:
        SystemExit: On connection errors or unexpected HTTP status.
    """
    url = f"{api_url}/uploads/{project_id}/raw/{name}"
    # The raw-file route supports GET/PUT/DELETE but not HEAD (405).
    # GET is opened and closed immediately: the existence is decided by
    # the status code, the body is never read.
    request = urllib.request.Request(url, method="GET")
    request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=timeout):
            return True
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return False
        body = error.read().decode("utf-8", errors="replace")[:500]
        raise SystemExit(f"HTTP {error.code} for {url}: {body}") from error
    except (urllib.error.URLError, OSError) as error:
        raise SystemExit(f"Connection error for {url}: {error}") from error


def _sha256_of(path: Path) -> str:
    """Compute the SHA-256 checksum of a file, streaming in blocks.

    Args:
        path: Path of the file.

    Returns:
        The hex digest of the file.
    """
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _put_files(
    api_url: str,
    project_id: str,
    entries: list[dict[str, Any]],
    token: str,
    *,
    timeout: float = 300.0,
) -> None:
    """Upload all files in one streaming multipart/form-data request.

    The PUT endpoint accepts a list of files in a single multipart
    request and adds them all with exactly ONE processing trigger
    (verified in the 2.0.0 endpoint source: one ADD operation per
    file, one ``process_upload`` call). The target file names are the
    multipart filenames; the URL path is the project root directory.
    The body is streamed with an exact Content-Length header: memory
    use is constant, independent of the total batch size.

    Args:
        api_url: Base URL of the NOMAD API.
        project_id: The upload/project id.
        entries: Local file entries (dicts with 'name' and 'path').
        token: Bearer token.
        timeout: Socket timeout in seconds.

    Raises:
        SystemExit: On connection errors or unexpected HTTP status.
    """
    url = f"{api_url}/uploads/{project_id}/raw/"
    boundary = f"to-nomad-{os.urandom(16).hex()}"
    body = MultipartBody(boundary, entries)
    request = urllib.request.Request(url, method="PUT", data=body)
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Accept", "application/json")
    request.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    request.add_header("Content-Length", str(body.length))
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response.read()
    except urllib.error.HTTPError as error:
        body_text = error.read().decode("utf-8", errors="replace")[:500]
        raise SystemExit(f"HTTP {error.code} for {url}: {body_text}") from error
    except (urllib.error.URLError, OSError) as error:
        raise SystemExit(
            f"Connection error while uploading the batch: {error}. "
            "The PUT is idempotent; verify the project state, then rerun."
        ) from error
    finally:
        body.close()


class MultipartBody:
    """Streaming multipart/form-data body with an exact total length."""

    def __init__(self, boundary: str, entries: list[dict[str, Any]]) -> None:
        """Open all files and build the multipart framing.

        Args:
            boundary: Multipart boundary string.
            entries: List of dicts with 'name' (target file name,
                used as the multipart filename) and 'path' (local
                source file path).
        """
        self._sources: list[Any] = []
        length = 0
        for entry in entries:
            prefix = (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="file"; filename="{entry["name"]}"\r\n'
                "Content-Type: application/octet-stream\r\n\r\n"
            ).encode("utf-8")
            size = entry["path"].stat().st_size
            self._sources.append(prefix)
            self._sources.append(entry["path"].open("rb"))
            self._sources.append(b"\r\n")
            length += len(prefix) + size + 2
        self._suffix = f"--{boundary}--\r\n".encode("utf-8")
        length += len(self._suffix)
        self.length = length
        self._index = 0
        self._position = 0
        self._suffix_sent = False

    def read(self, block_size: int = 65536) -> bytes:
        """Return the next block of the multipart body.

        Args:
            block_size: Maximum number of bytes to return.

        Returns:
            The next block, empty at the end of the body.
        """
        chunks: list[bytes] = []
        remaining = block_size
        while remaining > 0:
            if self._index < len(self._sources):
                source = self._sources[self._index]
                if isinstance(source, bytes):
                    take = min(remaining, len(source) - self._position)
                    chunks.append(source[self._position : self._position + take])
                    self._position += take
                    remaining -= take
                    if self._position >= len(source):
                        self._index += 1
                        self._position = 0
                else:
                    block = source.read(remaining)
                    if block:
                        chunks.append(block)
                        remaining -= len(block)
                    else:
                        self._index += 1
                        self._position = 0
            elif not self._suffix_sent:
                chunks.append(self._suffix)
                self._suffix_sent = True
                remaining -= len(self._suffix)
            else:
                break
        return b"".join(chunks)

    def close(self) -> None:
        """Close all underlying file handles."""
        for source in self._sources:
            if not isinstance(source, bytes):
                source.close()


def _local_files(files: list[str | Path]) -> list[dict[str, Any]]:
    """Validate the local file list and compute size and checksum.

    Args:
        files: Local file paths.

    Returns:
        List of dicts with 'path', 'name', 'size', 'sha256'.

    Raises:
        SystemExit: If a file does not exist, is not a file, or has a
            path separator in its name (flat upload layout only).
    """
    entries: list[dict[str, Any]] = []
    for item in files:
        path = Path(item).resolve()
        if not path.is_file():
            raise SystemExit(f"Not a file: {path}")
        name = path.name
        if "/" in name:
            raise SystemExit(f"Refusing nested target path: {name}")
        entries.append(
            {
                "path": path,
                "name": name,
                "size": path.stat().st_size,
                "sha256": _sha256_of(path),
            }
        )
    return entries


def upload_files(
    files: list[str | Path],
    project_id: str,
    *,
    api_url: str = DEFAULT_API_URL,
    token_file: str | Path | None = None,
    allow_overwrite: bool = False,
    dry_run: bool = True,
    wait: bool = False,
    poll_interval: float = 5.0,
    timeout: float = 300.0,
) -> dict[str, Any]:
    """Upload files into an existing NOMAD project, safely.

    Dry-run (default) performs no network access and only prints the
    plan. The real run verifies the project (access, unpublished),
    refuses to overwrite existing files without *allow_overwrite*,
    uploads each file streaming, and optionally waits for processing
    and reports per-entry status.

    Args:
        files: Local file paths to upload.
        project_id: Target project (upload) id, explicit.
        api_url: Base URL of the NOMAD API.
        token_file: Optional token file path outside the repository.
        allow_overwrite: Permit overwriting existing server files.
        dry_run: If True (default), only print the plan.
        wait: Wait for processing and report per-entry status.
        poll_interval: Seconds between status polls when waiting.
        timeout: Socket timeout in seconds (no total-time cap).

    Returns:
        Report dict with the local file list, project info (real run),
        and, when waiting, processing status and per-entry report.

    Raises:
        SystemExit: On missing token, inaccessible project, published
            project, existing files without overwrite permission, or
            any transfer error.
    """
    entries = _local_files(files)
    report: dict[str, Any] = {
        "project_id": project_id,
        "api_url": api_url,
        "dry_run": dry_run,
        "files": [
            {"name": e["name"], "size": e["size"], "sha256": e["sha256"]}
            for e in entries
        ],
    }
    print(f"project:       {project_id}")
    print(f"api:           {api_url}")
    print(f"mode:          {'DRY RUN (no network)' if dry_run else 'UPLOAD'}")
    for entry in entries:
        print(
            f"file:          {entry['name']}  ({entry['size']} bytes, "
            f"sha256 {entry['sha256'][:12]}...)"
        )
    if dry_run:
        print("dry-run: nothing was sent. Rerun with --yes to upload.")
        return report

    token = load_token(token_file)
    info = get_project_info(api_url, project_id, token, timeout=timeout)
    report["project"] = {
        "upload_name": info.get("upload_name"),
        "published": info.get("published"),
        "process_status": info.get("process_status"),
    }
    if info.get("published"):
        raise SystemExit(
            "This project is published and therefore immutable. "
            "Only read-only inspection is possible."
        )
    if info.get("process_running"):
        raise SystemExit(
            "The project is currently processing; wait for it to finish "
            "before uploading."
        )
    existing = [
        e["name"]
        for e in entries
        if _file_exists_on_server(api_url, project_id, e["name"], token, timeout=timeout)
    ]
    if existing:
        if not allow_overwrite:
            raise SystemExit(
                f"Refusing to overwrite existing file(s): {', '.join(existing)}. "
                "Use --allow-overwrite to replace them."
            )
        print(f"overwriting:   {', '.join(existing)}")
    print("uploading:     batch of %d file(s) in one request ..." % len(entries))
    _put_files(api_url, project_id, entries, token, timeout=timeout)
    for entry in entries:
        print(f"uploaded:      {entry['name']}")
    if wait:
        report["processing"] = wait_for_processing(
            api_url, project_id, token, poll_interval=poll_interval, timeout=timeout
        )
        report["entries"] = entry_report(api_url, project_id, token, timeout=timeout)
    else:
        print(
            "transfer done. Processing runs server-side; check later with "
            "`python -m to_nomad.upload_to_nomad --project-id <id> --status`"
        )
    return report


def wait_for_processing(
    api_url: str,
    project_id: str,
    token: str,
    *,
    poll_interval: float = 5.0,
    timeout: float = 300.0,
) -> dict[str, Any]:
    """Poll the project until processing finishes.

    There is no total time cap: processing of GB uploads may take a
    long time. Interrupt with Ctrl+C at any time; the upload itself
    has already completed at this point.

    Args:
        api_url: Base URL of the NOMAD API.
        project_id: The upload/project id.
        token: Bearer token.
        poll_interval: Seconds between status polls.
        timeout: Socket timeout in seconds.

    Returns:
        Final project 'data' dict.
    """
    print("waiting for processing (Ctrl+C to abort polling) ...")
    while True:
        info = get_project_info(api_url, project_id, token, timeout=timeout)
        if not info.get("process_running") and info.get("process_status") in (
            "SUCCESS",
            "FAILURE",
        ):
            print(f"processing:    {info.get('process_status')}")
            return info
        time.sleep(poll_interval)


def entry_report(
    api_url: str,
    project_id: str,
    token: str,
    *,
    timeout: float = 300.0,
) -> list[dict[str, Any]]:
    """Report per-entry processing status of the project.

    Args:
        api_url: Base URL of the NOMAD API.
        project_id: The upload/project id.
        token: Bearer token.
        timeout: Socket timeout in seconds.

    Returns:
        List of per-entry dicts with mainfile, process_status, errors.
    """
    url = f"{api_url}/uploads/{project_id}/entries"
    response = _request_json("GET", url, token, timeout=timeout)
    entries = response.get("data", [])
    failures = 0
    for entry in entries:
        status = entry.get("process_status")
        errors = entry.get("errors", [])
        print(
            f"entry:         {entry.get('mainfile')}  -> {status}"
            + (f"  errors: {errors}" if errors else "")
        )
        if status != "SUCCESS":
            failures += 1
    print("entries:       all processed successfully" if not failures else f"entries:       {failures} entry/entries failed")
    return entries


def status_only(
    project_id: str,
    *,
    api_url: str = DEFAULT_API_URL,
    token_file: str | Path | None = None,
    timeout: float = 300.0,
) -> None:
    """Read-only project status and entry report.

    Args:
        project_id: The upload/project id.
        api_url: Base URL of the NOMAD API.
        token_file: Optional token file path outside the repository.
        timeout: Socket timeout in seconds.
    """
    token = load_token(token_file)
    info = get_project_info(api_url, project_id, token, timeout=timeout)
    print(f"project:       {info.get('upload_name')} ({project_id})")
    print(f"published:     {info.get('published')}")
    print(f"process_status:{info.get('process_status')}")
    entry_report(api_url, project_id, token, timeout=timeout)


def main() -> None:
    """Command-line entry point for the safe upload tool."""
    parser = argparse.ArgumentParser(
        prog="python -m to_nomad.upload_to_nomad",
        description=(
            "Upload existing files into an existing NOMAD project. "
            "Dry-run by default; the real upload needs --yes. "
            f"The token is read from {TOKEN_ENV_VAR} or the token file "
            "(never from the command line)."
        ),
    )
    parser.add_argument("files", nargs="*", help="Local files to upload.")
    parser.add_argument("--project-id", required=True, help="Target project id.")
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help="NOMAD API base URL.")
    parser.add_argument("--token-file", default=None, help="Token file path outside the repository.")
    parser.add_argument("--yes", action="store_true", help="Perform the real upload (default is dry-run).")
    parser.add_argument("--allow-overwrite", action="store_true", help="Permit overwriting existing server files.")
    parser.add_argument("--wait", action="store_true", help="Wait for processing and report per-entry status.")
    parser.add_argument("--poll-interval", type=float, default=5.0, help="Seconds between status polls.")
    parser.add_argument("--timeout", type=float, default=300.0, help="Socket timeout in seconds.")
    parser.add_argument(
        "--status",
        action="store_true",
        help="Read-only: show project status and per-entry report, upload nothing.",
    )
    args = parser.parse_args()
    if args.status:
        status_only(args.project_id, api_url=args.api_url, token_file=args.token_file, timeout=args.timeout)
        return
    if not args.files:
        parser.error("no files given (use --status for a read-only report)")
    upload_files(
        args.files,
        args.project_id,
        api_url=args.api_url,
        token_file=args.token_file,
        allow_overwrite=args.allow_overwrite,
        dry_run=not args.yes,
        wait=args.wait,
        poll_interval=args.poll_interval,
        timeout=args.timeout,
    )


if __name__ == "__main__":
    main()
