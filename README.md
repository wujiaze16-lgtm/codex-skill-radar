# Codex Skill Radar

Discover what Codex skills are trending on GitHub, understand what they do,
inspect their risk signals, and install them through a Codex-native workflow.

## MVP components

- `scripts/crawl_catalog.py` searches public GitHub repositories and builds a
  normalized skill catalog.
- `site/` is a static GitHub Pages application for search, comparison, and
  installation handoff.
- `skills/skill-radar/` is the Codex skill that searches the catalog and runs
  the reviewed installer.
- `.github/workflows/catalog-and-pages.yml` refreshes data daily and deploys
  the site.

## Local development

Generate a catalog with an optional GitHub token:

```bash
export RADAR_GITHUB_TOKEN="your-read-only-token"
python3 scripts/crawl_catalog.py --output data/catalog.json --site-output site/catalog.json
```

Serve the site:

```bash
python3 -m http.server 8000 --directory site
```

Run tests and validation:

```bash
python3 -m unittest discover -s tests -v
python3 /path/to/skill-creator/scripts/quick_validate.py skills/skill-radar
python3 /path/to/plugin-creator/scripts/validate_plugin.py .
```

## GitHub configuration

Add a repository Actions secret named `GH_TOKEN` containing a fine-grained,
read-only GitHub token. In repository Settings, set Pages to use GitHub
Actions. The workflow falls back to the automatic `GITHUB_TOKEN` when the
custom secret is absent.

The installer downloads source archives but never executes third-party
scripts. It rejects symbolic links, traversal paths, archives above 50 MB, and
extractions above 100 MB or 5,000 files. Skill and plugin installation always
requires an explicit Codex confirmation.

## License

MIT
