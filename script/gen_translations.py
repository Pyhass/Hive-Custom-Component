"""Generate translations/en.json from strings.json.

strings.json uses Home Assistant's [%key:...%] references, which only core resolves.
Custom components load translations/en.json as-is, so the references have to be
expanded here. Needs homeassistant installed (it provides the common:: strings).

    python script/gen_translations.py          # rewrite translations/en.json
    python script/gen_translations.py --check  # exit 1 if en.json is out of date
"""

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any

import homeassistant

COMPONENT = Path(__file__).resolve().parent.parent / "custom_components" / "hive"
STRINGS = COMPONENT / "strings.json"
EN_JSON = COMPONENT / "translations" / "en.json"
REFERENCE = re.compile(r"\[%key:([a-z0-9_:]+)%\]")


def _lookup(tree: dict[str, Any], path: list[str]) -> str:
    node: Any = tree
    for part in path:
        node = node[part]
    if not isinstance(node, str):
        raise TypeError(f"{'::'.join(path)} is not a string")
    return node


def generate() -> dict[str, Any]:
    """Return strings.json with every [%key:...%] reference expanded."""
    strings = json.loads(STRINGS.read_text(encoding="utf-8"))
    core = json.loads(
        (Path(homeassistant.__file__).parent / "strings.json").read_text(
            encoding="utf-8"
        )
    )
    trees = {"common": core["common"], "component::hive": strings}

    def resolve(value: str) -> str:
        def replace(match: re.Match[str]) -> str:
            key = match.group(1)
            if key.startswith("component::hive::"):
                path = key.removeprefix("component::hive::").split("::")
                return resolve(_lookup(strings, path))
            if key.startswith("common::"):
                return _lookup(trees["common"], key.split("::")[1:])
            raise KeyError(f"can't resolve reference {key}")

        return REFERENCE.sub(replace, value)

    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            return {key: walk(value) for key, value in node.items()}
        return resolve(node)

    return walk(strings)


def render() -> str:
    """Return en.json content as it should be on disk."""
    return json.dumps(generate(), indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    """Write or check translations/en.json."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="only check, don't write")
    args = parser.parse_args()

    expected = render()
    if args.check:
        if EN_JSON.read_text(encoding="utf-8") != expected:
            print(f"{EN_JSON} is out of date, run: python script/gen_translations.py")
            return 1
        return 0

    EN_JSON.write_text(expected, encoding="utf-8")
    print(f"Wrote {EN_JSON}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
