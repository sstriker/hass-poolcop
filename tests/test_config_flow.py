"""Test PoolCop config flow."""

from unittest.mock import AsyncMock, patch

from aiopoolcop import (
    Pool,
    PoolCopClientAuthError,
    PoolCopClientConnectionError,
    PoolCopClientError,
    PoolCopDevice,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.poolcop.const import (
    CONF_FLOW_RATE_1,
    CONF_FLOW_RATE_2,
    CONF_FLOW_RATE_3,
    DOMAIN,
)

from .conftest import MOCK_DEVICE_RESPONSE, MOCK_POOL_RESPONSE


def _mock_api():
    """Create a mocked PoolCopClientAPI for config flow validation."""
    api = AsyncMock()
    api.get_pools.return_value = [Pool.from_dict(MOCK_POOL_RESPONSE)]
    api.get_device.return_value = PoolCopDevice.from_dict(MOCK_DEVICE_RESPONSE)
    api.close = AsyncMock()
    return api


async def test_user_flow(hass: HomeAssistant):
    """Test the full user config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_api = _mock_api()
    with patch(
        "custom_components.poolcop.config_flow.PoolCopClientAPI",
        return_value=mock_api,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "my-api-key"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "flow_rates"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_FLOW_RATE_1: 10.0,
            CONF_FLOW_RATE_2: 15.0,
            CONF_FLOW_RATE_3: 20.0,
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_API_KEY] == "my-api-key"
    assert CONF_FLOW_RATE_1 not in result["data"]
    assert result["options"][CONF_FLOW_RATE_1] == 10.0
    assert result["options"][CONF_FLOW_RATE_2] == 15.0
    assert result["options"][CONF_FLOW_RATE_3] == 20.0


async def test_user_flow_invalid_auth(hass: HomeAssistant):
    """Test config flow with invalid API key."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    mock_api = AsyncMock()
    mock_api.get_pools.side_effect = PoolCopClientAuthError("bad key")

    with patch(
        "custom_components.poolcop.config_flow.PoolCopClientAPI",
        return_value=mock_api,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "bad-key"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_auth"


async def test_user_flow_cannot_connect(hass: HomeAssistant):
    """Test config flow when API is unreachable."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    mock_api = AsyncMock()
    mock_api.get_pools.side_effect = PoolCopClientConnectionError("down")

    with patch(
        "custom_components.poolcop.config_flow.PoolCopClientAPI",
        return_value=mock_api,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "my-key"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


async def test_user_flow_unknown_error(hass: HomeAssistant):
    """Generic error shows unknown."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    mock_api = AsyncMock()
    mock_api.get_pools.side_effect = ValueError("boom")

    with patch(
        "custom_components.poolcop.config_flow.PoolCopClientAPI",
        return_value=mock_api,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "my-key"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "unknown"


async def test_user_flow_generic_poolcop_error(hass: HomeAssistant):
    """PoolCopClientError (not auth, not connection) maps to cannot_connect."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    mock_api = AsyncMock()
    mock_api.get_pools.side_effect = PoolCopClientError("generic")

    with patch(
        "custom_components.poolcop.config_flow.PoolCopClientAPI",
        return_value=mock_api,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "key"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


async def test_reauth_flow(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Test the reauth flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reauth", "entry_id": mock_config_entry.entry_id},
        data=mock_config_entry.data,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    validate_api = _mock_api()
    mock_poolcop_api.get_device.return_value = PoolCopDevice.from_dict(mock_device_data)
    mock_poolcop_api.get_pools.return_value = [Pool.from_dict(mock_pool_data)]

    with (
        patch(
            "custom_components.poolcop.config_flow.PoolCopClientAPI",
            return_value=validate_api,
        ),
        patch(
            "custom_components.poolcop.PoolCopClientAPI",
            return_value=mock_poolcop_api,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "new-api-key"},
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_API_KEY] == "new-api-key"


async def test_reauth_cannot_connect(hass: HomeAssistant, mock_config_entry):
    """ConnectionError during reauth shows cannot_connect."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reauth", "entry_id": mock_config_entry.entry_id},
        data=mock_config_entry.data,
    )

    mock_api = AsyncMock()
    mock_api.get_pools.side_effect = PoolCopClientConnectionError("down")

    with patch(
        "custom_components.poolcop.config_flow.PoolCopClientAPI",
        return_value=mock_api,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "new-key"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


async def test_reauth_invalid_auth(hass: HomeAssistant, mock_config_entry):
    """Invalid key during reauth shows invalid_auth."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reauth", "entry_id": mock_config_entry.entry_id},
        data=mock_config_entry.data,
    )

    mock_api = AsyncMock()
    mock_api.get_pools.side_effect = PoolCopClientAuthError("bad")

    with patch(
        "custom_components.poolcop.config_flow.PoolCopClientAPI",
        return_value=mock_api,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "bad-key"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_auth"


async def test_options_flow(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Test the options flow for reconfiguring flow rates."""
    mock_poolcop_api.get_device.return_value = PoolCopDevice.from_dict(mock_device_data)
    mock_poolcop_api.get_pools.return_value = [Pool.from_dict(mock_pool_data)]
    mock_config_entry.add_to_hass(hass)

    with patch("custom_components.poolcop.PoolCopClientAPI", return_value=mock_poolcop_api):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    from custom_components.poolcop.const import CONF_MAP_MODE, MAP_MODE_ALWAYS

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_MAP_MODE: MAP_MODE_ALWAYS,
            CONF_FLOW_RATE_1: 12.0,
            CONF_FLOW_RATE_2: 18.0,
            CONF_FLOW_RATE_3: 24.0,
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options[CONF_FLOW_RATE_1] == 12.0
    assert mock_config_entry.options[CONF_FLOW_RATE_2] == 18.0
    assert mock_config_entry.options[CONF_FLOW_RATE_3] == 24.0
