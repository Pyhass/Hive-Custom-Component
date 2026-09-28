"""Check a release tag agrees with manifest.json before it reaches HACS users.

    python check_release.py <tag> <true|false: release is marked pre-release>

HACS installs by tag, so the tag must match the manifest version (compared as
versions, so tag 2026.3.1.b1 matches manifest 2026.3.1b1). A beta version must be
a GitHub pre-release, otherwise HACS offers it to every user.
"""

import json
from pathlib import Path
import sys

from packaging.version import InvalidVersion, Version

MANIFEST = (
    Path(__file__).resolve().parents[2] / "custom_components" / "hive" / "manifest.json"
)


def main(tag: str, prerelease: bool) -> int:
    manifest_version = json.loads(MANIFEST.read_text(encoding="utf-8"))["version"]
    errors = []
    try:
        tag_version = Version(tag)
    except InvalidVersion:
        print(f"::error::Tag {tag!r} is not a valid version")
        return 1

    if tag_version != Version(manifest_version):
        errors.append(
            f"Tag {tag} doesn't match manifest.json version {manifest_version}. "
            "Bump the manifest version before tagging."
        )
    if tag_version.is_prerelease and not prerelease:
        errors.append(
            f"{tag} is a beta version but the release isn't marked as a pre-release, "
            "so HACS will offer it to every user."
        )
    if prerelease and not tag_version.is_prerelease:
        errors.append(
            f"{tag} is marked as a pre-release but isn't a beta version "
            "(expected something like 2026.9.0b1)."
        )

    for error in errors:
        print(f"::error::{error}")
    if not errors:
        print(f"Tag {tag} matches manifest.json version {manifest_version}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2].lower() == "true"))
