# hass-poolcop v3.0.0 (aiopoolcop) — TODO

## Blockers

- [ ] **OAuth2 client credentials** — Need third-party OAuth2 credentials from PoolCop to test against the cloud API.
- [ ] **Manual testing** — Blocked on credentials. Verify full config flow and entity creation in a live HA instance.

## Features

- [ ] **Bulk provisioning** — Add "All devices" option to config flow for pool maintainers managing multiple pools.
- [ ] **Shared coordinator** — One coordinator per OAuth2 account using `ExpandState=true` to fetch all devices in a single call. Verify response shape first.
- [ ] **PKCE support** — Investigate public client support to simplify distribution.

## Improvements

- [ ] **Additional test coverage** — Tests for new timer, history, and settings sensors/binary sensors.
- [ ] **Config flow migration v2→v3** — Add formal migration handler.
- [ ] **AutoChlor / Ioniser sensors** — Add when hardware is available for testing.
- [ ] **Alarm history entities** — Expose per-alarm history from cloud API.
- [ ] **BigPool analytics** — Historical data points and aggregations.

## Housekeeping

- [ ] **HACS compatibility** — Verify hacs.json and repo structure.
- [ ] **Add `.gitignore`**
