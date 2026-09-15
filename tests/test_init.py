"""Tests for setting up ProCiv Madeira and the states of its entities."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock
from unittest.mock import Mock
from unittest.mock import call
from unittest.mock import patch

import aiohttp
import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.button import SERVICE_PRESS
from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL
from homeassistant.components.lovelace.const import LOVELACE_DATA
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.icon import async_get_icons
from homeassistant.loader import async_get_integration
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.common import async_fire_time_changed
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.prociv_madeira.alerts import ALERT_SEVERITY
from custom_components.prociv_madeira.alerts import URL
from custom_components.prociv_madeira.alerts import IpmaWarnings
from custom_components.prociv_madeira.alerts import parse_warnings
from custom_components.prociv_madeira.const import DOMAIN

from .common import HEAT_TEXT
from .common import FakeLovelaceResources
from .common import ipma_baseline
from .common import ipma_feed
from .common import ipma_row

PREFIX = "sensor.prociv_madeira_weather_alerts_"
ANY_ALERT = "binary_sensor.prociv_madeira_weather_alerts_any_active_alert"
WORST_ALERT = f"{PREFIX}worst_alert"
LAST_FETCH = f"{PREFIX}last_fetch"
REFRESH = "button.prociv_madeira_weather_alerts_refresh_data"
NORTH_COAST = f"{PREFIX}north_coast"
SOUTH_COAST = f"{PREFIX}south_coast"
REGION_SENSORS = [
    NORTH_COAST,
    SOUTH_COAST,
    f"{PREFIX}porto_santo",
    f"{PREFIX}mountainous_regions",
]
CARD_PATH = "/prociv_madeira/prociv-madeira-weather-card.js"
LEGACY_URL = "https://www.procivmadeira.pt/pt/12-avisos.html"
NOON = "2026-09-14T12:00:00+00:00"

pytestmark = pytest.mark.usefixtures("mock_frontend")


async def _setup_integration(
    hass: HomeAssistant,
    options: dict[str, Any] | None = None,
    minor_version: int = 2,
) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        minor_version=minor_version,
        options={"scan_interval": 1440} if options is None else options,
    )
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    return entry


async def _move_to(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, when: str
) -> None:
    freezer.move_to(when)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def _press_refresh(hass: HomeAssistant) -> None:
    await hass.services.async_call(
        "button", SERVICE_PRESS, {ATTR_ENTITY_ID: REFRESH}, blocking=True
    )
    await hass.async_block_till_done()


async def _card_url(hass: HomeAssistant) -> str:
    version = (await async_get_integration(hass, DOMAIN)).version
    return f"{CARD_PATH}?v={version}"


def _state(hass: HomeAssistant, entity_id: str) -> str:
    state = hass.states.get(entity_id)
    assert state is not None, entity_id
    return state.state


# ---------------------------------------------------------------------------
# Entity states
# ---------------------------------------------------------------------------


async def test_states_follow_warning_times_without_polling(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to(NOON)
    heat = "2026-09-14T10:00:00", "2026-09-14T20:00:00"
    wind = "2026-09-14T15:00:00", "2026-09-14T16:00:00"
    aioclient_mock.get(
        URL,
        json=[
            *ipma_baseline(),
            ipma_row("MCS", "Tempo Quente", "orange", *heat, HEAT_TEXT),
            ipma_row("MCN", "Tempo Quente", "yellow", *heat, HEAT_TEXT),
            ipma_row("MCS", "Vento", "red", *wind),
        ],
    )
    await _setup_integration(hass)

    south = hass.states.get(SOUTH_COAST)
    assert south.state == "orange"
    assert south.attributes["problem_type"] == "Heat"
    assert south.attributes["end_date"] == "2026-09-14T20:00:00+00:00"
    assert [a["alert_type"] for a in south.attributes["alerts"]] == ["orange"]
    assert [a["alert_type"] for a in south.attributes["upcoming_alerts"]] == ["red"]
    assert _state(hass, NORTH_COAST) == "yellow"
    assert _state(hass, WORST_ALERT) == "orange"
    assert _state(hass, ANY_ALERT) == "on"

    await _move_to(hass, freezer, "2026-09-14T15:00:00+00:00")
    assert _state(hass, SOUTH_COAST) == "red"
    assert _state(hass, WORST_ALERT) == "red"

    await _move_to(hass, freezer, "2026-09-14T16:00:00+00:00")
    assert _state(hass, SOUTH_COAST) == "orange"

    await _move_to(hass, freezer, "2026-09-14T20:00:00+00:00")
    for entity_id in REGION_SENSORS:
        assert _state(hass, entity_id) == "green"
    assert _state(hass, WORST_ALERT) == "green"
    assert _state(hass, ANY_ALERT) == "off"
    # Every change came from the warning times; the daily poll is not due yet.
    assert aioclient_mock.call_count == 1


async def test_new_data_reschedules_state_changes(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to(NOON)
    aioclient_mock.get(URL, json=ipma_baseline())
    await _setup_integration(hass)

    aioclient_mock.clear_requests()
    wind = ipma_row("MCS", "Vento", "red", "2026-09-14T13:00:00", "2026-09-14T14:00:00")
    aioclient_mock.get(URL, json=[*ipma_baseline(), wind])
    await _press_refresh(hass)
    assert _state(hass, SOUTH_COAST) == "green"

    await _move_to(hass, freezer, "2026-09-14T13:00:00+00:00")
    assert _state(hass, SOUTH_COAST) == "red"
    await _move_to(hass, freezer, "2026-09-14T14:00:00+00:00")
    assert _state(hass, SOUTH_COAST) == "green"
    assert aioclient_mock.call_count == 1


async def test_upcoming_warnings_are_not_in_effect_yet(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to(NOON)
    wind = ipma_row("MCS", "Vento", "red", "2026-09-14T15:00:00", "2026-09-14T16:00:00")
    aioclient_mock.get(URL, json=[*ipma_baseline(), wind])
    await _setup_integration(hass)

    south = hass.states.get(SOUTH_COAST)
    assert south.state == "green"
    assert south.attributes["alerts"] == []
    assert [a["alert_type"] for a in south.attributes["upcoming_alerts"]] == ["red"]
    assert _state(hass, WORST_ALERT) == "green"
    assert _state(hass, ANY_ALERT) == "off"


async def test_attributes_describe_the_worst_warning_in_effect(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to(NOON)
    fog = ipma_row(
        "MCN", "Nevoeiro", "yellow", "2026-09-14T10:00:00", "2026-09-14T20:00:00"
    )
    wind = ipma_row(
        "MCN",
        "Vento",
        "orange",
        "2026-09-14T11:00:00",
        "2026-09-14T18:00:00",
        "Rajadas",
    )
    aioclient_mock.get(URL, json=[*ipma_baseline(), fog, wind])
    await _setup_integration(hass)

    north = hass.states.get(NORTH_COAST)
    assert north.state == "orange"
    assert {
        key: north.attributes[key]
        for key in (
            "alert_type",
            "color",
            "problem_type",
            "description",
            "start_date",
            "end_date",
        )
    } == {
        "alert_type": "orange",
        "color": "#ffa500",
        "problem_type": "Wind",
        "description": "Rajadas",
        "start_date": "2026-09-14T11:00:00+00:00",
        "end_date": "2026-09-14T18:00:00+00:00",
    }
    assert [a["problem_type"] for a in north.attributes["alerts"]] == ["Fog", "Wind"]


async def test_all_clear_feed_reports_green(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(URL, json=[row for row in ipma_feed() if row["text"] == ""])
    await _setup_integration(hass)

    for entity_id in [*REGION_SENSORS, WORST_ALERT]:
        state = hass.states.get(entity_id)
        assert state.state == "green"
        # Every option has a state name (see test_translations).
        assert state.attributes["options"] == list(ALERT_SEVERITY)
    assert _state(hass, ANY_ALERT) == "off"


async def test_alert_lists_are_not_recorded(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(URL, json=ipma_feed())
    await _setup_integration(hass)

    state_info = hass.states.get(SOUTH_COAST).state_info
    assert {"alerts", "upcoming_alerts"} <= state_info["unrecorded_attributes"]


@pytest.mark.parametrize(
    ("language", "entity_ids"),
    [
        (
            "en",
            [*REGION_SENSORS, WORST_ALERT, LAST_FETCH, ANY_ALERT, REFRESH],
        ),
        (
            "pt",
            [
                f"{PREFIX}costa_norte",
                f"{PREFIX}costa_sul",
                f"{PREFIX}porto_santo",
                f"{PREFIX}regioes_montanhosas",
                f"{PREFIX}pior_aviso",
                f"{PREFIX}ultima_atualizacao",
                "binary_sensor.prociv_madeira_weather_alerts_algum_aviso_ativo",
                "button.prociv_madeira_weather_alerts_atualizar_dados",
            ],
        ),
    ],
)
async def test_entity_ids_come_from_translated_names(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    language: str,
    entity_ids: list[str],
) -> None:
    hass.config.language = language
    aioclient_mock.get(URL, json=ipma_feed())
    entry = await _setup_integration(hass)

    entries = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    assert sorted(item.entity_id for item in entries) == sorted(entity_ids)


async def test_device_is_a_service_provided_by_ipma(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(URL, json=ipma_feed())
    entry = await _setup_integration(hass)

    (device,) = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    assert device.entry_type is dr.DeviceEntryType.SERVICE
    assert device.manufacturer == "IPMA"


async def test_icons_follow_the_alert_level(hass: HomeAssistant) -> None:
    icons = (await async_get_icons(hass, "entity", integrations=[DOMAIN]))[DOMAIN]

    assert icons["sensor"]["south_coast"]["default"] == "mdi:check-circle"
    assert icons["sensor"]["south_coast"]["state"]["red"] == "mdi:alert-octagon"
    assert icons["binary_sensor"]["any_active_alert"]["state"]["on"] == "mdi:alert"


async def test_default_scan_interval(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(URL, json=ipma_feed())
    entry = await _setup_integration(hass, options={})

    assert entry.runtime_data.coordinator.update_interval == timedelta(minutes=30)


# ---------------------------------------------------------------------------
# Regions whose data can't be used
# ---------------------------------------------------------------------------


async def test_broken_region_is_unavailable_on_its_own(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    freezer.move_to(NOON)
    aioclient_mock.get(URL, json=[*ipma_feed(), ipma_row("MCN", "Vento", "Red")])
    entry = await _setup_integration(hass, {"scan_interval": 5})

    assert entry.state is ConfigEntryState.LOADED
    assert _state(hass, NORTH_COAST) == STATE_UNAVAILABLE
    assert _state(hass, SOUTH_COAST) == "orange"
    assert _state(hass, f"{PREFIX}porto_santo") == "yellow"

    await _move_to(hass, freezer, "2026-09-14T12:05:00+00:00")
    assert _state(hass, NORTH_COAST) == STATE_UNAVAILABLE
    assert caplog.text.count("North Coast can't be used") == 1
    assert "MCN: unknown warning level 'Red'" in caplog.text

    aioclient_mock.clear_requests()
    aioclient_mock.get(URL, json=ipma_feed())
    await _move_to(hass, freezer, "2026-09-14T12:10:00+00:00")
    assert _state(hass, NORTH_COAST) == "yellow"
    assert "North Coast can be used again" in caplog.text


@pytest.mark.parametrize(
    ("elsewhere", "worst_alert", "any_active_alert"),
    [
        (ipma_row("MCS", "Vento", "red"), "red", "on"),
        (ipma_row("MCS", "Vento", "yellow"), STATE_UNAVAILABLE, "on"),
        (
            ipma_row("MCS", "Vento", "yellow", "2026-09-15T00:00:00"),
            STATE_UNAVAILABLE,
            STATE_UNAVAILABLE,
        ),
    ],
    ids=["red-elsewhere", "warning-elsewhere", "nothing-in-effect"],
)
async def test_aggregates_are_only_reported_when_certain(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
    elsewhere: dict[str, str],
    worst_alert: str,
    any_active_alert: str,
) -> None:
    freezer.move_to(NOON)
    broken = ipma_row("MCN", "Vento", "red", "garbage")
    aioclient_mock.get(URL, json=[*ipma_baseline(), broken, elsewhere])
    await _setup_integration(hass)

    assert _state(hass, WORST_ALERT) == worst_alert
    assert _state(hass, ANY_ALERT) == any_active_alert


# ---------------------------------------------------------------------------
# Fetch errors
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("response", "translation_key"),
    [
        ({"exc": aiohttp.ClientError("offline")}, "cannot_connect"),
        ({"exc": TimeoutError()}, "cannot_connect"),
        ({"status": 500}, "cannot_connect"),
        ({"json": {"error": "maintenance"}}, "invalid_data"),
        ({"json": [ipma_row("LSB", "Vento", "red")]}, "invalid_data"),
        ({"text": "<html>Service unavailable</html>"}, "invalid_data"),
    ],
    ids=["client-error", "timeout", "http-500", "not-a-list", "no-madeira", "html"],
)
async def test_setup_retries_with_a_translated_reason(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    response: dict[str, Any],
    translation_key: str,
) -> None:
    aioclient_mock.get(URL, **response)
    entry = await _setup_integration(hass)

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert entry.error_reason_translation_key == translation_key
    assert "IPMA" in entry.reason
    # Dashboards already get the card while the entry retries.
    assert await _card_url(hass) in hass.data[DATA_EXTRA_MODULE_URL].urls


async def test_outage_makes_alert_entities_unavailable_but_keeps_last_fetch(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    freezer.move_to(NOON)
    aioclient_mock.get(URL, json=ipma_feed())
    await _setup_integration(hass, {"scan_interval": 5})
    assert _state(hass, LAST_FETCH) == NOON

    aioclient_mock.clear_requests()
    aioclient_mock.get(URL, exc=aiohttp.ClientError("offline"))
    caplog.clear()
    await _move_to(hass, freezer, "2026-09-14T12:05:00+00:00")
    await _move_to(hass, freezer, "2026-09-14T12:10:00+00:00")

    for entity_id in [*REGION_SENSORS, WORST_ALERT, ANY_ALERT]:
        assert _state(hass, entity_id) == STATE_UNAVAILABLE, entity_id
    assert _state(hass, LAST_FETCH) == NOON
    assert caplog.text.count("Error fetching prociv_madeira data") == 1

    aioclient_mock.clear_requests()
    aioclient_mock.get(URL, json=ipma_feed())
    await _move_to(hass, freezer, "2026-09-14T12:15:00+00:00")

    assert _state(hass, SOUTH_COAST) == "orange"
    assert _state(hass, LAST_FETCH) == "2026-09-14T12:15:00+00:00"


async def test_refresh_button_presses_are_debounced(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to(NOON)
    aioclient_mock.get(URL, json=ipma_feed())
    await _setup_integration(hass)
    assert aioclient_mock.call_count == 1

    for _ in range(3):
        await hass.services.async_call(
            "button", SERVICE_PRESS, {ATTR_ENTITY_ID: REFRESH}, blocking=True
        )
    await hass.async_block_till_done()
    assert aioclient_mock.call_count == 2

    await _move_to(hass, freezer, "2026-09-14T12:00:11+00:00")
    assert aioclient_mock.call_count == 3


async def test_refresh_button_reports_a_failed_fetch(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to(NOON)
    aioclient_mock.get(URL, json=ipma_feed())
    await _setup_integration(hass)

    aioclient_mock.clear_requests()
    aioclient_mock.get(URL, exc=aiohttp.ClientError("offline"))
    with pytest.raises(HomeAssistantError) as raised:
        await _press_refresh(hass)

    assert raised.value.translation_domain == DOMAIN
    assert raised.value.translation_key == "cannot_connect"
    assert str(raised.value) == "Could not reach the IPMA warnings feed: offline"


async def test_refresh_button_reports_an_unexpected_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to(NOON)
    aioclient_mock.get(URL, json=ipma_feed())
    await _setup_integration(hass)

    with (
        patch(
            "custom_components.prociv_madeira.coordinator.fetch_alerts",
            side_effect=RuntimeError("bug in parser"),
        ),
        pytest.raises(HomeAssistantError) as raised,
    ):
        await _press_refresh(hass)

    assert raised.value.translation_key == "refresh_failed"
    assert str(raised.value) == "Could not refresh the IPMA warnings: bug in parser"


# ---------------------------------------------------------------------------
# Setup, unload and the bundled card
# ---------------------------------------------------------------------------


async def test_unload_entry(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    # Frozen so the heat warning has yet to end and a state change is pending.
    freezer.move_to(NOON)
    aioclient_mock.get(URL, json=ipma_feed())
    entry = await _setup_integration(hass)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    # The fixture teardown fails on lingering timers, so the pending
    # warning-time update must have been cancelled.
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_fetch_finishing_after_unload_schedules_nothing(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to(NOON)
    aioclient_mock.get(URL, json=ipma_feed())
    entry = await _setup_integration(hass)
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow_fetch(_session: aiohttp.ClientSession) -> IpmaWarnings:
        started.set()
        await release.wait()
        return parse_warnings(ipma_feed())

    with patch("custom_components.prociv_madeira.coordinator.fetch_alerts", slow_fetch):
        press = hass.async_create_task(_press_refresh(hass))
        await started.wait()
        assert await hass.config_entries.async_unload(entry.entry_id)
        release.set()
        await press
    # The fixture teardown fails on lingering timers, so the fetch that
    # finished after unloading must not have scheduled a state change.


async def test_card_file_is_served_without_cache_headers(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(URL, json=ipma_feed())
    await _setup_integration(hass)

    ((config,),) = hass.http.async_register_static_paths.await_args.args
    assert config.url_path == CARD_PATH
    assert Path(config.path).is_file()
    assert Path(config.path).name == "prociv-madeira-weather-card.js"
    assert config.cache_headers is False


async def test_card_is_loaded_once_and_kept_on_reload(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_frontend: Mock,
) -> None:
    aioclient_mock.get(URL, json=ipma_feed())
    entry = await _setup_integration(hass)
    url = await _card_url(hass)

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.data[DATA_EXTRA_MODULE_URL].urls == {url}
    assert mock_frontend.mock_calls == [call("added", url)]
    hass.http.async_register_static_paths.assert_awaited_once()


async def test_card_is_removed_with_the_entry_and_added_again(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(URL, json=ipma_feed())
    entry = await _setup_integration(hass)
    url = await _card_url(hass)

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert url not in hass.data[DATA_EXTRA_MODULE_URL].urls

    new_entry = MockConfigEntry(
        domain=DOMAIN, minor_version=2, options={"scan_interval": 1440}
    )
    new_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(new_entry.entry_id)
    await hass.async_block_till_done()
    assert url in hass.data[DATA_EXTRA_MODULE_URL].urls


async def test_migration_removes_legacy_card_resource_and_url_option(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    other_card = {"id": "2", "type": "module", "url": "/local/other-card.js"}
    manual_copy = {
        "id": "3",
        "type": "module",
        "url": "/local/prociv-madeira-weather-card.js",
    }
    resources = FakeLovelaceResources(
        [
            {"id": "1", "type": "module", "url": f"{CARD_PATH}?v=0.1.0"},
            other_card,
            manual_copy,
        ]
    )
    hass.data[LOVELACE_DATA] = SimpleNamespace(
        resource_mode="storage", resources=resources
    )
    aioclient_mock.get(URL, json=ipma_feed())
    entry = await _setup_integration(
        hass, {"scan_interval": 30, "url": LEGACY_URL}, minor_version=1
    )

    assert entry.state is ConfigEntryState.LOADED
    assert entry.minor_version == 2
    assert entry.options == {"scan_interval": 30}
    assert resources.stored == [other_card, manual_copy]


async def test_migration_leaves_yaml_dashboard_resources_alone(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    resources = FakeLovelaceResources([{"id": "1", "type": "module", "url": CARD_PATH}])
    hass.data[LOVELACE_DATA] = SimpleNamespace(
        resource_mode="yaml", resources=resources
    )
    aioclient_mock.get(URL, json=ipma_feed())
    entry = await _setup_integration(hass, minor_version=1)

    assert entry.minor_version == 2
    assert resources.loaded is False
    assert len(resources.stored) == 1


async def test_migration_survives_resource_errors(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    resources = FakeLovelaceResources([{"id": "1", "type": "module", "url": CARD_PATH}])
    resources.async_get_info = AsyncMock(side_effect=RuntimeError("storage broken"))
    hass.data[LOVELACE_DATA] = SimpleNamespace(
        resource_mode="storage", resources=resources
    )
    aioclient_mock.get(URL, json=ipma_feed())
    entry = await _setup_integration(
        hass, {"scan_interval": 30, "url": LEGACY_URL}, minor_version=1
    )

    assert entry.state is ConfigEntryState.LOADED
    assert entry.minor_version == 2
    assert entry.options == {"scan_interval": 30}


async def test_migration_survives_unexpected_lovelace_data(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    hass.data[LOVELACE_DATA] = SimpleNamespace()
    aioclient_mock.get(URL, json=ipma_feed())
    entry = await _setup_integration(hass, minor_version=1)

    assert entry.state is ConfigEntryState.LOADED
    assert entry.minor_version == 2


async def test_migration_keeps_removing_after_a_failed_delete(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    resources = FakeLovelaceResources(
        [
            {"id": "1", "type": "module", "url": f"{CARD_PATH}?v=0.1.0"},
            {"id": "2", "type": "module", "url": CARD_PATH},
        ]
    )
    delete = resources.async_delete_item

    async def fail_to_delete_the_first(item_id: str) -> None:
        if item_id == "1":
            raise RuntimeError("storage busy")
        await delete(item_id)

    resources.async_delete_item = fail_to_delete_the_first
    hass.data[LOVELACE_DATA] = SimpleNamespace(
        resource_mode="storage", resources=resources
    )
    aioclient_mock.get(URL, json=ipma_feed())
    entry = await _setup_integration(hass, minor_version=1)

    assert entry.state is ConfigEntryState.LOADED
    assert [item["id"] for item in resources.stored] == ["1"]
