"""Tests for the ProCiv Madeira config and options flows."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import patch

import aiohttp
import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.data_entry_flow import InvalidData
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.prociv_madeira.alerts import URL
from custom_components.prociv_madeira.const import DOMAIN

from .common import ipma_feed

pytestmark = pytest.mark.usefixtures("mock_frontend")


def _fields(result: dict[str, Any]) -> list[str]:
    return [str(key) for key in result["data_schema"].schema]


async def _start_user_flow(hass: HomeAssistant) -> dict[str, Any]:
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )


async def test_user_flow_creates_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(URL, json=ipma_feed())
    result = await _start_user_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert _fields(result) == ["scan_interval"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"scan_interval": 45}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "ProCiv Madeira"
    assert result["data"] == {}
    assert result["options"] == {"scan_interval": 45}
    assert result["result"].minor_version == 2


@pytest.mark.parametrize(
    ("response", "error", "detail"),
    [
        ({"exc": aiohttp.ClientError("offline")}, "cannot_connect", "offline"),
        ({"exc": TimeoutError()}, "cannot_connect", "Timed out after 30 seconds"),
        ({"status": 500}, "cannot_connect", "HTTP 500"),
        ({"json": {"error": "maintenance"}}, "invalid_data", "got dict"),
        (
            {"text": "<html>Service unavailable</html>"},
            "invalid_data",
            "Not valid JSON",
        ),
    ],
    ids=["client-error", "timeout", "http-500", "not-a-list", "html"],
)
async def test_user_flow_shows_errors_and_recovers(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    response: dict[str, Any],
    error: str,
    detail: str,
) -> None:
    aioclient_mock.get(URL, **response)
    result = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"scan_interval": 45}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}
    assert detail in result["description_placeholders"]["error"]
    (field,) = result["data_schema"].schema
    assert field.description == {"suggested_value": 45}

    aioclient_mock.clear_requests()
    aioclient_mock.get(URL, json=ipma_feed())
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"scan_interval": 45}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"] == {"scan_interval": 45}


async def test_user_flow_reports_unexpected_errors(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    result = await _start_user_flow(hass)
    with patch(
        "custom_components.prociv_madeira.config_flow.fetch_alerts",
        side_effect=RuntimeError("bug in parser"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"scan_interval": 45}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}
    assert "bug in parser" in caplog.text


@pytest.mark.parametrize("scan_interval", [4, 1441])
async def test_user_flow_rejects_interval_out_of_range(
    hass: HomeAssistant, scan_interval: int
) -> None:
    result = await _start_user_flow(hass)

    with pytest.raises(InvalidData):
        await hass.config_entries.flow.async_configure(
            result["flow_id"], {"scan_interval": scan_interval}
        )


async def test_only_one_entry_is_allowed(hass: HomeAssistant) -> None:
    MockConfigEntry(domain=DOMAIN).add_to_hass(hass)

    result = await _start_user_flow(hass)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_options_flow_updates_scan_interval_and_reloads(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    # Frozen so the reload also has a pending warning-time update to cancel.
    freezer.move_to("2026-09-14T12:00:00+00:00")
    aioclient_mock.get(URL, json=ipma_feed())
    entry = MockConfigEntry(domain=DOMAIN, options={"scan_interval": 45})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coordinator = entry.runtime_data.coordinator

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    (field,) = result["data_schema"].schema
    assert str(field) == "scan_interval"
    assert field.default() == 45

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"scan_interval": 60}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {"scan_interval": 60}
    assert entry.runtime_data.coordinator is not coordinator
    assert entry.runtime_data.coordinator.update_interval == timedelta(minutes=60)
