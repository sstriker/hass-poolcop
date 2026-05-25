"""Test PoolCop base entity."""

from aiopoolcop import PoolCopDevice

from custom_components.poolcop.coordinator import PoolCopData
from custom_components.poolcop.entity import PoolCopEntity


class FakeCoordinator:
    """Minimal coordinator stub for testing."""

    def __init__(self, data):
        self.data = data


def _make_data(equip_overrides=None):
    """Create PoolCopData with configurable equipment flags."""
    equip = {
        "hasPHSensor": True,
        "hasORPSensor": True,
        "hasAirTemperatureSensor": True,
        "hasWaterLevelSensor": True,
        "hasFACSensor": False,
        "hasConductivitySensor": False,
        "hasSaltSensor": False,
        "hasFCSensor": False,
        "hasTCSensor": False,
        "hasFlowMeter": False,
        "hasEnergyMeter": False,
        "hasPoolCover": True,
        "hasJetStream": False,
    }
    if equip_overrides:
        equip.update(equip_overrides)

    device = PoolCopDevice.from_dict({
        "id": 1,
        "equipmentsInfo": equip,
    })
    return PoolCopData(device=device)


def test_is_component_installed_ph():
    """Test pH component detection."""
    data_on = _make_data({"hasPHSensor": True})
    data_off = _make_data({"hasPHSensor": False})

    assert PoolCopEntity.is_component_installed(FakeCoordinator(data_on), "ph_control") is True
    assert PoolCopEntity.is_component_installed(FakeCoordinator(data_off), "ph_control") is False
    assert PoolCopEntity.is_component_installed(FakeCoordinator(data_on), "ph_set_point") is True
    assert PoolCopEntity.is_component_installed(FakeCoordinator(data_off), "ph_set_point") is False


def test_is_component_installed_orp():
    """Test ORP component detection."""
    data_on = _make_data({"hasORPSensor": True})
    data_off = _make_data({"hasORPSensor": False})

    assert PoolCopEntity.is_component_installed(FakeCoordinator(data_on), "orp_control") is True
    assert PoolCopEntity.is_component_installed(FakeCoordinator(data_off), "orp_control") is False
    assert PoolCopEntity.is_component_installed(FakeCoordinator(data_on), "orp_disinfectant") is True


def test_is_component_installed_waterlevel():
    """Test water level component detection."""
    data_on = _make_data({"hasWaterLevelSensor": True})
    data_off = _make_data({"hasWaterLevelSensor": False})

    assert PoolCopEntity.is_component_installed(FakeCoordinator(data_on), "waterlevel_auto_add") is True
    assert PoolCopEntity.is_component_installed(FakeCoordinator(data_off), "water_level") is False


def test_is_component_installed_air():
    """Test air temperature sensor detection."""
    data_on = _make_data({"hasAirTemperatureSensor": True})
    data_off = _make_data({"hasAirTemperatureSensor": False})

    assert PoolCopEntity.is_component_installed(FakeCoordinator(data_on), "temperature_air") is True
    assert PoolCopEntity.is_component_installed(FakeCoordinator(data_off), "temperature_air") is False


def test_is_component_installed_ioniser_always_false():
    """Ioniser is not exposed by client API."""
    data = _make_data()
    assert PoolCopEntity.is_component_installed(FakeCoordinator(data), "ioniser") is False
    assert PoolCopEntity.is_component_installed(FakeCoordinator(data), "ioniser_mode") is False


def test_is_component_installed_autochlor_always_false():
    """Autochlor is not exposed by client API."""
    data = _make_data()
    assert PoolCopEntity.is_component_installed(FakeCoordinator(data), "autochlor_control") is False
    assert PoolCopEntity.is_component_installed(FakeCoordinator(data), "autochlor_auto") is False


def test_is_component_installed_always_true():
    """Unrelated keys are always considered installed."""
    data = _make_data()
    coord = FakeCoordinator(data)

    assert PoolCopEntity.is_component_installed(coord, "pressure") is True
    assert PoolCopEntity.is_component_installed(coord, "temperature_water") is True
    assert PoolCopEntity.is_component_installed(coord, "pump_speed") is True


def test_is_component_installed_data_none():
    """When coordinator.data is None, all components are considered installed."""
    coord = FakeCoordinator(None)
    assert PoolCopEntity.is_component_installed(coord, "ph_control") is True
    assert PoolCopEntity.is_component_installed(coord, "pump_speed") is True


def test_is_component_installed_pool_cover():
    """Pool cover gating by hasPoolCover."""
    data_on = _make_data({"hasPoolCover": True})
    data_off = _make_data({"hasPoolCover": False})

    assert PoolCopEntity.is_component_installed(FakeCoordinator(data_on), "pool_cover_open") is True
    assert PoolCopEntity.is_component_installed(FakeCoordinator(data_off), "pool_cover_open") is False


def test_is_component_installed_jet_stream():
    """Jet stream gating by hasJetStream."""
    data_on = _make_data({"hasJetStream": True})
    data_off = _make_data({"hasJetStream": False})

    assert PoolCopEntity.is_component_installed(FakeCoordinator(data_on), "jet_stream_running") is True
    assert PoolCopEntity.is_component_installed(FakeCoordinator(data_off), "jet_stream_running") is False


def test_is_component_installed_free_chlorine():
    """Free chlorine gating by hasFCSensor."""
    data_on = _make_data({"hasFCSensor": True})
    data_off = _make_data({"hasFCSensor": False})

    assert PoolCopEntity.is_component_installed(FakeCoordinator(data_on), "free_chlorine") is True
    assert PoolCopEntity.is_component_installed(FakeCoordinator(data_off), "free_chlorine") is False


def test_is_component_installed_total_chlorine():
    """Total chlorine gating by hasTCSensor."""
    data_on = _make_data({"hasTCSensor": True})
    data_off = _make_data({"hasTCSensor": False})

    assert PoolCopEntity.is_component_installed(FakeCoordinator(data_on), "total_chlorine") is True
    assert PoolCopEntity.is_component_installed(FakeCoordinator(data_off), "total_chlorine") is False


def test_is_component_installed_disinfection():
    """Disinfection prefix gating by hasORPSensor."""
    data_on = _make_data({"hasORPSensor": True})
    data_off = _make_data({"hasORPSensor": False})

    assert PoolCopEntity.is_component_installed(FakeCoordinator(data_on), "disinfection_last_injection_duration") is True
    assert PoolCopEntity.is_component_installed(FakeCoordinator(data_off), "disinfection_last_injection_duration") is False
    assert PoolCopEntity.is_component_installed(FakeCoordinator(data_on), "disinfection_dosing") is True
    assert PoolCopEntity.is_component_installed(FakeCoordinator(data_off), "disinfection_dosing") is False


def test_is_component_installed_flow_meter():
    """Flow meter gating by hasFlowMeter."""
    data_on = _make_data({"hasFlowMeter": True})
    data_off = _make_data({"hasFlowMeter": False})

    assert PoolCopEntity.is_component_installed(FakeCoordinator(data_on), "flow_meter_rate") is True
    assert PoolCopEntity.is_component_installed(FakeCoordinator(data_off), "flow_meter_rate") is False
