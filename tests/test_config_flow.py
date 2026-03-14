"""Test PoolCop config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.poolcop.const import (
    CONF_FLOW_RATE_1,
    CONF_FLOW_RATE_2,
    CONF_FLOW_RATE_3,
    DOMAIN,
)

MOCK_STATUS = {
    "PoolCop": {
        "settings": {
            "pump": {
                "nb_speed": 3,
                "flowrate": 15.0,
            },
            "pool": {
                "volume": 50,
            },
        },
    },
}


async def test_user_flow(hass: HomeAssistant):
    """Test the full user config flow."""
    mock_poolcop = AsyncMock()
    mock_poolcop.poolcop_id = "test-id"
    mock_poolcop.status.return_value = MOCK_STATUS

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "custom_components.poolcop.config_flow.PoolCopilot",
        return_value=mock_poolcop,
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
    # Flow rates should be in options, not data
    assert CONF_FLOW_RATE_1 not in result["data"]
    assert result["options"][CONF_FLOW_RATE_1] == 10.0
    assert result["options"][CONF_FLOW_RATE_2] == 15.0
    assert result["options"][CONF_FLOW_RATE_3] == 20.0


async def test_user_flow_invalid_auth(hass: HomeAssistant):
    """Test config flow with invalid API key."""
    from poolcop import PoolCopilotInvalidKeyError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    mock_poolcop = MagicMock()
    mock_poolcop.status = AsyncMock(side_effect=PoolCopilotInvalidKeyError("bad key"))

    with patch(
        "custom_components.poolcop.config_flow.PoolCopilot",
        return_value=mock_poolcop,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "bad-key"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_auth"


async def test_user_flow_cannot_connect(hass: HomeAssistant):
    """Test config flow when API is unreachable."""
    from poolcop import PoolCopilotConnectionError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    with patch(
        "custom_components.poolcop.config_flow.PoolCopilot",
    ) as mock_cls:
        mock_cls.return_value.status.side_effect = PoolCopilotConnectionError("down")
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "my-key"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


async def test_reauth_flow(hass: HomeAssistant, mock_config_entry, mock_poolcop):
    """Test the reauth flow."""
    mock_poolcop_validate = AsyncMock()
    mock_poolcop_validate.poolcop_id = "test-poolcop-id"
    mock_poolcop_validate.status.return_value = MOCK_STATUS

    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reauth", "entry_id": mock_config_entry.entry_id},
        data=mock_config_entry.data,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with (
        patch(
            "custom_components.poolcop.config_flow.PoolCopilot",
            return_value=mock_poolcop_validate,
        ),
        patch(
            "custom_components.poolcop.coordinator.PoolCopilot",
            return_value=mock_poolcop,
        ),
    ):
        mock_poolcop.status.return_value = {
            "PoolCop": {
                "status": {"poolcop": 3, "pump": 0},
                "conf": {},
                "alarms": {"count": 0},
                "network": {"version": "1.0"},
                "aux": [],
            }
        }
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "new-api-key"},
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_API_KEY] == "new-api-key"


async def test_options_flow(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """Test the options flow for reconfiguring flow rates."""
    mock_poolcop.status.return_value = mock_poolcop_data
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.poolcop.coordinator.PoolCopilot",
        return_value=mock_poolcop,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_FLOW_RATE_1: 12.0,
            CONF_FLOW_RATE_2: 18.0,
            CONF_FLOW_RATE_3: 24.0,
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options[CONF_FLOW_RATE_1] == 12.0
    assert mock_config_entry.options[CONF_FLOW_RATE_2] == 18.0
    assert mock_config_entry.options[CONF_FLOW_RATE_3] == 24.0


async def test_reauth_cannot_connect(
    hass: HomeAssistant, mock_config_entry, mock_poolcop
):
    """ConnectionError → errors['base']='cannot_connect'."""
    from poolcop import PoolCopilotConnectionError

    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reauth", "entry_id": mock_config_entry.entry_id},
        data=mock_config_entry.data,
    )
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "custom_components.poolcop.config_flow.PoolCopilot",
    ) as mock_cls:
        mock_cls.return_value.status.side_effect = PoolCopilotConnectionError("down")
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "new-key"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


async def test_reauth_invalid_auth(
    hass: HomeAssistant, mock_config_entry, mock_poolcop
):
    """InvalidKey → errors['base']='invalid_auth'."""
    from poolcop import PoolCopilotInvalidKeyError

    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reauth", "entry_id": mock_config_entry.entry_id},
        data=mock_config_entry.data,
    )

    with patch(
        "custom_components.poolcop.config_flow.PoolCopilot",
    ) as mock_cls:
        mock_cls.return_value.status.side_effect = PoolCopilotInvalidKeyError("bad")
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "bad-key"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_auth"


async def test_user_flow_unknown_error(hass: HomeAssistant):
    """Generic error → errors['base']='unknown'."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    with patch(
        "custom_components.poolcop.config_flow.PoolCopilot",
    ) as mock_cls:
        mock_cls.return_value.status.side_effect = ValueError("boom")
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "my-key"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "unknown"


async def test_user_flow_flowrate_conversion_error(hass: HomeAssistant):
    """Flowrate string that can't be converted to float is logged and skipped."""
    mock_poolcop = AsyncMock()
    mock_poolcop.poolcop_id = "test-id"
    mock_poolcop.status.return_value = {
        "PoolCop": {
            "settings": {
                "pump": {"nb_speed": 3, "flowrate": "not-a-number"},
                "pool": {"volume": 50},
            },
        },
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    with patch(
        "custom_components.poolcop.config_flow.PoolCopilot",
        return_value=mock_poolcop,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "key"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "flow_rates"


async def test_reauth_unknown_error(
    hass: HomeAssistant, mock_config_entry, mock_poolcop
):
    """Generic error during reauth shows unknown error."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reauth", "entry_id": mock_config_entry.entry_id},
        data=mock_config_entry.data,
    )
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "custom_components.poolcop.config_flow.PoolCopilot",
    ) as mock_cls:
        mock_cls.return_value.status.side_effect = ValueError("boom")
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "new-key"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "unknown"


async def test_user_flow_generic_poolcop_error(hass: HomeAssistant):
    """PoolCopilotError (not connection, not auth) in validate_input raises CannotConnect."""
    from poolcop import PoolCopilotError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    with patch(
        "custom_components.poolcop.config_flow.PoolCopilot",
    ) as mock_cls:
        mock_cls.return_value.status.side_effect = PoolCopilotError("generic")
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "key"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"
