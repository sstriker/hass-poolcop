"""Test PoolCop const helper functions."""

import pytest

from custom_components.poolcop.const import alarm_display_name, aux_display_name


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("PressureLowPump1", "Pressure Low Pump 1"),
        ("ORPLow", "ORP Low"),
        ("PHLow", "PH Low"),
        ("FCHigh", "FC High"),
        ("DisinfectionControlInefficient", "Disinfection Control Inefficient"),
        ("", ""),
    ],
)
async def test_alarm_display_name(code: str, expected: str) -> None:
    """Alarm codes are split into words."""
    assert alarm_display_name(code) == expected


async def test_aux_display_name_known() -> None:
    """Known labels map to a name."""
    assert aux_display_name("PoolLight", "", 1) == "Pool Light"
    assert aux_display_name("ReservedSpeedControl", "", 1) == "Speed Control"


async def test_aux_display_name_friendly_name() -> None:
    """A friendly name set on the PoolCop wins."""
    assert aux_display_name("PoolLight", "Terrace", 1) == "Terrace"


async def test_aux_display_name_unknown_label() -> None:
    """Unknown labels are shown as-is."""
    assert aux_display_name("SomethingNew", "", 4) == "SomethingNew"


async def test_aux_display_name_empty() -> None:
    """Without a label the channel is used."""
    assert aux_display_name("", "", 3) == "Aux 3"
