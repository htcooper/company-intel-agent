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
