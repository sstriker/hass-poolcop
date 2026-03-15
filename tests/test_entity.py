"""Test PoolCop base entity."""

from custom_components.poolcop.coordinator import PoolCopData
from custom_components.poolcop.entity import PoolCopEntity


def _make_data(conf_overrides=None, pool=None, status_overrides=None):
    """Create a PoolCopData with configurable conf flags."""
    conf = {
        "orp": 1,
        "pH": 1,
        "waterlevel": 1,
        "ioniser": 0,
        "autochlor": 0,
        "air": 1,
    }
    if conf_overrides:
        conf.update(conf_overrides)
    status = {"PoolCop": {"conf": conf}}
    if status_overrides:
        for k, v in status_overrides.items():
            status["PoolCop"][k] = v
    if pool is not None:
        status["Pool"] = pool
    return PoolCopData(status=status)


class FakeCoordinator:
    """Minimal coordinator stub for testing."""

    def __init__(self, data):
        self.data = data


def test_is_component_installed_ph():
    """Test pH component detection."""
    data_on = _make_data({"pH": 1})
    data_off = _make_data({"pH": 0})
    coord_on = FakeCoordinator(data_on)
    coord_off = FakeCoordinator(data_off)

    assert PoolCopEntity.is_component_installed(coord_on, "ph_control") is True
    assert PoolCopEntity.is_component_installed(coord_off, "ph_control") is False
    assert PoolCopEntity.is_component_installed(coord_on, "ph_set_point") is True
    assert PoolCopEntity.is_component_installed(coord_off, "ph_set_point") is False


def test_is_component_installed_orp():
    """Test ORP component detection."""
    data_on = _make_data({"orp": 1})
    data_off = _make_data({"orp": 0})
    coord_on = FakeCoordinator(data_on)
    coord_off = FakeCoordinator(data_off)

    assert PoolCopEntity.is_component_installed(coord_on, "orp_control") is True
    assert PoolCopEntity.is_component_installed(coord_off, "orp_control") is False
    assert PoolCopEntity.is_component_installed(coord_on, "orp_disinfectant") is True


def test_is_component_installed_ioniser():
    """Test ioniser component detection."""
    data_off = _make_data({"ioniser": 0})
    data_on = _make_data({"ioniser": 1})
    coord_off = FakeCoordinator(data_off)
    coord_on = FakeCoordinator(data_on)

    assert PoolCopEntity.is_component_installed(coord_off, "ioniser") is False
    assert PoolCopEntity.is_component_installed(coord_off, "ioniser_mode") is False
    assert PoolCopEntity.is_component_installed(coord_on, "ioniser") is True


def test_is_component_installed_autochlor():
    """Test autochlor component detection."""
    data_off = _make_data({"autochlor": 0})
    data_on = _make_data({"autochlor": 1})

    assert (
        PoolCopEntity.is_component_installed(
            FakeCoordinator(data_off), "autochlor_control"
        )
        is False
    )
    assert (
        PoolCopEntity.is_component_installed(FakeCoordinator(data_on), "autochlor_auto")
        is True
    )


def test_is_component_installed_waterlevel():
    """Test water level component detection."""
    data_on = _make_data({"waterlevel": 1})
    data_off = _make_data({"waterlevel": 0})

    assert (
        PoolCopEntity.is_component_installed(
            FakeCoordinator(data_on), "waterlevel_auto_add"
        )
        is True
    )
    assert (
        PoolCopEntity.is_component_installed(FakeCoordinator(data_off), "water_level")
        is False
    )


def test_is_component_installed_air():
    """Test air temperature sensor detection."""
    data_on = _make_data({"air": 1})
    data_off = _make_data({"air": 0})

    assert (
        PoolCopEntity.is_component_installed(
            FakeCoordinator(data_on), "temperature_air"
        )
        is True
    )
    assert (
        PoolCopEntity.is_component_installed(
            FakeCoordinator(data_off), "temperature_air"
        )
        is False
    )


def test_is_component_installed_always_true():
    """Test that unrelated keys are always considered installed."""
    data = _make_data()
    coord = FakeCoordinator(data)

    assert PoolCopEntity.is_component_installed(coord, "pressure") is True
    assert PoolCopEntity.is_component_installed(coord, "temperature_water") is True
    assert PoolCopEntity.is_component_installed(coord, "poolcop") is True
    assert PoolCopEntity.is_component_installed(coord, "pump_speed") is True
