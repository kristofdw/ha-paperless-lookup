"""Tests that the version numbers of a release agree."""

import json
from pathlib import Path
import re
import tomllib

ROOT = Path(__file__).parents[1]
MANIFEST = ROOT / "custom_components" / "paperless_lookup" / "manifest.json"


def _manifest_version() -> str:
    version: str = json.loads(MANIFEST.read_text(encoding="utf-8"))["version"]
    return version


def test_versions_agree() -> None:
    """Test that the manifest, pyproject.toml and the frontend package have the same version."""
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    package = json.loads((ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))

    assert re.fullmatch(r"\d+\.\d+\.\d+", _manifest_version())
    assert pyproject["project"]["version"] == _manifest_version()
    assert package["version"] == _manifest_version()


def test_changelog_has_version() -> None:
    """Test that the changelog has a section for the version in the manifest."""
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    assert f"## [{_manifest_version()}] - " in changelog
