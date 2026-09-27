"""Health-e Pro Menu integration for Home Assistant."""
from __future__ import annotations

import logging
import random
from datetime import datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_change

from .const import DOMAIN
from .coordinator import HealtheProCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "calendar"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = HealtheProCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    # Today/tomorrow/calendar are computed from the clock, but coordinator
    # entities only write state on refresh. Redraw them at local midnight.
    @callback
    def _async_midnight_rollover(_now: datetime) -> None:
        coordinator.async_update_listeners()

    # Also refresh daily, at a random point in the first hour so installs
    # don't all hit the Health-e Pro API at 00:00.
    async def _async_daily_refresh(_now: datetime) -> None:
        await coordinator.async_request_refresh()

    offset = random.randint(0, 3599)
    entry.async_on_unload(
        async_track_time_change(
            hass, _async_midnight_rollover, hour=0, minute=0, second=0
        )
    )
    entry.async_on_unload(
        async_track_time_change(
            hass,
            _async_daily_refresh,
            hour=0,
            minute=offset // 60,
            second=offset % 60,
        )
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unloaded


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
