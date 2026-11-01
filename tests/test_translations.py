"""Check the translation files stay in step with the code."""

import json
from pathlib import Path
import re
import sys

import yaml

ROOT = Path(__file__).parent.parent
COMPONENT = ROOT / "custom_components" / "hive"
EN_JSON = COMPONENT / "translations" / "en.json"

sys.path.insert(0, str(ROOT / "script"))
import gen_translations  # noqa: E402


def _en() -> dict:
    return json.loads(EN_JSON.read_text(encoding="utf-8"))


def test_en_json_is_generated_from_strings_json() -> None:
    """translations/en.json matches strings.json with references expanded.

    Fix with: python script/gen_translations.py
    """
    assert EN_JSON.read_text(encoding="utf-8") == gen_translations.render()


def test_config_flow_errors_are_translated() -> None:
    """Every error the config flow can set has English text."""
    source = (COMPONENT / "config_flow.py").read_text(encoding="utf-8")
    used = set(re.findall(r'errors\["base"\] = "([a-z0-9_]+)"', source))

    assert used
    assert used - set(_en()["config"]["error"]) == set()


def test_services_are_translated() -> None:
    """Every service in services.yaml has a name in en.json."""
    services = yaml.safe_load((COMPONENT / "services.yaml").read_text(encoding="utf-8"))

    assert set(services) - set(_en().get("services", {})) == set()
