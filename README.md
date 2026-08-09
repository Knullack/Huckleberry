<!-- markdownlint-disable -->

# Huckleberry Home Assistant Integration

Custom Home Assistant integration for Huckleberry data with a quality-first architecture.

## Target Runtime
- Installation method: Home Assistant OS
- Home Assistant Core: 2026.8.1
- Supervisor: 2026.07.5
- Operating System: 18.2
- Frontend: 20260729.6

## Status
This repository is in active development.

Current implementation focus:
- Config flow authentication and child selection.
- Multi-child coordinator architecture.
- Sleep/feed/diaper/pump/activity/health read models.
- Sleep control buttons and services.
- Nursing controls (start, pause, resume, switch side, complete, cancel).
- Event logging services for sleep, nursing, bottle, diaper, potty, growth, pump, activities, and solids.
- Solids catalog services (curated and custom food listing, custom food creation).
- Optional realtime listener mode and session heartbeat hardening.
- Chart-friendly recent history attributes on sleep/feed/diaper entities.
- Chart-friendly recent history attributes for pump/activity/health entities.
- Early analytics signals and prediction scaffolding.

Current limitations:
- This is not yet a full parity replica of the Huckleberry app UI/workflows.
- Generic editing/deleting historical events is not implemented by the upstream public API.

## Goals
- Deliver a strong end-user experience from the Home Assistant UI.
- Follow Home Assistant quality scale practices as closely as possible for a custom integration.
- Keep analytics data-driven and transparent.
- Avoid medical framing in predictions.

## Architecture
- Home Assistant Config Entry + Options Flow.
- Typed API wrapper around huckleberry-api 0.4.3.
- DataUpdateCoordinator for periodic sync.
- Sensor and button entities per child.
- Diagnostics endpoint with redaction.

## Installation (dev)
1. Clone this repository.
2. Copy custom_components/huckleberry into your Home Assistant config custom_components folder.
3. Restart Home Assistant.
4. Add integration from Settings > Devices and Services.

## Privacy and Safety
- Credentials are stored via Home Assistant config entries.
- No credentials should be committed to source control.
- Analytics outputs are statistical estimates from historical behavior, not medical advice.

## Licensing
- This project: Apache-2.0.
- Key dependency huckleberry-api 0.4.3: MIT.
- See THIRD_PARTY_LICENSES.md.
