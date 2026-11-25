"""Check icons.json against the translated entities."""

import json
from pathlib import Path

COMPONENT = Path(__file__).parent.parent / "custom_components" / "poolcop"


def test_icons_match_translation_keys():
    """Every icon belongs to a translated entity or action."""
    icons = json.loads((COMPONENT / "icons.json").read_text())
    strings = json.loads((COMPONENT / "strings.json").read_text())
    for platform, entities in icons["entity"].items():
        assert set(entities) <= set(strings["entity"][platform]), platform
        for icon in entities.values():
            assert icon["default"].startswith("mdi:")
    assert set(icons["services"]) == set(strings["services"])


def test_enum_sensor_states_are_translated():
    """Every enum sensor option has a state translation in every language."""
    from homeassistant.components.sensor import SensorDeviceClass

    from custom_components.poolcop.sensor import (
        SENSORS,
        SETTINGS_SENSORS,
        TIMER_SENSORS,
    )

    languages = {
        path.name: json.loads(path.read_text())
        for path in [
            COMPONENT / "strings.json",
            *(COMPONENT / "translations").glob("*.json"),
        ]
    }
    enums = [
        d
        for d in (*SENSORS, *SETTINGS_SENSORS, *TIMER_SENSORS)
        if d.device_class == SensorDeviceClass.ENUM
    ]
    assert enums
    for name, strings in languages.items():
        sensors = strings["entity"]["sensor"]
        for description in enums:
            states = sensors[description.translation_key].get("state", {})
            assert set(description.options) == set(states), (name, description.key)
