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

A Streamlit app that turns a company name into a 1-page executive intelligence brief. It runs an agentic AI pipeline — not a single prompt — that autonomously researches the company across three dimensions and synthesizes the findings.

**[Live demo →](https://huggingface.co/spaces/htcooper/company-intel-agent)**

---

## What it does

Enter any company name. The app runs four sequential API calls:

1. **News & announcements** — product launches, funding, partnerships, acquisitions (last 6 months)
2. **Hiring signals** — open roles, growing teams, tech stack patterns, seniority distribution
3. **Content & positioning** — blog posts, exec interviews, conference talks, public narrative
4. **Synthesis** — cross-references all three passes into a structured 1-page brief

Results are cached for 24 hours. Same company searched again → instant result.

## Architecture

```
User inputs company name
        │
        ├── Pass 1: News & announcements    (Claude Sonnet 4.6 + web search)
        ├── Pass 2: Hiring signals           (Claude Sonnet 4.6 + web search)
        └── Pass 3: Content & positioning    (Claude Sonnet 4.6 + web search)
                │
                ▼
        Synthesis call: Cross-reference all 3 passes → structured brief
                │
                ▼
        Cache result (24hr TTL) → render as markdown + offer download
```

Each research pass is a separate Anthropic API call using the `web_search_20260209` tool. Claude autonomously decides what to search and how to interpret the results.

## Tech stack

- **LLM:** Claude Sonnet 4.6 (`claude-sonnet-4-6`)
- **Search:** Anthropic's built-in `web_search_20260209` tool (no separate search API)
- **Framework:** Streamlit
- **Cache:** File-based, 24hr TTL

## Run locally

```bash
git clone https://github.com/htcooper/company-intel-agent
cd company-intel-agent
pip install -r requirements.txt
cp .env.example .env
# Add your Anthropic API key to .env
streamlit run app.py
```

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes (for live runs) | Your Anthropic API key. On HF Spaces, set as a Space Secret. |

If no key is set, the app shows a pre-generated example output.

## Rate limiting

The hosted demo is limited to **3 runs per session** to control costs. Add your own API key in the "Use your own API key" expander for unlimited runs.

---

Built by [Hollis Cooper](https://htcooper.github.io) · [GitHub](https://github.com/htcooper) · [LinkedIn](https://linkedin.com/in/hollis)
