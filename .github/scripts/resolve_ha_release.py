"""Find the newest Home Assistant release in a channel and check its test package.

pytest-homeassistant is versioned with Home Assistant (pytest-homeassistant==X
pins homeassistant==X), so the test package to install has the same version.

Prints GitHub Actions outputs:
    homeassistant=<version>
    test_package=<pytest-homeassistant version to install>
    skip=true|false

    python resolve_ha_release.py stable|beta
"""

import json
import sys
from urllib.request import urlopen

from packaging.version import Version

PYPI = "https://pypi.org/pypi/{}/json"
TEST_PACKAGE = "pytest-homeassistant"


def _get(url: str) -> dict:
    with urlopen(url, timeout=30) as response:
        return json.load(response)


def _published(releases: dict[str, list]) -> set[Version]:
    return {
        Version(v)
        for v, files in releases.items()
        if files and not all(f.get("yanked") for f in files)
    }


def _newest(versions: set[Version], *, prerelease: bool) -> Version | None:
    return max((v for v in versions if v.is_prerelease == prerelease), default=None)


def main(channel: str) -> None:
    releases = _published(_get(PYPI.format("homeassistant"))["releases"])
    stable = _newest(releases, prerelease=False)
    if channel == "stable":
        target = stable
    elif channel == "beta":
        beta = _newest(releases, prerelease=True)
        target = beta if beta and stable and beta > stable else None
    else:
        sys.exit(f"unknown channel {channel!r}, expected stable or beta")

    if target is None:
        print(
            f"::notice::No Home Assistant {channel} release newer than stable",
            file=sys.stderr,
        )
        print("skip=true")
        return

    if target not in _published(_get(PYPI.format(TEST_PACKAGE))["releases"]):
        # Fail loudly: Home Assistant publishes both together, so this is rare.
        sys.exit(f"No {TEST_PACKAGE}=={target} on PyPI yet")

    print(f"homeassistant={target}")
    print(f"test_package={target}")
    print("skip=false")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "stable")
