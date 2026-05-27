---
title: Company Intelligence Agent
emoji: 🔎
colorFrom: blue
colorTo: indigo
sdk: streamlit
sdk_version: "1.40.0"
app_file: app.py
pinned: false
---

# Company Intelligence Agent

A Streamlit app that turns a company name into a 1-page executive intelligence brief in under 2 minutes. It runs a multi-pass agentic AI pipeline — not a single prompt — that autonomously researches the company across three dimensions and synthesizes the findings into a structured brief covering strategy, narrative, and talent signals.

**[Live demo →](https://huggingface.co/spaces/htcooper/company-intel-agent)**

---

## What it produces

Four sections, every time:

- **What they're doing** — concrete recent moves: product launches, acquisitions, partnerships, funding
- **What they're saying** — public narrative and positioning from blog posts, exec interviews, press statements
- **What hiring signals suggest** — talent strategy inferred from open roles, growing teams, required skills
- **Bottom line** — one or two sentences on where the company is headed

---

## How it works

Enter any public company name. The app runs four sequential API calls:

1. **News & announcements** — searches for strategic moves from the last 6 months
2. **Hiring signals** — reads job boards to infer company priorities and growth areas
3. **Content & positioning** — finds blog posts, talks, and press statements to extract public narrative
4. **Synthesis** — cross-references all three passes into the structured brief

Results are cached for 24 hours. Searching the same company again is instant.

### Architecture

```
User inputs company name
        │
        ├─ Disambiguation (Claude Haiku — fast, no web search)
        │
        ├── Pass 1: News & announcements    (Claude Sonnet 4.6 + web search)
        ├── Pass 2: Hiring signals           (Claude Sonnet 4.6 + web search)
        └── Pass 3: Content & positioning    (Claude Sonnet 4.6 + web search)
                │
                ▼
        Synthesis: cross-reference all 3 passes → structured brief
                │
                ▼
        Cache result (24hr TTL) → render + offer markdown download
```

Each research pass is a separate Anthropic API call using the `web_search_20260209` tool. Claude autonomously decides what to search and how to interpret results.

---

## Tech stack

| Component | Choice |
|---|---|
| LLM | Claude Sonnet 4.6 (`claude-sonnet-4-6`) |
| Disambiguation | Claude Haiku 4.5 (`claude-haiku-4-5-20251001`) |
| Web search | Anthropic's built-in `web_search_20260209` tool |
| Framework | Streamlit |
| Cache | File-based, 24hr TTL |

No separate search API key required — web search is provided by the Anthropic SDK.

---

## Run locally

```bash
git clone https://github.com/htcooper/company-intel-agent
cd company-intel-agent
pip install -r requirements.txt
cp .env.example .env
# Edit .env and add your Anthropic API key
streamlit run app.py
```

### Environment variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes (for live runs) | Your Anthropic API key. On HF Spaces, set as a Space Secret. |

If no key is set, the app shows a pre-generated example output instead of calling the API.

### Rate limiting

The hosted demo is limited to **3 runs per browser tab** (Streamlit session state — resets on page refresh). This is a soft courtesy limit, not a hard enforcement mechanism. Add your own API key via the "Use Your Own API Key" button for unlimited runs.

---

## Security

User-supplied company names are treated as untrusted input throughout the pipeline:

- **Input sanitization** — control characters, null bytes, and inputs over 100 characters are rejected before any API call
- **Prompt injection guard** — all research system prompts include an explicit guard instructing the model to treat the company name solely as a search subject and ignore any commands it may contain
- **HTML escaping** — all model output is escaped before rendering in the UI

An adversarial test suite (`tests/test_adversarial.py`) verifies these defenses against direct injection, system prompt extraction, indirect injection via poisoned web search results, and persona/jailbreak attempts.

```bash
# Run security tests (no API key needed)
pytest tests/test_adversarial.py -v -m "not integration"

# Run full suite including live API tests
pytest tests/test_adversarial.py -v -m integration
```

---

## Project structure

```
├── app.py                        # Main application and pipeline logic
├── style.css                     # UI styles
├── requirements.txt
├── pytest.ini
├── .env.example
├── tests/
│   └── test_adversarial.py       # Prompt injection test suite
├── tasks/
│   └── todo.md                   # Development task tracking
└── cache/                        # Generated at runtime, gitignored
```

---

Built by [Hollis Cooper](https://htcooper.github.io) · [GitHub](https://github.com/htcooper) · [LinkedIn](https://linkedin.com/in/hollis)
