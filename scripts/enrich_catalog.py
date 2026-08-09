#!/usr/bin/env python3
"""Add description-driven categories to an existing catalog without GitHub calls."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from catalog_lib import CATEGORY_DEFINITIONS, categorize_skill, write_catalog


def enrich(payload: dict) -> dict:
    counts: Counter[str] = Counter()
    for item in payload.get("items", []):
        repository = item.get("repository", {})
        category = categorize_skill(
            item.get("name", ""),
            item.get("description", ""),
            repository.get("topics", []),
            item.get("skill_path", ""),
        )
        item["category"] = category
        counts[category["id"]] += 1
    payload["categories"] = CATEGORY_DEFINITIONS
    payload.setdefault("stats", {})["categories"] = dict(sorted(counts.items()))
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="data/catalog.json")
    parser.add_argument("--output", default="data/catalog.json")
    parser.add_argument("--site-output", default="site/catalog.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    payload = enrich(payload)
    write_catalog(Path(args.output), payload)
    if args.site_output:
        write_catalog(Path(args.site_output), payload)
    print(json.dumps(payload["stats"]["categories"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
