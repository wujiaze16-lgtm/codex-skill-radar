---
name: skill-radar
description: Discover, compare, inspect, and install public Codex skills from the Codex Skill Radar GitHub catalog. Use when a user asks what Codex skills are popular or trending, wants a skill recommendation for a task, wants to compare GitHub skills or plugins, or asks to inspect and install a skill, Codex plugin, or skill-backed MCP integration from GitHub.
---

# Skill Radar

Use the bundled scripts for deterministic catalog search and installation. Treat popularity as a discovery signal, never as a security guarantee.

## Search

1. Run `scripts/query_catalog.py "<task or keywords>" --json` from this skill directory.
2. If the bundled catalog is empty or stale, rerun with `--catalog https://wujiaze16-lgtm.github.io/codex-skill-radar/catalog.json`. Network access may require user approval.
3. Present the best matches with:
   - the concrete task each skill enables;
   - repository, Stars, recent growth, and last activity;
   - whether it installs as a standalone skill or plugin;
   - scripts, MCP, hooks, license, and risk level.
4. Explain why each result matches the request. Do not claim a repository is endorsed by OpenAI unless the catalog source proves it.

Use `--type skill|plugin|mcp` and `--risk low|medium|high` when the request sets those constraints.

## Compare

Compare no more than five entries at once. Prioritize capability fit, maintenance, license, installation mode, and risk. Use the total score only as a tie-breaker because a high Star count does not establish quality or safety.

## Inspect Before Installing

Resolve the exact catalog entry or GitHub repository and path. Never install an ambiguous name.

For a standalone skill, run:

```bash
python3 scripts/install_from_github.py \
  --repo <owner/repository> \
  --path <path/to/skill> \
  --ref <ref> \
  --mode skill \
  --inspect --json
```

For a plugin, use the catalog's `install.plugin_path` as `--path` and run with `--mode plugin`. Use `.` when the plugin is at repository root.

Summarize the source, destination, file count, scripts, MCP configuration, hooks, and risk level. Ask for explicit confirmation before continuing. Do not combine inspection and installation into one unreviewed action.

## Install After Confirmation

Repeat the inspected command without `--inspect`. For plugins, add `--activate` so the installer registers it through the personal marketplace and activates it with the Codex CLI.

The installer must:

- abort when the destination already exists;
- install standalone skills under `$CODEX_HOME/skills` or `~/.codex/skills`;
- install plugins under `~/plugins` and register the standard personal marketplace;
- download and copy files without executing third-party scripts;
- reject archive traversal, symbolic links, invalid names, missing manifests, and oversized archives.

After success, tell the user the installed skill will be available on the next turn. For a plugin, recommend a new Codex task so its skills and MCP tools are picked up.

## Direct GitHub Requests

When the user provides a GitHub URL that is not in the catalog, derive the repository, ref, and skill path, then follow the same inspection and confirmation workflow. Require `SKILL.md` for standalone skill installation and `.codex-plugin/plugin.json` for plugin installation.
