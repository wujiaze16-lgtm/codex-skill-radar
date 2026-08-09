#!/usr/bin/env python3
"""Search and rank entries in the Codex Skill Radar catalog."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_URL = "https://wujiaze16-lgtm.github.io/codex-skill-radar/catalog.json"


def load_catalog(source: str | None) -> dict[str, Any]:
    bundled = Path(__file__).parents[3] / "data" / "catalog.json"
    if source:
        if source.startswith(("https://", "http://")):
            request = urllib.request.Request(source, headers={"User-Agent": "codex-skill-radar/0.1"})
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        return json.loads(Path(source).expanduser().read_text(encoding="utf-8"))
    if bundled.is_file():
        return json.loads(bundled.read_text(encoding="utf-8"))
    return load_catalog(DEFAULT_URL)


def search(items: list[dict[str, Any]], query: str, entry_type: str | None, risk: str | None) -> list[dict[str, Any]]:
    terms = query.lower().split()
    matches: list[dict[str, Any]] = []
    for item in items:
        if entry_type and entry_type not in item.get("types", []):
            continue
        if risk and item.get("risk", {}).get("level") != risk:
            continue
        searchable = " ".join(
            [
                item.get("name", ""),
                item.get("description", ""),
                item.get("repository", {}).get("full_name", ""),
                " ".join(item.get("repository", {}).get("topics", [])),
            ]
        ).lower()
        if all(term in searchable for term in terms):
            matches.append(item)
    return sorted(matches, key=lambda item: item.get("score", {}).get("total", 0), reverse=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", nargs="?", default="", help="Words to match")
    parser.add_argument("--catalog", help="Catalog path or URL")
    parser.add_argument("--type", choices=["skill", "plugin", "mcp"])
    parser.add_argument("--risk", choices=["low", "medium", "high"])
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        catalog = load_catalog(args.catalog)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"error: unable to load catalog: {error}", file=sys.stderr)
        return 1
    items = search(catalog.get("items", []), args.query, args.type, args.risk)[: max(1, args.limit)]
    if args.json:
        print(json.dumps({"generated_at": catalog.get("generated_at"), "items": items}, indent=2, ensure_ascii=False))
        return 0
    if not items:
        print("No matching skills found.")
        return 0
    print("SCORE  STARS  RISK    TYPES          SKILL / REPOSITORY")
    for item in items:
        types = ",".join(item.get("types", []))
        repository = item.get("repository", {})
        print(
            f"{item.get('score', {}).get('total', 0):>5}  "
            f"{repository.get('stars', 0):>5}  "
            f"{item.get('risk', {}).get('level', '?'):<7} "
            f"{types:<14} {item.get('name')} / {repository.get('full_name')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
