from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).parents[1]
INSTALLER_PATH = ROOT / "skills" / "skill-radar" / "scripts" / "install_from_github.py"
SPEC = importlib.util.spec_from_file_location("radar_installer", INSTALLER_PATH)
installer = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(installer)


class InstallerTests(unittest.TestCase):
    def make_archive(self, path: Path, members: dict[str, str]) -> None:
        with zipfile.ZipFile(path, "w") as archive:
            for name, content in members.items():
                archive.writestr(name, content)

    def test_extract_and_validate_skill(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "source.zip"
            self.make_archive(
                archive,
                {
                    "repo-sha/skills/demo/SKILL.md": "---\nname: demo\ndescription: Demo.\n---\n",
                    "repo-sha/skills/demo/scripts/run.py": "print('demo')\n",
                },
            )
            destination = root / "payload"
            files = installer.extract_subtree(archive, "skills/demo", destination)
            self.assertIn("SKILL.md", files)
            self.assertEqual(installer.validate_skill(destination, None), "demo")
            self.assertEqual(installer.inspect_payload(destination, "skill")["risk_level"], "medium")

    def test_extract_rejects_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "source.zip"
            self.make_archive(archive, {"repo-sha/skills/demo/../../escape.txt": "unsafe"})
            with self.assertRaises(installer.InstallError):
                installer.extract_subtree(archive, "skills/demo", root / "payload")

    def test_extract_enforces_file_limit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "source.zip"
            self.make_archive(
                archive,
                {
                    "repo-sha/skills/demo/SKILL.md": "---\nname: demo\n---\n",
                    "repo-sha/skills/demo/extra.txt": "extra",
                },
            )
            original_limit = installer.MAX_EXTRACTED_FILES
            installer.MAX_EXTRACTED_FILES = 1
            try:
                with self.assertRaises(installer.InstallError):
                    installer.extract_subtree(archive, "skills/demo", root / "payload")
            finally:
                installer.MAX_EXTRACTED_FILES = original_limit

    def test_marketplace_creation_uses_required_policy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            marketplace = Path(directory) / ".agents" / "plugins" / "marketplace.json"
            name = installer.update_personal_marketplace("demo-plugin", marketplace)
            payload = json.loads(marketplace.read_text(encoding="utf-8"))
            self.assertEqual(name, "personal")
            self.assertEqual(payload["plugins"][0]["source"]["path"], "./plugins/demo-plugin")
            self.assertEqual(payload["plugins"][0]["policy"]["installation"], "AVAILABLE")
            with self.assertRaises(installer.InstallError):
                installer.update_personal_marketplace("demo-plugin", marketplace)

    def test_root_python_file_is_an_executable_signal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "SKILL.md").write_text("---\nname: demo\n---\n", encoding="utf-8")
            (root / "runner.py").write_text("print('demo')\n", encoding="utf-8")
            inspection = installer.inspect_payload(root, "skill")
            self.assertTrue(inspection["has_scripts"])
            self.assertEqual(inspection["risk_level"], "medium")

    def test_install_directory_refuses_existing_destination(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            destination = root / "skills" / "demo"
            source.mkdir()
            destination.mkdir(parents=True)
            (source / "SKILL.md").write_text("demo", encoding="utf-8")
            with self.assertRaises(installer.InstallError):
                installer.install_directory(source, destination)


if __name__ == "__main__":
    unittest.main()
