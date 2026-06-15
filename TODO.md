# TODO — hermes-caido

## Packaging & Dependencies

- [ ] Add `pyproject.toml` with `aiohttp` as a declared dependency
- [x] ~~Replace hardcoded venv path in `auth_helper.py`~~ — now uses `sys.executable`
- [ ] Install plugin into Hermes venv via `pip install -e .` (editable)
- [ ] Skills import via `import automate` — no `sys.path.insert` needed

## SDK Migration (when SDK >= 0.57.0 + automate)

- [ ] Adopt `caido-sdk-client` as dependency in `pyproject.toml`
- [ ] Swap GraphQL layer from raw aiohttp to SDK client
- [ ] Migrate auth from custom code to `caido-server-auth`
- [ ] Keep skill interface stable (automate.sessions(), placeholders.find_value(), etc.)

## Automate — Remaining Phases

- [ ] Phase 4: Result retrieval — `get_entry_requests()` with HTTPQL filter and ordering
- [ ] Phase 5: Bundle common fuzzing patterns into `caido:automate` skill (IDOR, parameter fuzzing, auth bypass, rate limiting)

## Known Issues

- [x] ~~Hardcoded paths break under Hermes profiles~~ — fixed via `CAIDO_PLUGIN_DIR`, `HERMES_HOME`, `sys.executable`
- [x] ~~`search()` / `recent()` no scope filtering~~ — fixed via active scope state set by `caido_onboard`
- [x] ~~`findings { id }` in onboard query~~ — fixed to `findings { count { value } }`
- [ ] Event loop conflicts in `caido_onboard` / `caido_health` — auth helper subprocess workaround works, but health/graphql calls still run inside agent's event loop
