from __future__ import annotations

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "huckleberry"

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BUTTON,
    Platform.DATETIME,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SWITCH,
    Platform.TEXT,
]

CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_TIMEZONE = "timezone"
CONF_CHILDREN = "children"
CONF_CHILD_NAMES = "child_names"
CONF_UPDATE_INTERVAL_SECONDS = "update_interval_seconds"
CONF_LOOKBACK_HOURS = "lookback_hours"
CONF_NIGHT_START_HOUR = "night_start_hour"
CONF_NIGHT_END_HOUR = "night_end_hour"
CONF_ENABLE_REALTIME_LISTENERS = "enable_realtime_listeners"
CONF_SESSION_HEARTBEAT_MINUTES = "session_heartbeat_minutes"

DEFAULT_TIMEZONE = "UTC"
DEFAULT_UPDATE_INTERVAL_SECONDS = 300
DEFAULT_LOOKBACK_HOURS = 72
DEFAULT_NIGHT_START_HOUR = 19
DEFAULT_NIGHT_END_HOUR = 7
DEFAULT_ENABLE_REALTIME_LISTENERS = False
DEFAULT_SESSION_HEARTBEAT_MINUTES = 15

DEFAULT_UPDATE_INTERVAL = timedelta(seconds=DEFAULT_UPDATE_INTERVAL_SECONDS)

DATA_CLIENT = "client"
DATA_COORDINATOR = "coordinator"

SERVICE_START_SLEEP = "start_sleep"
SERVICE_COMPLETE_SLEEP = "complete_sleep"
SERVICE_CANCEL_SLEEP = "cancel_sleep"
SERVICE_PAUSE_SLEEP = "pause_sleep"
SERVICE_RESUME_SLEEP = "resume_sleep"
SERVICE_LOG_SLEEP = "log_sleep"
SERVICE_DELETE_SLEEP = "delete_sleep"
SERVICE_LIST_DELETED_INTERVALS = "list_deleted_intervals"
SERVICE_RESTORE_DELETED_INTERVAL = "restore_deleted_interval"
SERVICE_START_NURSING = "start_nursing"
SERVICE_PAUSE_NURSING = "pause_nursing"
SERVICE_RESUME_NURSING = "resume_nursing"
SERVICE_SWITCH_NURSING_SIDE = "switch_nursing_side"
SERVICE_COMPLETE_NURSING = "complete_nursing"
SERVICE_CANCEL_NURSING = "cancel_nursing"
SERVICE_LOG_NURSING = "log_nursing"
SERVICE_LOG_BOTTLE = "log_bottle"
SERVICE_DELETE_BOTTLE = "delete_bottle"
SERVICE_LOG_DIAPER = "log_diaper"
SERVICE_DELETE_DIAPER = "delete_diaper"
SERVICE_LOG_POTTY = "log_potty"
SERVICE_LOG_GROWTH = "log_growth"
SERVICE_LOG_PUMP = "log_pump"
SERVICE_LOG_ACTIVITY = "log_activity"
SERVICE_LOG_SOLIDS = "log_solids"
SERVICE_CREATE_SOLIDS_CUSTOM_FOOD = "create_solids_custom_food"
SERVICE_LIST_SOLIDS_CURATED_FOODS = "list_solids_curated_foods"
SERVICE_LIST_SOLIDS_CUSTOM_FOODS = "list_solids_custom_foods"

SERVICE_NAMES: tuple[str, ...] = (
    SERVICE_START_SLEEP,
    SERVICE_COMPLETE_SLEEP,
    SERVICE_CANCEL_SLEEP,
    SERVICE_PAUSE_SLEEP,
    SERVICE_RESUME_SLEEP,
    SERVICE_LOG_SLEEP,
    SERVICE_DELETE_SLEEP,
    SERVICE_LIST_DELETED_INTERVALS,
    SERVICE_RESTORE_DELETED_INTERVAL,
    SERVICE_START_NURSING,
    SERVICE_PAUSE_NURSING,
    SERVICE_RESUME_NURSING,
    SERVICE_SWITCH_NURSING_SIDE,
    SERVICE_COMPLETE_NURSING,
    SERVICE_CANCEL_NURSING,
    SERVICE_LOG_NURSING,
    SERVICE_LOG_BOTTLE,
    SERVICE_DELETE_BOTTLE,
    SERVICE_LOG_DIAPER,
    SERVICE_DELETE_DIAPER,
    SERVICE_LOG_POTTY,
    SERVICE_LOG_GROWTH,
    SERVICE_LOG_PUMP,
    SERVICE_LOG_ACTIVITY,
    SERVICE_LOG_SOLIDS,
    SERVICE_CREATE_SOLIDS_CUSTOM_FOOD,
    SERVICE_LIST_SOLIDS_CURATED_FOODS,
    SERVICE_LIST_SOLIDS_CUSTOM_FOODS,
)

ATTR_CHILD_UID = "child_uid"
ATTR_CHILD_NAME = "child_name"
ATTR_INTERVAL_ID = "interval_id"
ATTR_LOG_ID = "log_id"
ATTR_COLLECTION = "collection"
ATTR_LIMIT = "limit"
ATTR_START_TIME = "start_time"
ATTR_END_TIME = "end_time"
ATTR_AMOUNT = "amount"
ATTR_UNITS = "units"
ATTR_BOTTLE_TYPE = "bottle_type"
ATTR_SIDE = "side"
ATTR_MODE = "mode"
ATTR_DURATION_SECONDS = "duration_seconds"
ATTR_NOTES = "notes"
ATTR_PEE_AMOUNT = "pee_amount"
ATTR_POO_AMOUNT = "poo_amount"
ATTR_COLOR = "color"
ATTR_CONSISTENCY = "consistency"
ATTR_DIAPER_RASH = "diaper_rash"
ATTR_HOW_IT_HAPPENED = "how_it_happened"
ATTR_WEIGHT = "weight"
ATTR_HEIGHT = "height"
ATTR_HEAD = "head"
ATTR_GROWTH_UNITS = "growth_units"
ATTR_LEFT_AMOUNT = "left_amount"
ATTR_RIGHT_AMOUNT = "right_amount"
ATTR_TOTAL_AMOUNT = "total_amount"
ATTR_LEFT_DURATION_SECONDS = "left_duration_seconds"
ATTR_RIGHT_DURATION_SECONDS = "right_duration_seconds"
ATTR_FOODS = "foods"
ATTR_REACTION = "reaction"
ATTR_FOOD_NOTE_IMAGE = "food_note_image"
ATTR_IMAGE = "image"
ATTR_INCLUDE_ARCHIVED = "include_archived"

ATTR_SLEEPING = "sleeping"
ATTR_SLEEP_PAUSED = "sleep_paused"
ATTR_SLEEP_DURATION_SECONDS = "sleep_duration_seconds"
ATTR_SLEEP_DURATION_TEXT = "sleep_duration"
ATTR_LAST_SLEEP_START = "last_sleep_start"
ATTR_LAST_SLEEP_END = "last_sleep_end"
ATTR_LAST_SLEEP_DURATION_SECONDS = "last_sleep_duration_seconds"
ATTR_LAST_FEED_TIME = "last_feed_time"
ATTR_LAST_FEED_AMOUNT = "last_feed_amount"
ATTR_LAST_FEED_UNITS = "last_feed_units"
ATTR_LAST_DIAPER_TIME = "last_diaper_time"
ATTR_LAST_PUMP_TIME = "last_pump_time"
ATTR_LAST_PUMP_TOTAL_AMOUNT = "last_pump_total_amount"
ATTR_LAST_PUMP_UNITS = "last_pump_units"
ATTR_LAST_ACTIVITY_TIME = "last_activity_time"
ATTR_LAST_ACTIVITY_MODE = "last_activity_mode"
ATTR_LAST_GROWTH_TIME = "last_growth_time"
ATTR_LAST_GROWTH_WEIGHT = "last_growth_weight"
ATTR_LAST_GROWTH_HEIGHT = "last_growth_height"
ATTR_LAST_GROWTH_HEAD = "last_growth_head"
ATTR_NAPS_TODAY = "naps_today"
ATTR_DAY_SLEEP_SECONDS = "day_sleep_seconds"
ATTR_NIGHT_SLEEP_SECONDS = "night_sleep_seconds"
ATTR_NEXT_NAP = "next_nap"
ATTR_NEXT_FEED = "next_feed"
ATTR_NEXT_NAP_OVERDUE_SECONDS = "next_nap_overdue_seconds"
ATTR_NEXT_FEED_OVERDUE_SECONDS = "next_feed_overdue_seconds"
ATTR_SLEEP_CONFIDENCE = "sleep_confidence"
ATTR_FEED_CONFIDENCE = "feed_confidence"
ATTR_RECENT_SLEEP_EVENTS = "recent_sleep_events"
ATTR_RECENT_FEED_EVENTS = "recent_feed_events"
ATTR_RECENT_DIAPER_EVENTS = "recent_diaper_events"
ATTR_RECENT_PUMP_EVENTS = "recent_pump_events"
ATTR_RECENT_ACTIVITY_EVENTS = "recent_activity_events"
ATTR_RECENT_HEALTH_EVENTS = "recent_health_events"
