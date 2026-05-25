"""Test PoolCop const helper functions."""

from custom_components.poolcop.const import (
    alert_display_name,
    alert_title_id,
    aux_display_name,
    aux_label_id,
)


async def test_alert_title_id_valid():
    """Extract numeric ID from alert_title_5."""
    assert alert_title_id("alert_title_5") == 5
    assert alert_title_id("alert_title_0") == 0


async def test_alert_title_id_non_numeric():
    """Non-numeric suffix returns None."""
    assert alert_title_id("alert_title_abc") is None


async def test_alert_title_id_wrong_prefix():
    """String without alert_title_ prefix returns None."""
    assert alert_title_id("PressureLow") is None
    assert alert_title_id("") is None


async def test_alert_display_name_known():
    """Known alert_title ID maps to name."""
    name = alert_display_name("alert_title_1")
    assert name == "Freezing Risk"


async def test_alert_display_name_unknown_id():
    """Unknown ID falls back to 'Alarm N'."""
    assert alert_display_name("alert_title_999") == "Alarm 999"


async def test_alert_display_name_raw_string():
    """Raw alarm string is returned as-is."""
    assert alert_display_name("PressureLowPump1") == "PressureLowPump1"


async def test_alert_display_name_empty():
    """Empty string returns 'Unknown Alarm'."""
    assert alert_display_name("") == "Unknown Alarm"


async def test_aux_label_id_valid():
    """Extract numeric ID from label_aux_17."""
    assert aux_label_id("label_aux_17") == 17
    assert aux_label_id("label_aux_0") == 0


async def test_aux_label_id_non_numeric():
    """Non-numeric suffix returns None."""
    assert aux_label_id("label_aux_xyz") is None


async def test_aux_label_id_wrong_prefix():
    """String without label_aux_ prefix returns None."""
    assert aux_label_id("TransferPump") is None
    assert aux_label_id("") is None


async def test_aux_display_name_known():
    """Known label ID maps to name."""
    name = aux_display_name("label_aux_0", 1)
    assert name == "Pool Light"


async def test_aux_display_name_unknown_id():
    """Unknown label ID falls back to 'Aux N'."""
    assert aux_display_name("label_aux_999", 5) == "Aux 5"


async def test_aux_display_name_raw_label():
    """Raw string label is returned as-is."""
    assert aux_display_name("TransferPump", 4) == "TransferPump"


async def test_aux_display_name_empty():
    """Empty label falls back to 'Aux N'."""
    assert aux_display_name("", 3) == "Aux 3"
