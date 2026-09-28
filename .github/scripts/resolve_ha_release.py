"""Find the newest Home Assistant release in a channel and its test plugin build.

Prints GitHub Actions outputs:
    homeassistant=<version>
    test_plugin=<pytest-homeassistant-custom-component version pinned to it>
    skip=true|false

    python resolve_ha_release.py stable|beta
"""

import json
import sys
from urllib.request import urlopen

from packaging.version import Version

PYPI = "https://pypi.org/pypi/{}/json"
TEST_PLUGIN = "pytest-homeassistant-custom-component"
# How many recent test plugin releases to search for a matching HA pin.
SEARCH_DEPTH = 40


def _get(url: str) -> dict:
    with urlopen(url, timeout=30) as response:
        return json.load(response)


def _newest(releases: dict[str, list], *, prerelease: bool) -> Version | None:
    versions = [
        Version(v)
        for v, files in releases.items()
        if files and not all(f.get("yanked") for f in files)
    ]
    matching = [v for v in versions if v.is_prerelease == prerelease]
    return max(matching, default=None)


def _test_plugin_for(ha_version: Version) -> str | None:
    releases = _get(PYPI.format(TEST_PLUGIN))["releases"]
    recent = sorted(
        (v for v, files in releases.items() if files),
        key=lambda v: max(f["upload_time"] for f in releases[v]),
        reverse=True,
    )[:SEARCH_DEPTH]
    pin = f"homeassistant=={ha_version}"
    for version in recent:
        info = _get(PYPI.format(f"{TEST_PLUGIN}/{version}"))["info"]
        if pin in (info["requires_dist"] or []):
            return version
    return None


def main(channel: str) -> None:
    releases = _get(PYPI.format("homeassistant"))["releases"]
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

    plugin = _test_plugin_for(target)
    if plugin is None:
        # Fail loudly: the plugin normally ships within a day of an HA release.
        sys.exit(f"No {TEST_PLUGIN} release pins homeassistant=={target} yet")

    print(f"homeassistant={target}")
    print(f"test_plugin={plugin}")
    print("skip=false")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "stable")
