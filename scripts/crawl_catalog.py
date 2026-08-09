#!/usr/bin/env python3
"""Build a normalized catalog of public Codex skills on GitHub."""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from catalog_lib import (
    SCHEMA_VERSION,
    build_catalog_item,
    isoformat_z,
    load_star_baselines,
    save_star_snapshot,
    utc_now,
    write_catalog,
)


API_ROOT = "https://api.github.com"
DEFAULT_QUERIES = [
    '"codex skills" in:name,description,readme fork:false archived:false',
    '"SKILL.md" codex in:readme fork:false archived:false',
    "topic:codex-skills fork:false archived:false",
    "topic:codex-skill fork:false archived:false",
]


class GitHubError(RuntimeError):
    pass


class GitHubClient:
    def __init__(self, token: str | None = None) -> None:
        self.token = token
        self.request_count = 0

    def get_json(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = path if path.startswith("https://") else f"{API_ROOT}{path}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "codex-skill-radar/0.1",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        for attempt in range(3):
            request = urllib.request.Request(url, headers=headers)
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    self.request_count += 1
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as error:
                body = error.read().decode("utf-8", errors="replace")
                if error.code in {502, 503, 504} and attempt < 2:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise GitHubError(f"GitHub API {error.code} for {url}: {body[:300]}") from error
            except urllib.error.URLError as error:
                if attempt < 2:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise GitHubError(f"GitHub API connection failed for {url}: {error.reason}") from error
        raise GitHubError(f"GitHub API request failed for {url}")


def discover_repositories(client: GitHubClient, queries: list[str], max_repositories: int) -> list[dict[str, Any]]:
    repositories: dict[str, dict[str, Any]] = {}
    per_query = max(10, min(100, max_repositories))
    for query in queries:
        payload = client.get_json(
            "/search/repositories",
            {"q": query, "sort": "stars", "order": "desc", "per_page": per_query},
        )
        for repository in payload.get("items", []):
            if repository.get("archived") or repository.get("fork"):
                continue
            repositories.setdefault(repository["full_name"], repository)
    return sorted(
        repositories.values(),
        key=lambda repository: int(repository.get("stargazers_count") or 0),
        reverse=True,
    )[:max_repositories]


def fetch_tree_paths(client: GitHubClient, repository: dict[str, Any]) -> list[str]:
    full_name = repository["full_name"]
    branch = urllib.parse.quote(repository.get("default_branch") or "main", safe="")
    payload = client.get_json(f"/repos/{full_name}/git/trees/{branch}", {"recursive": "1"})
    if payload.get("truncated"):
        print(f"warning: recursive tree was truncated for {full_name}", file=sys.stderr)
    return [entry["path"] for entry in payload.get("tree", []) if entry.get("type") == "blob"]


def fetch_text_file(client: GitHubClient, repository: dict[str, Any], path: str) -> str:
    full_name = repository["full_name"]
    encoded_path = urllib.parse.quote(path, safe="/")
    payload = client.get_json(
        f"/repos/{full_name}/contents/{encoded_path}",
        {"ref": repository.get("default_branch") or "main"},
    )
    content = payload.get("content")
    if payload.get("encoding") != "base64" or not isinstance(content, str):
        raise GitHubError(f"Unsupported content response for {full_name}/{path}")
    return base64.b64decode(content).decode("utf-8", errors="replace")


def build_catalog(args: argparse.Namespace) -> dict[str, Any]:
    token = os.environ.get("RADAR_GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    client = GitHubClient(token)
    now = utc_now()
    snapshot_dir = Path(args.snapshot_dir)
    baseline_7d, baseline_30d = load_star_baselines(snapshot_dir, now)
    repositories = discover_repositories(client, args.query or DEFAULT_QUERIES, args.max_repositories)

    items: list[dict[str, Any]] = []
    scanned = 0
    errors: list[str] = []
    for repository in repositories:
        full_name = repository["full_name"]
        try:
            paths = fetch_tree_paths(client, repository)
            skill_paths = [
                path
                for path in paths
                if path.endswith("SKILL.md")
                and "/node_modules/" not in f"/{path}/"
                and not path.startswith("vendor/")
            ][: args.max_skills_per_repository]
            if not skill_paths:
                continue
            scanned += 1
            stars = int(repository.get("stargazers_count") or 0)
            for skill_path in skill_paths:
                try:
                    skill_text = fetch_text_file(client, repository, skill_path)
                    items.append(
                        build_catalog_item(
                            repository,
                            skill_path,
                            skill_text,
                            paths,
                            stars - baseline_7d.get(full_name, stars),
                            stars - baseline_30d.get(full_name, stars),
                        )
                    )
                except GitHubError as error:
                    errors.append(str(error))
        except GitHubError as error:
            errors.append(str(error))

    items.sort(key=lambda item: (item["score"]["total"], item["repository"]["stars"]), reverse=True)
    save_star_snapshot(snapshot_dir, now, repositories)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": isoformat_z(now),
        "stats": {
            "repositories_discovered": len(repositories),
            "repositories_scanned": scanned,
            "skills_found": len(items),
            "github_requests": client.request_count,
            "partial_errors": len(errors),
        },
        "source": {
            "provider": "GitHub",
            "queries": args.query or DEFAULT_QUERIES,
        },
        "items": items,
        "warnings": errors[:20],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="data/catalog.json", help="Primary catalog JSON path")
    parser.add_argument("--site-output", default="site/catalog.json", help="Copy for the static site")
    parser.add_argument("--snapshot-dir", default="data/snapshots", help="Daily star snapshot directory")
    parser.add_argument("--max-repositories", type=int, default=60)
    parser.add_argument("--max-skills-per-repository", type=int, default=30)
    parser.add_argument("--query", action="append", help="Override repository search query; repeatable")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        catalog = build_catalog(args)
    except GitHubError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    write_catalog(Path(args.output), catalog)
    if args.site_output:
        write_catalog(Path(args.site_output), catalog)
    print(
        f"Wrote {len(catalog['items'])} skills from "
        f"{catalog['stats']['repositories_scanned']} repositories to {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
