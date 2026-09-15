"""Consistency checks for translations and icons."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from custom_components.prociv_madeira.alerts import ALERT_SEVERITY
from custom_components.prociv_madeira.alerts import REGION_KEYS

COMPONENT = Path(__file__).parent.parent / "custom_components" / "prociv_madeira"


def _load(relative_path: str) -> dict[str, Any]:
    return json.loads((COMPONENT / relative_path).read_text(encoding="utf-8"))


def _leaves(data: dict[str, Any], prefix: str = "") -> dict[str, str]:
    """Flatten nested translations into {"a.b.c": text}."""
    leaves: dict[str, str] = {}
    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            leaves.update(_leaves(value, path))
        else:
            leaves[path] = value
    return leaves


def test_portuguese_translates_every_english_string() -> None:
    english = _leaves(_load("translations/en.json"))
    portuguese = _leaves(_load("translations/pt.json"))

    assert portuguese.keys() == english.keys()


def test_placeholders_match_between_languages() -> None:
    english = _leaves(_load("translations/en.json"))
    portuguese = _leaves(_load("translations/pt.json"))

    for path, text in english.items():
        expected = set(re.findall(r"{\w+}", text))
        assert set(re.findall(r"{\w+}", portuguese[path])) == expected, path


def test_translation_keys_used_in_the_code_exist() -> None:
    source = "\n".join(path.read_text() for path in COMPONENT.glob("*.py"))
    english = _load("translations/en.json")

    config_errors = set(re.findall(r'errors\["base"\] = "(\w+)"', source))
    exceptions = set(re.findall(r'translation_key="(\w+)"', source))

    assert config_errors
    assert config_errors <= english["config"]["error"].keys()
    assert exceptions
    assert exceptions <= english["exceptions"].keys()


def test_every_alert_level_has_a_state_name() -> None:
    level_sensors = [*REGION_KEYS.values(), "worst_alert"]

    for language in ("en", "pt"):
        sensors = _load(f"translations/{language}.json")["entity"]["sensor"]
        for key in level_sensors:
            assert sorted(sensors[key]["state"]) == sorted(ALERT_SEVERITY), (
                language,
                key,
            )


def test_every_translated_entity_has_icons() -> None:
    icons = _load("icons.json")["entity"]
    names = _load("translations/en.json")["entity"]

    assert {platform: sorted(keys) for platform, keys in icons.items()} == {
        platform: sorted(keys) for platform, keys in names.items()
    }
