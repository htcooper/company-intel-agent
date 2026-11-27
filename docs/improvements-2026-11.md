# Company Intelligence Agent — November 2026 improvements

A round of improvements to the multi-agent research pipeline: a new company overview section, concurrent research passes, per-step model routing backed by a side-by-side model evaluation, and cross-provider fallback for rate limits.

## Results at a glance

| | Before | After |
|---|---|---|
| Time to generate a brief | ~5–6 min (passes ran one after another) | ~45 s (Figma, measured end to end) |
| Cost per brief (Anthropic) | ~$0.52 | ~$0.49 |
| Sources cited by research passes | 32–38 | 45–60 |
| Research passes cut off by the output cap | 3 of 3 on every brief | none |
| Brief sections | 4 (recent strategy only) | 7 (company overview + recent strategy) |
| Offline tests | 22 | 61 |

Cost and source figures come from a side-by-side run on Ramp, CrowdStrike, and Linear (see [Model choice](#3-model-choice-refinement)). Costs include web search fees.

---

## 1. "At a glance" company overview

**Problem.** The brief covered only recent moves (what the company is doing, saying, and hiring for). A reader unfamiliar with the company had no orientation.

**Change.** A new research pass, *Pass 0: Company profile*, looks up founding year and founders, headquarters, CEO, headcount, ownership (public ticker or latest private valuation), main competitors, and concrete differentiation. Synthesis now produces three new sections ahead of the existing four:

- **Key facts:** a structured list rendered as a facts box. A fact that isn't in the research is left out rather than guessed.
- **What they do:** two plain-language sentences for someone who has never heard of the company.
- **What sets them apart:** differentiation measured against the named competitors (business model, technology, distribution, pricing, or market focus), not marketing copy.

**Details.**
- Briefs cached before this change have no overview sections; the parser returns empty values and the UI skips the band, so old cache entries still render.
- The downloadable Markdown brief includes the new sections automatically.

## 2. Concurrent research passes

**Problem.** Four research passes ran one after another, each a web-search API call taking 20–60 seconds, so a brief took 5–6 minutes. The passes don't depend on each other — each receives only the company name — so the wait was unnecessary.

**Change.** The four passes now run in parallel (a thread pool), and synthesis runs once they finish. Total time is roughly the slowest pass plus synthesis.

**Details.**
- **Streamlit threading.** Streamlit calls aren't safe from worker threads, so workers only make API calls. The main thread collects results as they complete and updates the progress display ("✓ Hiring signals (3/4)").
- **Deterministic output.** Results are reassembled in a fixed order (profile, news, hiring, content) before synthesis and source collection. The prompt and the source list don't depend on which pass happened to finish first.
- **Partial failure policy.** If one pass fails (e.g. a timeout), synthesis proceeds with a placeholder and the prompt's existing "say when information is missing" rule handles the gap. If two or more fail, or an API key is rejected, the run stops with a clear error and cancels any calls that haven't started.
- **Measured.** With the original models, the first parallel run took 85 s, down from ~5–6 minutes. With the model changes below, a brief takes ~45 s.

## 3. Model choice refinement

Each step now uses a model sized to its job:

| Step | Anthropic | OpenAI |
|---|---|---|
| Company profile (factual lookup) | Claude Haiku 5.5 | GPT-4o-mini |
| News, hiring, content research | Claude Sonnet 5.5 | GPT-4o |
| Synthesis (writes the brief) | Claude Opus 5.5 | GPT-4o |
| Company-name disambiguation | Claude Haiku 5.5 | GPT-4o-mini |

Previously, every Anthropic step except disambiguation ran on Claude Sonnet 4.6.

### Fast model: Haiku 4.5 → Haiku 5.5

Haiku 5.5 costs about a tenth as much as Haiku 4.5 ($0.10 / $0.50 vs $1 / $5 per million input/output tokens). In a side-by-side test on three companies, its profiles were *better*:
- It flagged conflicting sources instead of picking one. For Linear, Haiku 4.5 stated a $2.5B valuation as fact, while Haiku 5.5 noted it came from a single aggregator it couldn't verify.
- It led with the profile instead of filler text ("I'll search for…").

The evaluation also caught two regressions before they shipped:
1. **Thinking consumed the output budget.** Haiku 5.5 thinks by default, and thinking counts toward `max_tokens`. The disambiguation call's 256-token cap left no room for an answer, so the call returned nothing. Caps on fast-model calls were raised.
2. **More literal instruction-following.** For non-company input, the shared prompt-injection guard says to reply *only* with "This does not appear to be a valid company name." Haiku 5.5 did exactly that instead of returning the expected JSON. The parse failed, and the fallback treated the input as a valid company. The classifier now maps that sentence to "invalid".

### Research and synthesis: Sonnet 4.6 → Sonnet 5.5 + Opus 5.5

Three configurations were run on the same three companies (Ramp, CrowdStrike, Linear), all sharing the same company-profile pass so only the compared steps differed:

| | A: Sonnet 4.6 (previous) | B: Sonnet 5.5 | C: Sonnet 5.5 + Opus 5.5 synthesis (chosen) |
|---|---|---|---|
| Cost per brief | $0.50–0.53 (avg $0.52) | $0.40–0.46 (avg $0.44) | $0.45–0.51 (avg $0.49) |
| Research + synthesis time | 79–86 s | 36–43 s | 47–54 s |
| Sources cited in research | 32–38 | 45–60 | 45–60 |
| Research passes cut off at the output cap | 9 of 9 | 0 | 0 |
| Refusals (incl. CrowdStrike, a security company) | — | 0 | 0 |

**Key finding: the previous setup was silently truncating its research.** Every Sonnet 4.6 research pass hit its 2048-token output cap, so briefs were built on cut-off research. In the Ramp brief, "What they're doing" described 2025 (a $32B valuation) and missed the October 2026 raise at $60B. The CrowdStrike brief missed the latest quarterly results. Raising the cap to 8000 tokens fixes this for any model.

**Why C over B.** B was the cheapest and fastest, and its research was current and careful. For example, it noted that Ramp's hiring showed no sign of IPO preparation, where A had predicted an IPO. C uses the same research but has Opus 5.5 write the synthesis, which produced tighter prose and sharper specifics: it framed CrowdStrike's Zscaler deal as a move onto Palo Alto's turf, and quoted job requirements verbatim with salary ranges. That costs about $0.05 and 10 seconds more per brief than B. C is still cheaper (about 5%) and faster than the previous setup.

**Model settings.**
- Sonnet 5.5 and Opus 5.5 run at `medium` effort.
- Research and synthesis caps were raised to 8000 tokens to leave room for thinking.
- Both use Anthropic's server-side refusal fallback (`fallbacks: "default"`), which reruns a declined request on another model. If a research pass is still refused, it counts as a failed pass; a refused synthesis shows a clear message instead of a generic error.
- The web search tool version is chosen per model. Sonnet 5.5 uses the dynamic-filtering `web_search_20260209`; Haiku needs the basic `web_search_20250305`.

## 4. Fallback provider integration and rate-limit handling

**Problem.** Running four passes at once on the app's shared demo key raises the chance of hitting per-minute rate limits (429s), especially since web search results make each call token-heavy.

**Change.** Rate limits are handled in layers, and handling differs by who owns the key:

1. **SDK retries.** Both SDKs retry 429s and server errors with backoff; retries were raised from 2 to 4.
2. **App default (shared server key).** If a call is still rate-limited and the server also has the *other* provider's key, that pass — or the synthesis — reruns on the other provider's model of the same tier (e.g. Haiku 5.5 → GPT-4o-mini). If the fallback also fails, the original rate-limit error is reported. Without a second key, the app shows the pre-generated example brief, as before.
3. **Bring-your-own-key.** No cross-provider fallback; the user supplied a single key, and their usage shouldn't spill onto the app's account. The app says "Your Anthropic account hit its rate limit — wait a minute and try again" instead of showing the example brief, which was confusing for someone using their own key.

**Attribution.** Every brief ends with a line listing every model that contributed, including any fallback — e.g. `Anthropic (claude-opus-5-5, claude-haiku-5-5, claude-sonnet-5-5) · OpenAI fallback (gpt-4o-mini)`. Cached and shared briefs stay self-describing.

**Verified live.** A full brief with OpenAI as the provider (13.5 s), and a simulated 429 on an Anthropic call that switched to OpenAI. OpenAI briefs are noticeably thinner (about 20 sources vs 45–60, and more generic differentiation), which is acceptable for an occasional fallback.

## 5. Smaller fixes

- **Tracking parameters removed from sources.** OpenAI's web search appends `?utm_source=openai` to cited links; `utm_*` parameters are now stripped from all source URLs, which also merges tagged and untagged copies of the same page.
- **Layout fixes** for the new overview band (spacing, and a stray column divider), checked on the live Hugging Face deployment.
- **Docs.** README, in-app "How it works" diagram, `.env.example` (adds the optional `OPENAI_API_KEY`), and a note on running locally on Windows ARM (pyarrow has no ARM64 wheel; use x64 Python or WSL2).

## Testing

The offline test suite grew from 22 to 61 tests, all runnable without an API key:
- **Pipeline tests** (`tests/test_pipeline.py`) replace the provider adapters with fakes that return scripted responses, delays, and errors. They cover concurrency, ordering, model tiers, rate-limit fallback (including fallback that also fails), BYOK behavior, partial failures, refusals, and the exact request options sent to each Anthropic model.
- **Parsing tests** (`tests/test_parse_brief.py`) cover the new sections and backward compatibility with older cached briefs.
- The existing prompt-injection suite (`tests/test_adversarial.py`) now also feeds poisoned content into the new profile pass.

Every model change was verified with live runs before shipping.

## Design decisions and tradeoffs

- **Parallel over sequential:** the passes were already independent, so parallelism cost nothing in quality. The main risks were rate limits and Streamlit's threading rules, handled above.
- **Route by task difficulty, not by provider:** splitting passes across providers would spread rate-limit load but give uneven quality and complicate BYOK. Instead, each provider uses the cheapest model that does each step well, and the other provider is used only as a rate-limit fallback.
- **Opus only where it pays off:** synthesis is a single call that reads all the research, so a stronger model there improves the whole brief for a small cost increase.
- **Measure before switching models:** each change was decided by a side-by-side run on real companies. The runs found two regressions in the new Haiku before release, and a truncation bug that had been degrading every brief.
- **Fail soft, but not silently:** one failed pass still yields a brief; anything worse produces a specific error rather than a thin or misleading brief.

## Commits

| Commit | Change |
|---|---|
| `637d9d5` | Add "At a glance" company overview section |
| `848dac6` | README: describe the overview section |
| `daf1542` | Parallel research passes; Haiku 5.5 for the profile pass; rate-limit fallback |
| `2cc23a7` | Strip `utm_*` tracking parameters from source URLs |
| `2b1e451` | Sonnet 5.5 research + Opus 5.5 synthesis; fix truncated research |

Note: the commit message for `2b1e451` says the new mix is "~10% cheaper per brief"; the measured average is about 5% cheaper (10%+ was the Sonnet-only variant B). The figures in this document and the README are correct.
