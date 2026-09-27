"""Unit tests for parser.py."""
from __future__ import annotations

import json

import pytest

from custom_components.healthepro_menu.parser import parse_day, parse_menu_url, parse_month
from custom_components.healthepro_menu.const import MEAL_TYPE_LUNCH, MEAL_TYPE_BREAKFAST


# ── URL parsing ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("url,expected", [
    (
        "https://menus.healthepro.com/organizations/2169/sites/13982/menus/92206",
        (2169, 13982, 92206),
    ),
    (
        "https://menus.healthepro.com/organizations/2169/sites/13982/menus/92206?calendarView=month&date=2026-04-01#today",
        (2169, 13982, 92206),
    ),
    (
        "https://menus.healthepro.com/organizations/999/sites/1/menus/2",
        (999, 1, 2),
    ),
])
def test_parse_menu_url_valid(url, expected):
    assert parse_menu_url(url) == expected


@pytest.mark.parametrize("url", [
    "https://example.com/organizations/2169/sites/13982/menus/92206",
    "https://menus.healthepro.com/organizations/2169",
    "https://menus.healthepro.com/organizations/abc/sites/def/menus/ghi",
    "not-a-url",
    "",
])
def test_parse_menu_url_invalid(url):
    assert parse_menu_url(url) is None


# ── Day parsing ───────────────────────────────────────────────────────────────

def test_parse_school_day(school_day_record):
    day = parse_day(school_day_record, MEAL_TYPE_LUNCH)
    assert day.date == "2026-04-01"
    assert day.off_day is False
    assert day.off_day_reason is None
    # Entrées should include the Puyallup April 1 lunch options
    assert len(day.entrees) >= 1
    assert "Taco Nachos" in day.entrees
    assert "Hawaiian Pizza" in day.entrees
    # Sections should include Vegetables, Fruit, Milk
    assert "Vegetables" in day.sections
    assert "Fruit" in day.sections
    assert "Milk" in day.sections
    # Recipe IDs should be collected
    assert len(day.recipe_ids) > 0


def test_parse_spring_break(spring_break_record):
    day = parse_day(spring_break_record, MEAL_TYPE_LUNCH)
    assert day.date == "2026-04-07"
    assert day.off_day is True
    assert day.off_day_reason == "Spring Break"
    assert day.entrees == []
    assert day.sections == {}


def test_parse_day_missing_setting():
    record = {"day": "2026-04-15", "setting": None}
    day = parse_day(record, MEAL_TYPE_LUNCH)
    assert day.date == "2026-04-15"
    assert day.off_day is False
    assert "no_setting" in day.notes


def test_parse_day_malformed_setting():
    record = {"day": "2026-04-15", "setting": "NOT VALID JSON {{{"}
    day = parse_day(record, MEAL_TYPE_LUNCH)
    assert day.date == "2026-04-15"
    assert "parse_error" in day.notes
    assert day.entrees == []


def test_parse_day_category_ordering():
    """Verify items are sorted by weight and assigned to the preceding category."""
    # Categories precede their recipes in weight — this mirrors real API data
    setting = {
        "current_display": [
            {"item": "Lunch Entree", "weight": 0, "name": "Lunch Entree", "type": "category"},
            {"item": 100, "weight": 1, "name": "Pizza", "type": "recipe"},
            {"item": "Fruit", "weight": 10, "name": "Fruit", "type": "category"},
            {"item": 101, "weight": 11, "name": "Apple", "type": "recipe"},
        ],
        "days_off": [],
        "available_recipes": [],
        "hidden_items": [],
        "daily_meal_items": [],
    }
    record = {"day": "2026-05-01", "setting": json.dumps(setting)}
    day = parse_day(record, MEAL_TYPE_LUNCH)
    assert "Pizza" in day.entrees
    assert "Apple" in day.sections.get("Fruit", [])


def test_parse_day_string_recipe_ids():
    """Recipe IDs sent as strings are kept, as ints, in display order."""
    # Trimmed from the real 2026-09-30 record for Bellevue SD elementary lunch
    # (org 99, menu 130572): an edited day that mixes string and int IDs.
    setting = {
        "current_display": [
            {"item": "cust_featured_entree(s)", "weight": 0, "name": "Featured Entree(s)", "type": "category"},
            {"item": "1490667", "weight": 1, "name": "Macaroni & Cheese with Wheat Roll", "type": "recipe"},
            {"item": "cust_daily_choices", "weight": 2, "name": "Daily Choices", "type": "category"},
            {"item": 25093, "weight": 3, "name": "Chicken Burger", "type": "recipe"},
        ],
        "days_off": [],
    }
    record = {"day": "2026-09-30", "setting": json.dumps(setting), "overwritten": True}
    day = parse_day(record, MEAL_TYPE_LUNCH)
    assert day.recipe_ids == [1490667, 25093]
    assert day.entrees == ["Macaroni & Cheese with Wheat Roll"]


# ── Month parsing ─────────────────────────────────────────────────────────────

def test_parse_month(april_overwrites):
    month = parse_month(april_overwrites, 2026, 4, MEAL_TYPE_LUNCH)
    assert month.year == 2026
    assert month.month == 4
    assert len(month.days) == 22  # 22 records in April fixture

    apr1 = month.get_day("2026-04-01")
    assert apr1 is not None
    assert apr1.off_day is False

    apr7 = month.get_day("2026-04-07")
    assert apr7 is not None
    assert apr7.off_day is True

    # Day not in month
    assert month.get_day("2026-05-01") is None
