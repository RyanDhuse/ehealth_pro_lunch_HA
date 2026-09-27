"""DataUpdateCoordinator for Health-e Pro Menu."""
from __future__ import annotations

import calendar
import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import HealtheProApi, HealtheProApiError
from .const import (
    CONF_INCLUDE_RECIPE_DETAILS,
    CONF_MENU_ID,
    CONF_MEAL_TYPE_ID,
    CONF_ORG_ID,
    CONF_PREFETCH_NEXT_MONTH,
    CONF_REFRESH_HOURS,
    CONF_SITE_ID,
    CONF_SOURCE_URL,
    DEFAULT_INCLUDE_RECIPE_DETAILS,
    DEFAULT_PREFETCH_NEXT_MONTH,
    DEFAULT_REFRESH_HOURS,
    DOMAIN,
    MEAL_TYPE_LABELS,
)
from .models import RecipeDetail, SchoolMenuData
from .parser import parse_month

_LOGGER = logging.getLogger(__name__)


def _parse_recipe(raw: dict) -> RecipeDetail:
    allergens = [a["name"] for a in raw.get("allergens", []) if a.get("name")]
    attributes = [a["name"] for a in raw.get("attributes", []) if a.get("name")]
    nutrients = raw.get("nutrients") or {}
    try:
        calories = float(nutrients["calories_kcal"]) if nutrients.get("calories_kcal") else None
    except (ValueError, TypeError):
        calories = None
    category = raw.get("category", {}).get("category") if raw.get("category") else None
    return RecipeDetail(
        id=raw["id"],
        name=raw.get("name", ""),
        allergens=allergens,
        attributes=attributes,
        calories=calories,
        category=category,
        image_url=raw.get("image_path") or None,
        updated_at=raw.get("updated_at"),
    )


def _merge_recipes(month, raw_recipes: list[dict]) -> None:
    """Merge recipe detail into each day's recipe_ids lookup."""
    recipe_map: dict[int, RecipeDetail] = {
        r["id"]: _parse_recipe(r) for r in raw_recipes if r.get("id")
    }
    for day in month.days:
        day.recipes = {rid: recipe_map[rid] for rid in day.recipe_ids if rid in recipe_map}


def _shift_month(year: int, month: int) -> tuple[int, int]:
    if month == 12:
        return year + 1, 1
    return year, month + 1


def _month_date_range(year: int, month: int) -> tuple[str, str]:
    last_day = calendar.monthrange(year, month)[1]
    return f"{year}-{month:02d}-01", f"{year}-{month:02d}-{last_day:02d}"


def _select_target_month(
    published_months: list[str], now
) -> tuple[int, int] | None:
    """Pick which (year, month) to fetch based on what the API has published.

    Prefers the current calendar month if it's published; otherwise the
    nearest upcoming published month (e.g. school hasn't started yet); and
    otherwise falls back to the most recent past published month (e.g. menus
    for next school year aren't published yet).
    """
    months: list[tuple[int, int]] = []
    for raw in published_months:
        try:
            parts = raw.split("-")
            months.append((int(parts[0]), int(parts[1])))
        except (IndexError, ValueError):
            continue
    if not months:
        return None
    months.sort()

    current = (now.year, now.month)
    if current in months:
        return current

    upcoming = [m for m in months if m >= current]
    if upcoming:
        return upcoming[0]

    return months[-1]


class HealtheProCoordinator(DataUpdateCoordinator[SchoolMenuData]):
    def __init__(self, hass: HomeAssistant, entry) -> None:
        self.entry = entry
        refresh_hours = entry.options.get(CONF_REFRESH_HOURS, DEFAULT_REFRESH_HOURS)
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(hours=refresh_hours),
        )
        session = async_get_clientsession(hass)
        self.api = HealtheProApi(session)

    async def _async_update_data(self) -> SchoolMenuData:
        cfg = self.entry.data
        opts = self.entry.options

        org_id: int = cfg[CONF_ORG_ID]
        site_id: int = cfg[CONF_SITE_ID]
        menu_id: int = cfg[CONF_MENU_ID]
        meal_type_id: int = cfg.get(CONF_MEAL_TYPE_ID, 2)
        source_url: str = cfg[CONF_SOURCE_URL]
        prefetch = opts.get(CONF_PREFETCH_NEXT_MONTH, DEFAULT_PREFETCH_NEXT_MONTH)
        include_recipes = opts.get(CONF_INCLUDE_RECIPE_DETAILS, DEFAULT_INCLUDE_RECIPE_DETAILS)

        now = dt_util.now()
        last_error: str | None = None

        # Fetch metadata (non-fatal if cached version already exists)
        try:
            org = await self.api.async_get_organization(org_id)
            site = await self.api.async_get_site(org_id, site_id)
            menu_meta = await self.api.async_get_menu(org_id, menu_id)
        except HealtheProApiError as err:
            if self.data:
                _LOGGER.warning("Metadata refresh failed, using cached: %s", err)
                org = {"name": self.data.organization_name}
                site = {"name": self.data.site_name}
                menu_meta = {
                    "name": self.data.menu_name,
                    "published_months": self.data.published_months,
                }
                last_error = str(err)
            else:
                raise UpdateFailed(f"Cannot reach Health-e Pro API: {err}") from err

        org_name = org.get("name", str(org_id))
        site_name = site.get("name", str(site_id))
        menu_name = menu_meta.get("name", str(menu_id))
        published_months = menu_meta.get("published_months", [])

        target = _select_target_month(published_months, now)
        if target is None:
            raise UpdateFailed("No published months available for this menu")
        cur_year, cur_month = target
        nxt_year, nxt_month = _shift_month(cur_year, cur_month)

        # Fetch current month (required)
        try:
            raw = await self.api.async_get_date_overwrites(org_id, menu_id, cur_year, cur_month)
        except HealtheProApiError as err:
            raise UpdateFailed(f"Failed to fetch menu for {cur_year}-{cur_month}: {err}") from err

        current_month = parse_month(raw, cur_year, cur_month, meal_type_id)

        # Optionally enrich with recipe details
        if include_recipes and not last_error:
            try:
                start, end = _month_date_range(cur_year, cur_month)
                raw_recipes = await self.api.async_get_recipes(org_id, menu_id, start, end)
                _merge_recipes(current_month, raw_recipes)
            except HealtheProApiError as err:
                _LOGGER.warning("Recipe enrichment failed (non-fatal): %s", err)
                last_error = str(err)

        # Optionally fetch next month
        next_month = None
        if prefetch:
            try:
                raw_next = await self.api.async_get_date_overwrites(
                    org_id, menu_id, nxt_year, nxt_month
                )
                next_month = parse_month(raw_next, nxt_year, nxt_month, meal_type_id)
                if include_recipes and not last_error and next_month:
                    try:
                        start, end = _month_date_range(nxt_year, nxt_month)
                        raw_recipes_next = await self.api.async_get_recipes(
                            org_id, menu_id, start, end
                        )
                        _merge_recipes(next_month, raw_recipes_next)
                    except HealtheProApiError:
                        pass
            except HealtheProApiError:
                # Next month may simply not be published yet — not an error
                pass

        return SchoolMenuData(
            vendor="healthepro",
            organization_id=org_id,
            site_id=site_id,
            menu_id=menu_id,
            organization_name=org_name,
            site_name=site_name,
            menu_name=menu_name,
            meal_type_id=meal_type_id,
            meal_type_label=MEAL_TYPE_LABELS.get(meal_type_id, "Lunch"),
            published_months=published_months,
            source_url=source_url,
            current_month=current_month,
            next_month=next_month,
            last_error=last_error,
        )
