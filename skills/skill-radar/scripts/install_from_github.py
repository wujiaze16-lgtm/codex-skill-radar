#!/usr/bin/env python3
"""Inspect and install a Codex skill or plugin from a GitHub repository.

The installer downloads source archives and validates their structure. It never
executes files from the downloaded repository.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
import uuid
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
EXECUTABLE_SUFFIXES = {
    ".py", ".sh", ".bash", ".zsh", ".ps1", ".js", ".mjs", ".cjs",
    ".ts", ".tsx", ".rb", ".pl", ".lua", ".jar", ".exe",
}
MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024
MAX_EXTRACTED_BYTES = 100 * 1024 * 1024
MAX_EXTRACTED_FILES = 5000


class InstallError(RuntimeError):
    pass


def normalize_name(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    normalized = re.sub(r"-{2,}", "-", normalized)
    if not NAME_RE.fullmatch(normalized):
        raise InstallError(f"Invalid Codex skill name: {value}")
    return normalized


def validate_repo(value: str) -> str:
    if not REPOSITORY_RE.fullmatch(value):
        raise InstallError("Repository must be in owner/repository form.")
    return value


def validate_source_path(value: str) -> str:
    if value in {"", "."}:
        return "."
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise InstallError("Source path must be a relative repository path.")
    return path.as_posix()


def download_archive(repository: str, ref: str, output: Path) -> None:
    encoded_ref = urllib.parse.quote(ref, safe="")
    url = f"https://codeload.github.com/{repository}/zip/{encoded_ref}"
    headers = {"User-Agent": "codex-skill-radar/0.1"}
    token = os.environ.get("RADAR_GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=60) as response, output.open("wb") as handle:
            content_length = int(response.headers.get("Content-Length") or 0)
            if content_length > MAX_DOWNLOAD_BYTES:
                raise InstallError("Repository archive exceeds the 50 MB download limit.")
            downloaded = 0
            while chunk := response.read(1024 * 1024):
                downloaded += len(chunk)
                if downloaded > MAX_DOWNLOAD_BYTES:
                    raise InstallError("Repository archive exceeds the 50 MB download limit.")
                handle.write(chunk)
    except OSError as error:
        raise InstallError(f"Unable to download {repository}@{ref}: {error}") from error


def _archive_root(archive: zipfile.ZipFile) -> str:
    roots = {PurePosixPath(info.filename).parts[0] for info in archive.infolist() if info.filename and not info.is_dir()}
    if len(roots) != 1:
        raise InstallError("Archive has an unexpected root layout.")
    return roots.pop()


def _is_symlink(info: zipfile.ZipInfo) -> bool:
    mode = info.external_attr >> 16
    return (mode & 0o170000) == 0o120000


def extract_subtree(archive_path: Path, source_path: str, destination: Path) -> list[str]:
    """Extract only source_path while rejecting archive traversal and symlinks."""
    selected: list[str] = []
    extracted_bytes = 0
    prefix = "" if source_path == "." else f"{source_path.rstrip('/')}/"
    with zipfile.ZipFile(archive_path) as archive:
        root = _archive_root(archive)
        for info in archive.infolist():
            if info.is_dir() or not info.filename.startswith(f"{root}/"):
                continue
            if _is_symlink(info):
                raise InstallError(f"Archive contains a symbolic link: {info.filename}")
            relative = info.filename[len(root) + 1 :]
            if not relative.startswith(prefix):
                continue
            target_relative = relative[len(prefix) :] if prefix else relative
            if not target_relative:
                continue
            safe_path = PurePosixPath(target_relative)
            if safe_path.is_absolute() or ".." in safe_path.parts:
                raise InstallError(f"Unsafe archive path: {info.filename}")
            if len(selected) >= MAX_EXTRACTED_FILES:
                raise InstallError("Selected package exceeds the 5,000 file extraction limit.")
            extracted_bytes += info.file_size
            if extracted_bytes > MAX_EXTRACTED_BYTES:
                raise InstallError("Selected package exceeds the 100 MB extraction limit.")
            target = destination.joinpath(*safe_path.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)
            selected.append(safe_path.as_posix())
    if not selected:
        raise InstallError(f"No files found at repository path '{source_path}'.")
    return selected


def parse_frontmatter_name(skill_file: Path) -> str | None:
    lines = skill_file.read_text(encoding="utf-8", errors="replace").splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for line in lines[1:]:
        if line.strip() == "---":
            break
        match = re.match(r"^name:\s*(.+?)\s*$", line)
        if match:
            return match.group(1).strip().strip("\"'")
    return None


def inspect_payload(source: Path, mode: str) -> dict[str, Any]:
    files = [path.relative_to(source).as_posix() for path in source.rglob("*") if path.is_file()]
    has_scripts = any(
        path.startswith("scripts/")
        or "/scripts/" in path
        or PurePosixPath(path).suffix.lower() in EXECUTABLE_SUFFIXES
        for path in files
    )
    has_mcp = any(path.endswith(".mcp.json") or path.endswith("mcp.json") for path in files)
    has_hooks = any(path.startswith("hooks/") or "/hooks/" in path or path.endswith("hooks.json") for path in files)
    level = "high" if has_hooks and (has_scripts or has_mcp) else "medium" if (has_scripts or has_mcp or has_hooks) else "low"
    return {
        "mode": mode,
        "files": len(files),
        "has_scripts": has_scripts,
        "has_mcp": has_mcp,
        "has_hooks": has_hooks,
        "risk_level": level,
        "sample_files": files[:20],
    }


def validate_skill(source: Path, requested_name: str | None) -> str:
    skill_file = source / "SKILL.md"
    if not skill_file.is_file():
        raise InstallError("Selected path does not contain SKILL.md.")
    frontmatter_name = parse_frontmatter_name(skill_file)
    name = normalize_name(requested_name or frontmatter_name or source.name)
    if frontmatter_name and normalize_name(frontmatter_name) != name:
        raise InstallError("The requested install name does not match SKILL.md frontmatter.")
    return name


def validate_plugin(source: Path) -> tuple[str, dict[str, Any]]:
    manifest_path = source / ".codex-plugin" / "plugin.json"
    if not manifest_path.is_file():
        raise InstallError("Selected plugin path does not contain .codex-plugin/plugin.json.")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise InstallError("Plugin manifest is not valid JSON.") from error
    name = manifest.get("name")
    if not isinstance(name, str):
        raise InstallError("Plugin manifest does not define a name.")
    return normalize_name(name), manifest


def install_directory(source: Path, destination: Path) -> None:
    if destination.exists():
        raise InstallError(f"Destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.parent / f".{destination.name}.installing-{uuid.uuid4().hex[:8]}"
    try:
        shutil.copytree(source, temporary)
        temporary.replace(destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def update_personal_marketplace(plugin_name: str, marketplace_path: Path) -> str:
    if marketplace_path.exists():
        try:
            marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise InstallError(f"Marketplace JSON is invalid: {marketplace_path}") from error
    else:
        marketplace = {"name": "personal", "interface": {"displayName": "Personal"}, "plugins": []}
    if not isinstance(marketplace, dict) or not isinstance(marketplace.get("plugins"), list):
        raise InstallError("Marketplace must contain a plugins array.")
    marketplace_name = marketplace.get("name")
    if not isinstance(marketplace_name, str) or not marketplace_name:
        raise InstallError("Marketplace must have a non-empty name.")
    if any(isinstance(entry, dict) and entry.get("name") == plugin_name for entry in marketplace["plugins"]):
        raise InstallError(f"Marketplace already contains plugin '{plugin_name}'.")
    marketplace["plugins"].append(
        {
            "name": plugin_name,
            "source": {"source": "local", "path": f"./plugins/{plugin_name}"},
            "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
            "category": "Productivity",
        }
    )
    marketplace_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = marketplace_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(marketplace, indent=2) + "\n", encoding="utf-8")
    temporary.replace(marketplace_path)
    return marketplace_name


def run_activation(plugin_name: str, marketplace_name: str) -> None:
    try:
        subprocess.run(["codex", "plugin", "add", f"{plugin_name}@{marketplace_name}"], check=True)
    except FileNotFoundError as error:
        raise InstallError("Codex CLI was not found. Open Codex and add the plugin from the personal marketplace.") from error
    except subprocess.CalledProcessError as error:
        raise InstallError(f"Codex could not activate plugin '{plugin_name}': {error}") from error


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="GitHub repository as owner/repository")
    parser.add_argument("--path", required=True, help="Path to the skill or plugin in the repository")
    parser.add_argument("--ref", default="main", help="Git reference to download")
    parser.add_argument("--mode", choices=["auto", "skill", "plugin"], default="auto")
    parser.add_argument("--name", help="Required destination name override for a standalone skill")
    parser.add_argument("--inspect", action="store_true", help="Download and inspect only; do not install")
    parser.add_argument("--dry-run", action="store_true", help="Validate and report the destination without writing")
    parser.add_argument("--activate", action="store_true", help="Run codex plugin add after a plugin install")
    parser.add_argument("--dest", help="Standalone skill destination parent; defaults to $CODEX_HOME/skills")
    parser.add_argument("--plugin-dest", help="Plugin destination parent; defaults to ~/plugins")
    parser.add_argument("--marketplace-path", help="Personal marketplace JSON path")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable output")
    return parser.parse_args()


def emit(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    for key, value in payload.items():
        print(f"{key}: {value}")


def main() -> int:
    args = parse_args()
    try:
        repository = validate_repo(args.repo)
        source_path = validate_source_path(args.path)
        with tempfile.TemporaryDirectory(prefix="codex-skill-radar-") as temporary:
            temporary_path = Path(temporary)
            archive_path = temporary_path / "source.zip"
            source_path_on_disk = temporary_path / "payload"
            download_archive(repository, args.ref, archive_path)
            extract_subtree(archive_path, source_path, source_path_on_disk)

            detected_mode = "plugin" if (source_path_on_disk / ".codex-plugin" / "plugin.json").is_file() else "skill"
            mode = detected_mode if args.mode == "auto" else args.mode
            if mode == "skill":
                name = validate_skill(source_path_on_disk, args.name)
                destination_parent = Path(args.dest or Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "skills").expanduser()
                destination = destination_parent / name
            else:
                name, _manifest = validate_plugin(source_path_on_disk)
                destination_parent = Path(args.plugin_dest or Path.home() / "plugins").expanduser()
                destination = destination_parent / name

            inspection = inspect_payload(source_path_on_disk, mode)
            result: dict[str, Any] = {
                "repository": repository,
                "ref": args.ref,
                "path": source_path,
                "name": name,
                "destination": str(destination),
                "inspection": inspection,
            }
            if args.inspect or args.dry_run:
                result["status"] = "inspected" if args.inspect else "dry-run"
                emit(result, args.json)
                return 0

            install_directory(source_path_on_disk, destination)
            result["status"] = "installed"
            if mode == "plugin":
                marketplace_path = Path(args.marketplace_path or Path.home() / ".agents" / "plugins" / "marketplace.json").expanduser()
                try:
                    marketplace_name = update_personal_marketplace(name, marketplace_path)
                except Exception:
                    shutil.rmtree(destination, ignore_errors=True)
                    raise
                result["marketplace"] = str(marketplace_path)
                result["marketplace_name"] = marketplace_name
                if args.activate:
                    run_activation(name, marketplace_name)
                    result["activated"] = True
            emit(result, args.json)
            return 0
    except InstallError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
