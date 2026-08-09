<!-- markdownlint-disable -->

# Troubleshooting

## Invalid credentials
- Reopen integration and re-authenticate.
- Confirm email and password are correct in Huckleberry app.

## No children found
- Confirm the account has at least one child profile.
- Re-run setup and verify the correct account is used.

## Entities unavailable
- Check Home Assistant logs for connectivity errors.
- Confirm outbound access to Huckleberry backend.
- Wait for next coordinator refresh cycle.

## Sleep controls disabled
- Start Sleep is disabled when a timer is already active.
- Complete or Cancel is disabled when no timer is active.
- Resume requires an active paused timer.

## Diagnostics
- Use Home Assistant diagnostics export for this config entry.
- Sensitive fields are redacted by design.
