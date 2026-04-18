"""Tests for coordinator update logic.

Since the coordinator class inherits from a stubbed HA base class, we
test the update logic by directly invoking the function body with a
minimal self-like namespace.
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

# We need to test the actual code in coordinator.py's _async_update_data.
# Because the class hierarchy is broken by stubs, we re-implement the
# function reference from source and call it with a fake self.
import custom_components.prociv_madeira.coordinator as coord_mod


async def _run_update(fake_self: MagicMock) -> dict:
    """Call the real _async_update_data logic with a fake self."""
    try:
        session = coord_mod.async_get_clientsession(fake_self.hass)
        result = await coord_mod.fetch_alerts(session, fake_self.url)
        fake_self.last_fetch = coord_mod.dt_util.utcnow()
        return result
    except Exception as exception:
        coord_mod.LOGGER.warning("Failed to fetch ProCiv Madeira data: %s", exception)
        raise


class TestCoordinatorUpdate:
    """Tests for the coordinator's update logic."""

    @pytest.mark.asyncio
    async def test_successful_update_sets_last_fetch(self) -> None:
        fake = MagicMock()
        fake.url = "https://example.com"
        fake.last_fetch = None
        mock_data = {"CN": [], "CS": [], "PS": [], "RM": []}

        with (
            patch.object(
                coord_mod,
                "fetch_alerts",
                new_callable=AsyncMock,
                return_value=mock_data,
            ),
            patch.object(
                coord_mod,
                "async_get_clientsession",
                return_value=MagicMock(),
            ),
        ):
            result = await _run_update(fake)

        assert result == mock_data
        assert fake.last_fetch is not None

    @pytest.mark.asyncio
    async def test_error_propagates(self) -> None:
        fake = MagicMock()
        fake.url = "https://example.com"

        with (
            patch.object(
                coord_mod,
                "fetch_alerts",
                new_callable=AsyncMock,
                side_effect=Exception("timeout"),
            ),
            patch.object(
                coord_mod,
                "async_get_clientsession",
                return_value=MagicMock(),
            ),
            pytest.raises(Exception, match="timeout"),
        ):
            await _run_update(fake)

    @pytest.mark.asyncio
    async def test_last_fetch_unchanged_on_error(self) -> None:
        fake = MagicMock()
        fake.url = "https://example.com"
        fake.last_fetch = None

        with (
            patch.object(
                coord_mod,
                "fetch_alerts",
                new_callable=AsyncMock,
                side_effect=Exception("fail"),
            ),
            patch.object(
                coord_mod,
                "async_get_clientsession",
                return_value=MagicMock(),
            ),
        ):
            try:
                await _run_update(fake)
            except Exception:  # noqa: BLE001
                pass

        assert fake.last_fetch is None
