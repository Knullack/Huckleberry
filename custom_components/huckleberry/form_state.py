from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

FIELD_ACTIVITY_DATETIME = "activity_datetime"
FIELD_ACTIVITY_DURATION = "activity_duration"
FIELD_ACTIVITY_FORM = "activity_form"
FIELD_ACTIVITY_NOTES = "activity_notes"
FIELD_ACTIVITY_TYPE = "activity_type"

FIELD_BOTTLE_AMOUNT = "bottle_amount"
FIELD_BOTTLE_DATETIME = "bottle_datetime"
FIELD_BOTTLE_FORM = "bottle_form"
FIELD_BOTTLE_TYPE = "bottle_type"
FIELD_BOTTLE_UNITS = "bottle_units"

FIELD_DIAPER_DATETIME = "diaper_datetime"
FIELD_DIAPER_FORM = "diaper_form"
FIELD_DIAPER_MODE = "diaper_mode"
FIELD_DIAPER_NOTES = "diaper_notes"
FIELD_DIAPER_RASH = "diaper_rash"
FIELD_PEE_AMOUNT = "pee_amount"
FIELD_POO_AMOUNT = "poo_amount"
FIELD_POO_COLOR = "poo_color"
FIELD_POO_CONSISTENCY = "poo_consistency"

FIELD_SLEEP_END = "sleep_end"
FIELD_SLEEP_START = "sleep_start"

SELECT_OPTION_NONE = "none"

ACTIVITY_TYPE_OPTIONS: tuple[str, ...] = (
    "bath",
    "tummyTime",
    "storyTime",
    "screenTime",
    "skinToSkin",
    "outdoorPlay",
    "indoorPlay",
    "brushTeeth",
)

BOTTLE_TYPE_OPTIONS: tuple[str, ...] = (
    SELECT_OPTION_NONE,
    "Breast Milk",
    "Formula",
    "Tube Feeding",
    "Cow Milk",
    "Goat Milk",
    "Soy Milk",
    "Other",
)

BOTTLE_UNIT_OPTIONS: tuple[str, ...] = ("ml", "oz")

DIAPER_MODE_OPTIONS: tuple[str, ...] = ("pee", "poo", "both", "dry")

DIAPER_AMOUNT_OPTIONS: tuple[str, ...] = (
    SELECT_OPTION_NONE,
    "little",
    "medium",
    "big",
)

DIAPER_COLOR_OPTIONS: tuple[str, ...] = (
    SELECT_OPTION_NONE,
    "yellow",
    "brown",
    "black",
    "green",
    "red",
    "gray",
)

DIAPER_CONSISTENCY_OPTIONS: tuple[str, ...] = (
    SELECT_OPTION_NONE,
    "solid",
    "loose",
    "runny",
    "mucousy",
    "hard",
    "pebbles",
    "diarrhea",
)


def default_form_values(now: datetime | None = None) -> dict[str, Any]:
    """Return default values for native form entities."""
    resolved_now = now or datetime.now(tz=UTC)
    if resolved_now.tzinfo is None:
        resolved_now = resolved_now.replace(tzinfo=UTC)
    resolved_now = resolved_now.replace(microsecond=0)

    return {
        FIELD_ACTIVITY_DATETIME: resolved_now,
        FIELD_ACTIVITY_DURATION: 0.0,
        FIELD_ACTIVITY_FORM: False,
        FIELD_ACTIVITY_NOTES: "",
        FIELD_ACTIVITY_TYPE: ACTIVITY_TYPE_OPTIONS[0],
        FIELD_BOTTLE_AMOUNT: 0.0,
        FIELD_BOTTLE_DATETIME: resolved_now,
        FIELD_BOTTLE_FORM: False,
        FIELD_BOTTLE_TYPE: SELECT_OPTION_NONE,
        FIELD_BOTTLE_UNITS: BOTTLE_UNIT_OPTIONS[0],
        FIELD_DIAPER_DATETIME: resolved_now,
        FIELD_DIAPER_FORM: False,
        FIELD_DIAPER_MODE: DIAPER_MODE_OPTIONS[0],
        FIELD_DIAPER_NOTES: "",
        FIELD_DIAPER_RASH: False,
        FIELD_PEE_AMOUNT: SELECT_OPTION_NONE,
        FIELD_POO_AMOUNT: SELECT_OPTION_NONE,
        FIELD_POO_COLOR: SELECT_OPTION_NONE,
        FIELD_POO_CONSISTENCY: SELECT_OPTION_NONE,
        FIELD_SLEEP_START: resolved_now - timedelta(hours=1),
        FIELD_SLEEP_END: resolved_now,
    }


def optional_select_value(value: Any) -> str | None:
    """Normalize optional select values to None for service payloads."""
    if not isinstance(value, str):
        return None
    if value == SELECT_OPTION_NONE:
        return None
    cleaned = value.strip()
    return cleaned or None
