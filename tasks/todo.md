# Company Intelligence Agent — Tasks

## Setup
- [x] Init git repo
- [x] Create tasks/todo.md
- [x] Write .env.example and .gitignore
- [x] Write requirements.txt

## Implementation
- [x] Write app.py — config, cache layer, pipeline functions
- [x] Write app.py — UI layout, rate limiting, fallback
- [x] Write README.md

## Verification
- [ ] Smoke test: run locally with a real company name
- [ ] Verify download button works
- [ ] Verify fallback triggers correctly (exhaust rate limit or remove key)

## Post-deploy (after HF Spaces)
- [ ] Generate 2-3 real cached example outputs; replace EXAMPLE_BRIEF stub in app.py
- [ ] Tune prompts based on output quality
- [ ] Add run counter for analytics

## Provider/BYOK UX overhaul (plan: tasks/provider-ux-flows.html)
- [x] BYOK popover: add "App default" radio, on_change clears key, hide key field when default
- [x] Default `provider_select` session state to `"default"`
- [x] Pending-run block: provider/key resolution branch for `"default"`, `force_fresh` flag
- [x] No-key error: provider-aware message
- [x] Auth error: name the provider, run_count untouched
- [x] Skip run_count gate when BYOK present (main + disambig)
- [x] Cache banner: model + date, two-click Rerun fresh / Rerun with X
- [x] Top D3 banner: append AI model on every result (fresh + cached)
- [x] Unit tests still pass (22 passed); `_parse_brief` verified on new + old briefs
- [ ] Manual smoke test (see plan verification steps 1-10)

### Review
All edits scoped to `app.py`. Removed dead `stored_api_key` writes. Provider radio now defaults to `"default"`, which maps to Anthropic + server env var at resolution time. BYOK users bypass both run_count gates (main and disambig). Cache hits render a `⚡` success banner with the parsed AI model and run date, plus a two-click `↺ Rerun fresh` / `↺ Rerun with <Provider>` flow. Fresh results carry the AI model in the top D3 banner alongside the date. Old cached briefs without the AI model line gracefully render as `(model unknown)`. Auth errors now name the rejecting provider; run_count is only incremented after a successful pipeline run (no change needed). `_parse_brief` is unchanged and verified to keep working on both old and new cache formats.
