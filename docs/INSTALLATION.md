<!-- markdownlint-disable -->

# Installation

## Prerequisites
- Home Assistant with custom integration support.
- Huckleberry account credentials.
- Network connectivity to Huckleberry backend.

Tested target runtime:
- Installation method: Home Assistant OS
- Core: 2026.8.1
- Supervisor: 2026.07.5
- Operating System: 18.2
- Frontend: 20260729.6

## Manual install
1. Copy custom_components/huckleberry into your Home Assistant config custom_components folder.
2. Restart Home Assistant.
3. Open Settings > Devices and Services.
4. Add Huckleberry integration.
5. Enter email, password, and timezone.
6. Select one or more children.

## HACS install (planned)
HACS metadata is included. Publish the repository first, then add as a custom repository in HACS.
