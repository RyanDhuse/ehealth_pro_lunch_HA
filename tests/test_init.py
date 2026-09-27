"""Tests for the midnight rollover and daily refresh listeners."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import custom_components.healthepro_menu as integration


def test_setup_registers_midnight_redraw_and_jittered_refresh():
    coordinator = MagicMock()
    coordinator.async_config_entry_first_refresh = AsyncMock()
    coordinator.async_request_refresh = AsyncMock()
    hass = SimpleNamespace(
        data={},
        config_entries=SimpleNamespace(async_forward_entry_setups=AsyncMock()),
    )
    entry = MagicMock(entry_id="abc")

    tracked = []

    def fake_track(_hass, action, **when):
        tracked.append((action, when))
        return lambda: None

    with (
        patch.object(integration, "HealtheProCoordinator", return_value=coordinator),
        patch.object(integration, "async_track_time_change", fake_track),
    ):
        assert asyncio.run(integration.async_setup_entry(hass, entry))

    (redraw, redraw_at), (refresh, refresh_at) = tracked

    assert redraw_at == {"hour": 0, "minute": 0, "second": 0}
    redraw(None)
    coordinator.async_update_listeners.assert_called_once()
    coordinator.async_request_refresh.assert_not_called()

    assert refresh_at["hour"] == 0
    assert 0 <= refresh_at["minute"] * 60 + refresh_at["second"] <= 3599
    asyncio.run(refresh(None))
    coordinator.async_request_refresh.assert_awaited_once()
