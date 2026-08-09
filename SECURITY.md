<!-- markdownlint-disable -->

# Security Policy

## Reporting a vulnerability
Please report vulnerabilities privately to the maintainer before public disclosure.

## Sensitive data handling
- Never commit credentials, tokens, child identifiers, or personal data exports.
- Diagnostics must redact all secrets and identifying fields.
- Logs should avoid raw payload dumps in normal operation.

## Dependency controls
- Pin huckleberry-api to a known version and review updates before upgrades.
- Re-validate third-party licenses and changelogs before release.

## Threat model notes
This integration handles sensitive family and child-tracking data. Prioritize confidentiality, least-privilege data exposure, and clear user controls.
