"""Test PoolCop base entity."""

from __future__ import annotations

from unittest.mock import MagicMock


from custom_components.poolcop.entity import PoolCopEntity
from custom_components.poolcop.coordinator import PoolCopData

from .conftest import make_device, make_pool, make_state


def _make_mock_coordinator(data: PoolCopData | None = None):
    """Create a mock coordinator with data."""
    coordinator = MagicMock()
    coordinator.data = data
    coordinator.config_entry = MagicMock()
    coordinator.config_entry.unique_id = "12345"
    return coordinator


def test_is_component_installed_ph():
    """Test component installed check for pH."""
    data = PoolCopData(
        device=make_device(),
        state=make_state(),
        alarms=[],
        auxiliaries=[],
        pool=make_pool(),
        equipments={"pH": True, "orp": True},
    )
    coordinator = _make_mock_coordinator(data)
    assert PoolCopEntity.is_component_installed(coordinator, "pH") is True
    assert PoolCopEntity.is_component_installed(coordinator, "ph_control") is True


def test_is_component_installed_missing():
    """Test component installed check for missing component."""
    data = PoolCopData(
        device=make_device(),
        state=make_state(),
        alarms=[],
        auxiliaries=[],
        pool=make_pool(),
        equipments={"pH": True, "orp": False},
    )
    coordinator = _make_mock_coordinator(data)
    assert PoolCopEntity.is_component_installed(coordinator, "orp_control") is False


def test_is_component_installed_water_level():
    """Test component installed check for water level."""
    data = PoolCopData(
        device=make_device(),
        state=make_state(),  # water_level.installed=True by default
        alarms=[],
        auxiliaries=[],
        pool=make_pool(),
    )
    coordinator = _make_mock_coordinator(data)
    assert PoolCopEntity.is_component_installed(coordinator, "water_level") is True


def test_is_component_installed_no_data():
    """Test component installed returns True when no data."""
    coordinator = _make_mock_coordinator(None)
    assert PoolCopEntity.is_component_installed(coordinator, "pH") is True
