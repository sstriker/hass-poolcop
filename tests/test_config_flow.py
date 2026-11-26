"""Test PoolCop config flow."""

from copy import deepcopy
from unittest.mock import AsyncMock, patch

import pytest
from aiopoolcop import (
    Pool,
    PoolCopClientAuthError,
    PoolCopClientConnectionError,
    PoolCopClientError,
    PoolCopDevice,
)
from conftest import MOCK_DEVICE_RESPONSE, MOCK_POOL_RESPONSE
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.poolcop.config_flow import _device_label, _speed_to_int
from custom_components.poolcop.const import (
    CONF_FLOW_RATE_1,
    CONF_FLOW_RATE_2,
    CONF_FLOW_RATE_3,
    CONF_MAP_MODE,
    DOMAIN,
    MAP_MODE_ATTENTION,
)

CLIENT = "custom_components.poolcop.helpers.PoolCopClientAPI"


def _pool(pool_id: int = 97138, devices=None, **overrides) -> Pool:
    data = deepcopy(MOCK_POOL_RESPONSE)
    data["id"] = pool_id
    if devices is not None:
        data["devices"] = devices
    data.update(overrides)
    return Pool.from_dict(data)


def _mock_api(pools=None, device_data=None):
    """Create a mocked PoolCopClientAPI."""
    api = AsyncMock()
    api.get_pools.return_value = [_pool()] if pools is None else pools
    api.get_device.return_value = PoolCopDevice.from_dict(
        device_data or MOCK_DEVICE_RESPONSE
    )
    return api


@pytest.fixture
def mock_setup_entry():
    """Don't set up the entry after the flow creates it."""
    with patch(
        "custom_components.poolcop.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


async def _start_with_key(hass: HomeAssistant, api, key: str = "my-api-key"):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    with patch(CLIENT, return_value=api):
        return await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_KEY: key}
        )


async def test_user_flow_single_device(hass: HomeAssistant, mock_setup_entry):
    """One PoolCop on the account goes straight to the flow rates."""
    api = _mock_api()
    result = await _start_with_key(hass, api, "  my-api-key  ")

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "flow_rates"
    assert result["description_placeholders"]["pump_speeds"] == "3"
    api.get_device.assert_called_once_with(2478)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_FLOW_RATE_1: 10.0, CONF_FLOW_RATE_2: 15.0, CONF_FLOW_RATE_3: 20.0},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Striker"
    assert result["result"].unique_id == "2478"
    assert result["data"] == {CONF_API_KEY: "my-api-key", "pump_speeds": 3}
    assert result["options"] == {
        CONF_FLOW_RATE_1: 10.0,
        CONF_FLOW_RATE_2: 15.0,
        CONF_FLOW_RATE_3: 20.0,
    }


async def test_user_flow_picks_device(hass: HomeAssistant, mock_setup_entry):
    """With several PoolCops the user picks one."""
    device_data = deepcopy(MOCK_DEVICE_RESPONSE)
    device_data["id"] = 3001
    device_data["nickname"] = "Holiday home"
    device_data["settings"]["filtrations"][0]["nbSpeeds"] = "Speed1"
    api = _mock_api(
        pools=[
            _pool(),
            _pool(97139, devices=[{"id": 3001, "nickname": "Holiday home"}]),
        ],
        device_data=device_data,
    )
    result = await _start_with_key(hass, api)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "device"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"device_id": "3001"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "flow_rates"
    api.get_device.assert_called_once_with(3001)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_FLOW_RATE_1: 8.0}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Holiday home"
    assert result["result"].unique_id == "3001"
    assert result["data"]["pump_speeds"] == 1
    assert result["options"] == {CONF_FLOW_RATE_1: 8.0}


async def test_user_flow_skips_configured_devices(
    hass: HomeAssistant, mock_config_entry, mock_setup_entry
):
    """Configured PoolCops are not offered again."""
    mock_config_entry.add_to_hass(hass)
    api = _mock_api(
        pools=[
            _pool(
                devices=[
                    {"id": 2478, "nickname": "Striker"},
                    {"id": 3001, "nickname": "Spa"},
                ]
            )
        ]
    )
    result = await _start_with_key(hass, api)

    # Only one unconfigured device left: no picker
    assert result["step_id"] == "flow_rates"
    api.get_device.assert_called_once_with(3001)


async def test_user_flow_all_configured(hass: HomeAssistant, mock_config_entry):
    """Abort when every PoolCop of the account is configured."""
    mock_config_entry.add_to_hass(hass)
    result = await _start_with_key(hass, _mock_api())
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (PoolCopClientAuthError("bad"), "invalid_auth"),
        (PoolCopClientConnectionError("down"), "cannot_connect"),
        (PoolCopClientError("boom"), "unknown"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant, mock_setup_entry, side_effect, error
):
    """Errors are shown on the form, and the user can retry."""
    api = _mock_api()
    api.get_pools.side_effect = side_effect
    result = await _start_with_key(hass, api)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error}

    api.get_pools.side_effect = None
    with patch(CLIENT, return_value=api):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_KEY: "my-api-key"}
        )
    assert result["step_id"] == "flow_rates"


@pytest.mark.parametrize("pools", [[], [_pool(devices=[])]])
async def test_user_flow_no_devices(hass: HomeAssistant, pools):
    """A key without PoolCops shows an error."""
    result = await _start_with_key(hass, _mock_api(pools=pools))
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_devices"}


async def test_user_flow_device_load_fails(hass: HomeAssistant):
    """Abort when the chosen PoolCop cannot be loaded."""
    api = _mock_api()
    api.get_device.side_effect = PoolCopClientConnectionError("down")
    result = await _start_with_key(hass, api)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_user_flow_device_configured_meanwhile(hass: HomeAssistant):
    """Abort if the picked PoolCop was configured while the flow ran."""
    api = _mock_api(
        pools=[
            _pool(
                devices=[
                    {"id": 2478, "nickname": "Striker"},
                    {"id": 3001, "nickname": "Spa"},
                ]
            )
        ]
    )
    result = await _start_with_key(hass, api)
    assert result["step_id"] == "device"

    MockConfigEntry(domain=DOMAIN, unique_id="3001", version=3).add_to_hass(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"device_id": "3001"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_without_filtration_settings(
    hass: HomeAssistant, mock_setup_entry
):
    """Without filtration settings a single speed is assumed."""
    device_data = deepcopy(MOCK_DEVICE_RESPONSE)
    device_data["settings"]["filtrations"] = []
    device_data["settings"]["pool"]["estimatedFlowrate"] = None
    result = await _start_with_key(hass, _mock_api(device_data=device_data))
    assert result["step_id"] == "flow_rates"
    assert result["description_placeholders"]["pump_speeds"] == "1"
    assert result["description_placeholders"]["flowrate"] == "0"


async def _start_reauth(hass: HomeAssistant, entry: MockConfigEntry):
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["description_placeholders"]["title"] == entry.title
    return result


async def test_reauth_flow(hass: HomeAssistant, mock_config_entry):
    """A key that can see the PoolCop replaces the old one."""
    result = await _start_reauth(hass, mock_config_entry)
    with (
        patch(CLIENT, return_value=_mock_api()),
        patch(
            "custom_components.poolcop.async_setup_entry", return_value=True
        ) as mock_setup,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_KEY: " new-key "}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_API_KEY] == "new-key"
    assert mock_setup.called


@pytest.mark.parametrize(
    ("side_effect", "pools", "error"),
    [
        (PoolCopClientAuthError("bad"), None, "invalid_auth"),
        (PoolCopClientConnectionError("down"), None, "cannot_connect"),
        (PoolCopClientError("boom"), None, "unknown"),
        (None, [_pool(devices=[{"id": 1, "nickname": "Other"}])], "device_not_found"),
    ],
)
async def test_reauth_errors(
    hass: HomeAssistant, mock_config_entry, side_effect, pools, error
):
    """Reauth shows errors, including a key from another account."""
    result = await _start_reauth(hass, mock_config_entry)
    api = _mock_api(pools=pools)
    api.get_pools.side_effect = side_effect
    with patch(CLIENT, return_value=api):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_KEY: "new-key"}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}
    assert mock_config_entry.data[CONF_API_KEY] != "new-key"


async def test_reconfigure_flow(hass: HomeAssistant, mock_config_entry):
    """The API key can be changed through reconfigure."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    api = _mock_api(pools=[_pool(devices=[{"id": 1, "nickname": "Other"}])])
    with patch(CLIENT, return_value=api):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_KEY: "other-account"}
        )
    assert result["errors"] == {"base": "device_not_found"}

    with (
        patch(CLIENT, return_value=_mock_api()),
        patch("custom_components.poolcop.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_KEY: "new-key"}
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_API_KEY] == "new-key"


async def test_options_flow(
    hass: HomeAssistant,
    mock_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """Test the options flow for map mode and flow rates."""
    mock_poolcop_api.get_device.return_value = PoolCopDevice.from_dict(mock_device_data)
    mock_poolcop_api.get_pools.return_value = [Pool.from_dict(mock_pool_data)]
    mock_config_entry.add_to_hass(hass)

    with patch(CLIENT, return_value=mock_poolcop_api):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(
            mock_config_entry.entry_id
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_MAP_MODE: MAP_MODE_ATTENTION,
                CONF_FLOW_RATE_1: 12.0,
                CONF_FLOW_RATE_2: 18.0,
                CONF_FLOW_RATE_3: 24.0,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options == {
        CONF_MAP_MODE: MAP_MODE_ATTENTION,
        CONF_FLOW_RATE_1: 12.0,
        CONF_FLOW_RATE_2: 18.0,
        CONF_FLOW_RATE_3: 24.0,
    }


async def test_options_flow_single_speed_defaults_from_data(hass: HomeAssistant):
    """Pre-migration flow rates in data are used as defaults."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key", "pump_speeds": 1, CONF_FLOW_RATE_1: 9.0},
        unique_id="2478",
        version=3,
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    schema_keys = {str(key): key for key in result["data_schema"].schema}
    assert set(schema_keys) == {CONF_MAP_MODE, CONF_FLOW_RATE_1}
    assert schema_keys[CONF_FLOW_RATE_1].default() == 9.0


def test_speed_to_int():
    """Speed names convert to a number of speeds."""
    assert _speed_to_int("Speed3") == 3
    assert _speed_to_int("Speed1") == 1
    assert _speed_to_int("BadValue") == 1
    assert _speed_to_int("SpeedABC") == 1


def test_device_label():
    """Picker labels combine pool and PoolCop names and location."""
    assert _device_label(_pool(), "Striker", 2478) == (
        "Striker (TestCity, Netherlands) #2478"
    )
    assert _device_label(_pool(), "Spa", 3001) == (
        "Striker / Spa (TestCity, Netherlands) #3001"
    )
    bare = _pool(nickname=None, city=None, country=None)
    assert _device_label(bare, None, 7) == "PoolCop 7 #7"
