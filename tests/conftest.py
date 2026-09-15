"""Shared fixtures for the ProCiv Madeira tests."""

from __future__ import annotations

from unittest.mock import AsyncMock
from unittest.mock import Mock

import pytest
from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL
from homeassistant.components.frontend import UrlManager
from homeassistant.core import HomeAssistant


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Let Home Assistant load the integration from custom_components."""


@pytest.fixture
def mock_frontend(hass: HomeAssistant) -> Mock:
    """Satisfy the http and frontend dependencies without a web server.

    Returns the mock that records extra module URL changes.
    """
    hass.config.components.update({"http", "frontend"})
    hass.http = Mock(async_register_static_paths=AsyncMock())
    on_change = Mock()
    hass.data[DATA_EXTRA_MODULE_URL] = UrlManager(on_change, [])
    return on_change
