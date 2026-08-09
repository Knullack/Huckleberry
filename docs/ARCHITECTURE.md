<!-- markdownlint-disable -->

# Architecture

## Layers
- Config Flow and Options Flow for UI setup and reconfiguration.
- API wrapper around huckleberry-api 0.4.3.
- DataUpdateCoordinator for periodic sync.
- Sensor and button entities scoped per child.
- Diagnostics endpoint with redaction.

## Data model
- ChildProfile: stable child identity and display name.
- SleepTimer: live timer state.
- SleepEvent, FeedEvent, DiaperEvent: normalized event records.
- AnalyticsSnapshot: derived statistical metrics and predictions.
- ChildSnapshot: aggregate data for one child.

## Runtime strategy
- Poll at configurable intervals.
- Compute live sleep duration locally from timerStartTime.
- Guard write actions by current timer state.
- Keep prediction language probabilistic and non-medical.
