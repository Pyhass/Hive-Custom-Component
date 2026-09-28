"""Import every module of the component, including the core platforms it re-exports.

Catches Home Assistant removing or renaming something the component depends on.
"""

import importlib
from pathlib import Path
import sys
import traceback

ROOT = Path(__file__).resolve().parents[2]
COMPONENT = ROOT / "custom_components" / "hive"
sys.path.insert(0, str(ROOT))

failures = 0
for path in sorted(COMPONENT.glob("*.py")):
    module = f"custom_components.hive.{path.stem}".removesuffix(".__init__")
    try:
        importlib.import_module(module)
    except Exception:  # report every failure, not just the first
        failures += 1
        print(f"::error file={path.relative_to(ROOT)}::Failed to import {module}")
        traceback.print_exc()
    else:
        print(f"ok  {module}")

from homeassistant.const import __version__  # noqa: E402

print(f"Home Assistant {__version__}")
sys.exit(1 if failures else 0)
