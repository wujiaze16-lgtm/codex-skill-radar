from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from catalog_lib import (  # noqa: E402
    build_catalog_item,
    classify_capabilities,
    load_star_baselines,
    parse_frontmatter,
)


class CatalogLibTests(unittest.TestCase):
    def test_parse_frontmatter_supports_folded_description(self) -> None:
        metadata = parse_frontmatter(
            """---
name: browser-audit
description: >
  Inspect a web app and
  report accessibility issues.
---
# Browser Audit
"""
        )
        self.assertEqual(metadata["name"], "browser-audit")
        self.assertEqual(metadata["description"], "Inspect a web app and report accessibility issues.")

    def test_capability_classification_marks_plugin_mcp_and_scripts(self) -> None:
        types, risk = classify_capabilities(
            [
                ".codex-plugin/plugin.json",
                ".mcp.json",
                "skills/browser/SKILL.md",
                "skills/browser/scripts/run.py",
            ],
            "",
        )
        self.assertEqual(types, ["skill", "plugin", "mcp"])
        self.assertEqual(risk["level"], "medium")
        self.assertTrue(risk["has_scripts"])
        self.assertTrue(risk["has_mcp"])

    def test_build_catalog_item_uses_plugin_install_mode(self) -> None:
        repository = {
            "name": "useful-plugin",
            "full_name": "example/useful-plugin",
            "html_url": "https://github.com/example/useful-plugin",
            "description": "A useful Codex plugin for browser testing.",
            "default_branch": "main",
            "stargazers_count": 120,
            "forks_count": 10,
            "pushed_at": datetime.now(timezone.utc).isoformat(),
            "language": "Python",
            "license": {"spdx_id": "MIT"},
            "topics": ["codex-skills"],
            "archived": False,
            "owner": {"login": "example", "avatar_url": "https://avatars.example/user.png"},
        }
        item = build_catalog_item(
            repository,
            "skills/browser-audit/SKILL.md",
            "---\nname: browser-audit\ndescription: Audit browser accessibility and report actionable issues.\n---\n",
            [".codex-plugin/plugin.json", "skills/browser-audit/SKILL.md"],
            8,
            20,
        )
        self.assertEqual(item["install"]["mode"], "plugin")
        self.assertEqual(item["install"]["plugin_path"], "")
        self.assertIn("plugin", item["types"])
        self.assertEqual(item["score"]["star_delta_7d"], 8)

    def test_load_star_baselines_chooses_older_snapshot(self) -> None:
        now = datetime(2026, 8, 9, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for days, stars in [(8, 10), (31, 4), (2, 15)]:
                created = now - timedelta(days=days)
                payload = {"generated_at": created.isoformat(), "repositories": {"a/b": stars}}
                (root / f"{created.date()}.json").write_text(json.dumps(payload), encoding="utf-8")
            baseline_7d, baseline_30d = load_star_baselines(root, now)
        self.assertEqual(baseline_7d["a/b"], 10)
        self.assertEqual(baseline_30d["a/b"], 4)


if __name__ == "__main__":
    unittest.main()
