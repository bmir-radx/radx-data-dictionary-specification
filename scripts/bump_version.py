"""Bump the shared version across all packages and pin internal deps to the tag.

All six packages share one version. Given the new version, this rewrites every
``pyproject.toml``'s ``version = "..."`` line and pins each internal
``dd-* @ git+...`` dependency to the matching release tag
(``...@v<version>#subdirectory=...``), so a ``pipx upgrade`` of a downstream
package pulls the exact matching build of its siblings.

Usage: ``python scripts/bump_version.py <new-version>``  (e.g. 0.2.0)
The GitHub release workflow computes the next version and invokes this.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ["core", "linkml", "api", "printer", "validator", "redcap"]
# Internal dependency URLs are pinned to the release tag on bump. This regex
# matches a dd-* git dependency with an optional existing @<ref> before the
# #subdirectory fragment, so re-running is idempotent.
_DEP_RE = re.compile(
    r'("dd-[a-z]+ @ git\+https://github\.com/bmir-radx/'
    r'radx-data-dictionary-specification\.git)(@[^#"]+)?(#subdirectory=[a-z]+")'
)


def _bump_pyproject(path: Path, version: str) -> None:
    text = path.read_text()
    text, n = re.subn(r'^version = "[^"]*"', f'version = "{version}"', text, count=1, flags=re.M)
    if n != 1:
        raise SystemExit(f"{path}: expected exactly one version line, changed {n}")
    text = _DEP_RE.sub(rf"\1@v{version}\3", text)
    path.write_text(text)


def main(argv: list[str]) -> int:
    if len(argv) != 2 or not re.fullmatch(r"\d+\.\d+\.\d+", argv[1]):
        raise SystemExit("usage: bump_version.py <major.minor.patch>")
    version = argv[1]
    for name in PACKAGES:
        _bump_pyproject(ROOT / name / "pyproject.toml", version)
    print(f"bumped all packages to {version}; internal deps pinned to v{version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
