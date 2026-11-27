---
title: Company Intelligence Agent
emoji: 🔎
colorFrom: blue
colorTo: indigo
sdk: streamlit
sdk_version: "1.56.0"
app_file: app.py
pinned: false
---

# Company Intelligence Agent

A Streamlit app that turns a company name into a 1-page executive intelligence brief in about 2 minutes. It runs a multi-pass agentic AI pipeline — not a single prompt — that autonomously researches the company across four dimensions and synthesizes the findings into a structured brief covering company background, strategy, narrative, and talent signals.

**[Live demo →](https://huggingface.co/spaces/htcooper/company-intel-agent)**

---

## What it produces

An **At a glance** overview, for readers who don't know the company yet:

- **Key facts** — founded (and by whom), headquarters, CEO, headcount, ownership (public ticker or latest private valuation), and main competitors
- **What they do** — what the company sells and to whom, in plain language
- **What sets them apart** — concrete differentiation from the named competitors (business model, technology, distribution, pricing, or market focus)

Followed by four sections on recent strategy:

- **What they're doing** — concrete recent moves: product launches, acquisitions, partnerships, funding
- **What they're saying** — public narrative and positioning from blog posts, exec interviews, press statements
- **What hiring signals suggest** — talent strategy inferred from open roles, growing teams, required skills
- **Bottom line** — one or two sentences on where the company is headed

---

## How it works

Enter any public company name. The app runs four independent research passes **in parallel**, then a synthesis call:

0. **Company profile** (fast model) — founding, HQ, leadership, ownership, what they do, main competitors, and what sets them apart
1. **News & announcements** — searches for strategic moves from the last 12 months
2. **Hiring signals** — reads job boards to infer company priorities and growth areas
3. **Content & positioning** — finds blog posts, talks, and press statements to extract public narrative
4. **Synthesis** — cross-references all four passes into the structured brief

The research passes don't depend on each other, so they run concurrently and the total time is roughly the slowest pass plus synthesis. Progress updates as each pass finishes. If one pass fails (e.g. a timeout), the brief is still built from the other three; if two or more fail, the run stops with an error.

Results are cached for 24 hours per company. Cache hits show a banner with the original provider/model and date, plus a `↺ Rerun fresh` link that regenerates with the currently selected provider (overwriting the cache).

### Architecture

```
User inputs company name
        │
        ├─ Disambiguation (fast model — no web search)
        │
        ├── Pass 0: Company profile        (fast model + web search)      ┐
        ├── Pass 1: News & announcements   (research model + web search)  │ run in
        ├── Pass 2: Hiring signals         (research model + web search)  │ parallel
        └── Pass 3: Content & positioning  (research model + web search)  ┘
                │
                ▼
        Synthesis: cross-reference all 4 passes → structured brief  (synthesis model)
                │
                ▼
        Cache result (24hr TTL) → render + offer markdown download
```

Each research pass is a separate API call. With the Anthropic provider, it uses the `web_search_20260209` tool (or the basic `web_search_20250305` on models that don't support it, such as Haiku 5.5); with OpenAI, the Responses API's `web_search_preview` tool. The model autonomously decides what to search and how to interpret results.

**Model routing.** Each step uses a model sized to the job. With Anthropic: Haiku 5.5 for the factual company-profile pass, Sonnet 5.5 for the news, hiring, and content passes, and Opus 5.5 to write the final brief. Sonnet 5.5 and Opus 5.5 run at `medium` effort with Anthropic's server-side refusal fallback (`fallbacks: "default"`), which reruns a declined request on another model. With OpenAI, GPT-4o-mini handles the profile and GPT-4o the rest.

In a side-by-side test on three companies, this mix cost about 10% less per brief than running everything on Sonnet 4.6, took about 50 seconds instead of 80 for research and synthesis, cited more sources, and produced more current briefs.

**Rate limits.** The SDKs retry rate-limited (429) calls with backoff. If a call is still rate-limited:
- **App default / server keys:** if the server also has the *other* provider's key (`OPENAI_API_KEY` or `ANTHROPIC_API_KEY`), that pass or synthesis reruns on the other provider. Without it, the app shows the pre-generated example brief.
- **Your own key (BYOK):** no cross-provider fallback; the app reports that your account hit its rate limit.

Every brief — both the UI and the downloaded `.md` — ends with an attribution line listing the models that generated it (e.g., `*AI model: Anthropic (claude-opus-5-5, claude-haiku-5-5, claude-sonnet-5-5)*`, plus `· OpenAI fallback (gpt-4o)` if a fallback ran), so cached and shared briefs are always self-describing.

---

## Tech stack

| Component | Choice |
|---|---|
| Research model (Anthropic) | Claude Sonnet 5.5 (`claude-sonnet-5-5`) |
| Synthesis model (Anthropic) | Claude Opus 5.5 (`claude-opus-5-5`) |
| Research + synthesis model (OpenAI) | GPT-4o (`gpt-4o`) |
| Fast model (disambiguation + company profile) | Claude Haiku 5.5 (`claude-haiku-5-5`) / GPT-4o-mini |
| Web search (Anthropic) | `web_search_20260209` tool (Sonnet 5.5); basic `web_search_20250305` (Haiku 5.5) |
| Web search (OpenAI) | `web_search_preview` tool (Responses API) |
| Framework | Streamlit |
| Cache | File-based, 24hr TTL, keyed by company name |

No separate search API key required — web search is provided by whichever LLM provider is selected.

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

> **Windows on ARM:** Streamlit depends on `pyarrow`, which has no native Windows ARM64 wheel. Install the x64 build of Python from python.org (it runs under emulation alongside an ARM64 install) and create the venv with it, e.g. `py -V:3.13 -m venv .venv`. WSL2 also works.

### Environment variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes (App default mode) | Server-side Anthropic key. Powers the "App default" provider option and the free demo runs. On HF Spaces, set as a Space Secret. |
| `OPENAI_API_KEY` | Optional | Server-side key used when a user selects the OpenAI provider without entering their own key, and as the rate-limit fallback for App default runs. |

If neither key is set for the selected provider (and the user hasn't supplied a BYOK key), the app shows a pre-generated example output instead of calling the API.

### Providers & rate limiting

The "🔑 Use Your Own API Key" popover in the topbar exposes three modes:

| Mode | Key source | Models | Rate limit |
|---|---|---|---|
| **App default** (preselected) | Server's `ANTHROPIC_API_KEY` | Claude Opus 5.5 + Sonnet 5.5 + Haiku 5.5 | 3 runs per browser tab |
| **Anthropic** | Your Anthropic key (BYOK) | Claude Opus 5.5 + Sonnet 5.5 + Haiku 5.5 | Unlimited |
| **OpenAI** | Your OpenAI key (BYOK) | GPT-4o + GPT-4o-mini | Unlimited |

The 3-run cap is a soft courtesy limit on the free demo to protect server-side API costs — it resets on page refresh and applies only to the **App default** mode. BYOK users (Anthropic or OpenAI with a key entered) bypass the cap entirely on both the main and disambiguation paths, billed to their own provider account.

Switching providers does not clear the key field automatically, but the field is grayed out when **App default** is selected and the help text notes it's ignored in that mode. Invalid keys produce a provider-aware error (`API key rejected by Anthropic.` / `API key rejected by OpenAI.`) and do not consume a session run.

---

## Security

User-supplied company names are treated as untrusted input throughout the pipeline:

- **Input sanitization** — control characters, null bytes, and inputs over 100 characters are rejected before any API call
- **Prompt injection guard** — all research system prompts include an explicit guard instructing the model to treat the company name solely as a search subject and ignore any commands it may contain
- **HTML escaping** — all model output is escaped before rendering in the UI
- **BYOK key handling** — user-supplied API keys live in Streamlit session state only; they are never logged, persisted, or echoed back. Invalid keys raise a provider-aware error and do not increment the session run counter.

An adversarial test suite (`tests/test_adversarial.py`) verifies these defenses against direct injection, system prompt extraction, indirect injection via poisoned web search results, and persona/jailbreak attempts.

```bash
# Run security, parsing, and pipeline tests (no API key needed)
pytest tests -v -m "not integration"

# Run live API tests
pytest tests/test_adversarial.py -v -m integration
```

`tests/test_parse_brief.py` covers brief parsing, including the At a glance sections and backward compatibility with briefs cached before they existed.

---

## Project structure

```
├── app.py                        # Main application and pipeline logic
├── providers.py                  # LLM adapter factory (Anthropic + OpenAI)
├── style.css                     # UI styles
├── requirements.txt
├── pytest.ini
├── .env.example
├── tests/
│   ├── test_adversarial.py       # Prompt injection test suite
│   ├── test_parse_brief.py       # Brief parsing tests
│   └── test_pipeline.py          # Parallel pipeline, model routing, fallback (offline)
└── cache/                        # Generated at runtime, gitignored
```

---

Built by [Hollis Cooper](https://htcooper.github.io) · [GitHub](https://github.com/htcooper) · [LinkedIn](https://linkedin.com/in/hollis)
