"""URL parsing and Health-e Pro payload normalization."""
from __future__ import annotations

import json
import logging
import re
from urllib.parse import urlparse

from .const import MEAL_ENTREE_CATEGORIES, MEAL_TYPE_LUNCH, MENU_HOST
from .models import MenuDay, MenuMonth

_LOGGER = logging.getLogger(__name__)

HEALTHEPRO_URL_RE = re.compile(
    r"/organizations/(?P<org_id>\d+)/sites/(?P<site_id>\d+)/menus/(?P<menu_id>\d+)"
)


def parse_menu_url(url: str) -> tuple[int, int, int] | None:
    """Extract (org_id, site_id, menu_id) from a Health-e Pro public menu URL.

    Returns None if the URL is not a valid Health-e Pro menu URL.
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return None

    if parsed.hostname != MENU_HOST:
        return None

    match = HEALTHEPRO_URL_RE.search(parsed.path)
    if not match:
        return None

    return (
        int(match.group("org_id")),
        int(match.group("site_id")),
        int(match.group("menu_id")),
    )


def parse_day(record: dict, meal_type_id: int = MEAL_TYPE_LUNCH) -> MenuDay:
    """Normalize one date_overwrites record into a MenuDay."""
    date_str = record.get("day", "")
    raw_setting = record.get("setting")

    if not raw_setting:
        return MenuDay(
            date=date_str,
            off_day=False,
            off_day_reason=None,
            entrees=[],
            sections={},
            recipe_ids=[],
            notes=["no_setting"],
        )

    try:
        setting = json.loads(raw_setting)
    except (json.JSONDecodeError, TypeError):
        _LOGGER.warning("Failed to parse setting JSON for day %s", date_str)
        return MenuDay(
            date=date_str,
            off_day=False,
            off_day_reason=None,
            entrees=[],
            sections={},
            recipe_ids=[],
            notes=["parse_error"],
        )

    # Off-day check — authoritative signal
    days_off = setting.get("days_off")
    if isinstance(days_off, dict) and days_off.get("status") == 1:
        return MenuDay(
            date=date_str,
            off_day=True,
            off_day_reason=days_off.get("description"),
            entrees=[],
            sections={},
            recipe_ids=[],
            notes=[],
        )

    # Walk current_display in weight order to build sections
    display_items = setting.get("current_display", [])
    display_items = sorted(display_items, key=lambda x: x.get("weight", 0))

    sections: dict[str, list[str]] = {}
    recipe_ids: list[int] = []
    notes: list[str] = []
    current_section = "_uncategorized"

    for item in display_items:
        item_type = item.get("type")
        name = item.get("name", "")
        raw_item = item.get("item")

        if item_type == "category":
            current_section = name
            if current_section not in sections:
                sections[current_section] = []
        elif item_type == "recipe":
            sections.setdefault(current_section, []).append(name)
            # The API sends recipe IDs sometimes as ints (25141) and sometimes
            # as strings ("25141"), even for the same recipe. Strings appear in
            # days edited after the menu was published.
            if isinstance(raw_item, str) and raw_item.isdigit():
                raw_item = int(raw_item)
            if isinstance(raw_item, int):
                recipe_ids.append(raw_item)
        elif item_type == "text" and name:
            notes.append(name)

    entree_category = MEAL_ENTREE_CATEGORIES.get(meal_type_id, "Lunch Entree")
    entrees = sections.get(entree_category, [])

    # Fallback: if the exact category label isn't found, try case-insensitive match
    if not entrees:
        for key, items in sections.items():
            if "entree" in key.lower() and items:
                entrees = items
                break

    return MenuDay(
        date=date_str,
        off_day=False,
        off_day_reason=None,
        entrees=entrees,
        sections={k: v for k, v in sections.items() if k != "_uncategorized"},
        recipe_ids=recipe_ids,
        notes=notes,
    )


def parse_month(data: list[dict], year: int, month: int, meal_type_id: int) -> MenuMonth:
    """Normalize a full date_overwrites response into a MenuMonth."""
    days = [parse_day(record, meal_type_id) for record in data]
    return MenuMonth(year=year, month=month, days=days)
