"""Test PoolCop constants and helper functions."""

from custom_components.poolcop.const import (
    ALARM_NAMES,
    AUX_LABEL_NAMES,
    alert_display_name,
    alert_title_id,
    aux_display_name,
    aux_label_id,
)


def test_aux_label_id_valid():
    """Test extracting numeric ID from label_aux_N strings."""
    assert aux_label_id("label_aux_0") == 0
    assert aux_label_id("label_aux_17") == 17
    assert aux_label_id("label_aux_27") == 27


def test_aux_label_id_invalid():
    """Test aux_label_id with non-matching strings."""
    assert aux_label_id("") is None
    assert aux_label_id("Pool Light") is None
    assert aux_label_id("label_aux_") is None
    assert aux_label_id("label_aux_abc") is None
    assert aux_label_id(None) is None


def test_aux_display_name_from_label_id():
    """Test resolving label_aux_N to display names."""
    assert aux_display_name("label_aux_0", 1) == "Pool Light"
    assert aux_display_name("label_aux_16", 5) == "Waste Valve"
    assert aux_display_name("label_aux_18", 6) == "ORP Control"
    assert aux_display_name("label_aux_15", 2) == "Available"


def test_aux_display_name_plain_text():
    """Test that plain text labels pass through unchanged."""
    assert aux_display_name("Pool Light", 1) == "Pool Light"
    assert aux_display_name("Transf Pump", 4) == "Transf Pump"
    assert aux_display_name("Used for Speed Control", 1) == "Used for Speed Control"


def test_aux_display_name_fallback():
    """Test fallback to Aux N for unknown or missing labels."""
    assert aux_display_name("label_aux_999", 7) == "Aux 7"
    assert aux_display_name("", 3) == "Aux 3"
    assert aux_display_name(None, 5) == "Aux 5"


def test_alert_title_id_valid():
    """Test extracting numeric ID from alert_title_N strings."""
    assert alert_title_id("alert_title_0") == 0
    assert alert_title_id("alert_title_5") == 5
    assert alert_title_id("alert_title_29") == 29
    assert alert_title_id("alert_title_69") == 69


def test_alert_title_id_invalid():
    """Test alert_title_id with non-matching strings."""
    assert alert_title_id("") is None
    assert alert_title_id("pH Low") is None
    assert alert_title_id("alert_title_") is None
    assert alert_title_id("alert_title_abc") is None
    assert alert_title_id(None) is None


def test_alert_display_name_from_id():
    """Test resolving alert_title_N to display names."""
    assert alert_display_name("alert_title_5") == "pH Low"
    assert alert_display_name("alert_title_29") == "Water Level Not Optimum"
    assert alert_display_name("alert_title_1") == "Freezing Risk"
    assert alert_display_name("alert_title_20") == "Battery Low"
    assert alert_display_name("alert_title_42") == "Water No Flow Detected"


def test_alert_display_name_plain_text():
    """Test that plain text alert names pass through."""
    assert alert_display_name("pH Low") == "pH Low"
    assert alert_display_name("Some Alarm") == "Some Alarm"


def test_alert_display_name_fallback():
    """Test fallback for unknown alarm IDs."""
    assert alert_display_name("alert_title_999") == "Alarm 999"
    assert alert_display_name("") == "Unknown Alarm"
    assert alert_display_name(None) == "Unknown Alarm"


def test_alarm_names_completeness():
    """Test that all alarm IDs 0-69 are mapped."""
    for i in range(70):
        assert i in ALARM_NAMES, f"Alarm ID {i} missing from ALARM_NAMES"


def test_aux_label_names_completeness():
    """Test that all aux label IDs 0-27 are mapped."""
    for i in range(28):
        assert i in AUX_LABEL_NAMES, f"Aux label ID {i} missing from AUX_LABEL_NAMES"
