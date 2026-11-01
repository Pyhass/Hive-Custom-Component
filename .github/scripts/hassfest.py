"""Run hassfest, allowing only the errors this repo causes on purpose.

    python .github/scripts/hassfest.py

This component replaces Home Assistant core's hive integration and may pin a
different pyhive-integration than core does (see CLAUDE.md). hassfest checks a
custom integration's requirements against every core integration's pins, including
core hive's own, so it reports that difference as an error. Those errors are shown
as warnings here. Any other error, or a failure with no error lines, still fails.
"""

from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
IMAGE = "ghcr.io/home-assistant/hassfest"

# Packages whose core pin belongs to the core integration this repo replaces.
OVERRIDDEN_PACKAGES = {"pyhive-integration"}

# The two hassfest errors about differing from a core integration's pin. Errors
# about Home Assistant's own dependencies or package constraints are not here:
# those can break the whole installation, so they must fail.
ALLOWED = re.compile(
    r"\[REQUIREMENTS\] Requirement (?P<package>[A-Za-z0-9][A-Za-z0-9._-]*)\S* "
    r"(pins a package Home Assistant depends on"
    r"|is incompatible with \S+, which Home Assistant depends on\.)"
)


def is_allowed(line: str) -> bool:
    """Return True if a hassfest error line is an expected override difference."""
    match = ALLOWED.search(line)
    return bool(match) and match["package"].lower() in OVERRIDDEN_PACKAGES


def main() -> int:
    result = subprocess.run(
        ["docker", "run", "--rm", "-v", f"{ROOT}:/github/workspace", IMAGE],
        capture_output=True,
        text=True,
        check=False,
    )
    output = result.stdout + result.stderr
    print(output)
    if result.returncode == 0:
        return 0

    errors = [line for line in output.splitlines() if "[ERROR]" in line]
    if not errors:
        print(
            f"::error::hassfest exited with {result.returncode} without an error line"
        )
        return result.returncode

    blocking = [line for line in errors if not is_allowed(line)]
    for line in errors:
        level = "error" if line in blocking else "warning"
        print(f"::{level}::{line.lstrip('* ').strip()}")
    if blocking:
        return 1
    print("Only expected differences from core hive's requirements; passing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
