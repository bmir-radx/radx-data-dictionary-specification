"""Bump the shared version across all packages and pin internal deps to the tag.

All six packages share one version. Given a bump *level* (``major`` / ``minor``
/ ``patch``), this reads the current shared version from the core package,
computes the next version, and rewrites every ``pyproject.toml``'s
``version = "..."`` line. It also pins each internal ``dd-* @ git+...``
dependency to the matching release tag (``...@v<version>#subdirectory=...``),
so a ``pipx upgrade`` of a downstream package pulls the exact matching build of
its siblings.

Usage: ``python scripts/bump_version.py <level>``  (level: major|minor|patch).
Prints the new version. The release workflow derives the level from the merged
PR's labels and invokes this.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ["core", "linkml", "api", "printer", "validator", "redcap"]
_VERSION_RE = re.compile(r'^version = "(\d+)\.(\d+)\.(\d+)"$', re.M)
# Internal dependency URLs are pinned to the release tag on bump. This regex
# matches a dd-* git dependency with an optional existing @<ref> before the
# #subdirectory fragment, so re-running is idempotent.
_DEP_RE = re.compile(
    r'("dd-[a-z]+ @ git\+https://github\.com/bmir-radx/'
    r'radx-data-dictionary-specification\.git)(@[^#"]+)?(#subdirectory=[a-z]+")'
)


def _current_version() -> tuple[int, int, int]:
    text = (ROOT / "core" / "pyproject.toml").read_text()
    match = _VERSION_RE.search(text)
    if match is None:
        raise SystemExit("could not find a version = \"X.Y.Z\" line in core/pyproject.toml")
    return tuple(int(g) for g in match.groups())  # type: ignore[return-value]


def _next_version(level: str) -> str:
    major, minor, patch = _current_version()
    if level == "major":
        major, minor, patch = major + 1, 0, 0
    elif level == "minor":
        minor, patch = minor + 1, 0
    elif level == "patch":
        patch += 1
    else:
        raise SystemExit(f"unknown bump level {level!r} (expected major|minor|patch)")
    return f"{major}.{minor}.{patch}"


def _bump_pyproject(path: Path, version: str) -> None:
    text = path.read_text()
    text, n = _VERSION_RE.subn(f'version = "{version}"', text, count=1)
    if n != 1:
        raise SystemExit(f"{path}: expected exactly one version line, changed {n}")
    text = _DEP_RE.sub(rf"\1@v{version}\3", text)
    path.write_text(text)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        raise SystemExit("usage: bump_version.py <major|minor|patch>")
    version = _next_version(argv[1])
    for name in PACKAGES:
        _bump_pyproject(ROOT / name / "pyproject.toml", version)
    print(version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
