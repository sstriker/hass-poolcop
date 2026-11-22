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
