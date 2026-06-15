# TODO — hermes-caido

## Packaging & Dependencies

- [ ] Add `pyproject.toml` with `aiohttp` as a declared dependency
- [ ] Replace hardcoded `~/.hermes/hermes-agent/venv/bin/python3` in `auth_helper.py` with `sys.executable`
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

## Intercept Skill

- [ ] `caido:intercept` — intercept toggle, scope management, rule editing

## Known Issues

- [ ] `caido_onboard` / `caido_health` — event loop conflicts when called from Hermes agent's async context (auth helper subprocess workaround works, but root cause is inherited aiohttp state)
- [ ] `search()` / `recent()` — no automatic scope filtering (Caido doesn't expose "active scope for proxy history" via GraphQL; only intercept scope is available)
