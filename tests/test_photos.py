"""Tests for picking the week's recipe photos."""
from __future__ import annotations

import json
from datetime import date

from custom_components.healthepro_menu.const import MEAL_TYPE_LUNCH
from custom_components.healthepro_menu.models import (
    MenuDay,
    MenuMonth,
    RecipeDetail,
    SchoolMenuData,
    week_dates,
)
from custom_components.healthepro_menu.parser import parse_day


def _recipe(rid: int, name: str, image_url: str | None = "https://img/x.png") -> RecipeDetail:
    return RecipeDetail(
        id=rid, name=name, allergens=[], attributes=[], calories=None,
        category="Lunch Entree", image_url=image_url, updated_at="2026-01-01",
    )


def _day(day: str, recipes: list[RecipeDetail], off_day: bool = False) -> MenuDay:
    return MenuDay(
        date=day, off_day=off_day, off_day_reason=None, entrees=[], sections={},
        recipe_ids=[r.id for r in recipes], notes=[],
        recipes={r.id: r for r in recipes},
        recipe_names={r.id: f"{r.name} (menu)" for r in recipes},
    )


def _data(days: list[MenuDay]) -> SchoolMenuData:
    return SchoolMenuData(
        vendor="healthepro", organization_id=99, site_id=755, menu_id=130572,
        organization_name="", site_name="", menu_name="", meal_type_id=2,
        meal_type_label="Lunch", published_months=[], source_url="",
        current_month=MenuMonth(year=2026, month=9, days=days),
    )


def test_week_dates_on_a_weekday_is_this_week():
    assert week_dates(date(2026, 9, 30)) == [date(2026, 9, d) for d in range(28, 31)] + [
        date(2026, 10, 1), date(2026, 10, 2)
    ]


def test_week_dates_on_a_weekend_is_the_coming_week():
    assert week_dates(date(2026, 9, 27))[0] == date(2026, 9, 28)  # Sunday
    assert week_dates(date(2026, 9, 26))[0] == date(2026, 9, 28)  # Saturday


def test_week_photos_dedupes_and_skips_missing_photos_and_off_days():
    burger = _recipe(1, "Chicken Burger")
    mac = _recipe(2, "Mac & Cheese")
    fruit = _recipe(3, "Grapes", image_url=None)
    nachos = _recipe(4, "Nachos")
    data = _data([
        _day("2026-09-28", [mac, burger, fruit]),
        _day("2026-09-29", [burger]),
        _day("2026-09-30", [nachos], off_day=True),
        _day("2026-10-05", [nachos]),  # next week
    ])

    photos = data.week_photos(date(2026, 9, 29))

    assert list(photos) == [2, 1]
    assert photos[2] == (mac, "Mac & Cheese (menu)")


def test_parse_day_records_display_name_per_recipe_id():
    setting = {
        "current_display": [
            {"item": "cust_daily_choices", "weight": 0, "name": "Daily Choices", "type": "category"},
            {"item": "25145", "weight": 1, "name": "Grapes ", "type": "recipe"},
            {"item": 25093, "weight": 2, "name": "Chicken Burger", "type": "recipe"},
        ],
        "days_off": [],
    }
    day = parse_day({"day": "2026-10-06", "setting": json.dumps(setting)}, MEAL_TYPE_LUNCH)
    assert day.recipe_names == {25145: "Grapes ", 25093: "Chicken Burger"}
