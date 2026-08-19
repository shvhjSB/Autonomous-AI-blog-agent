# 🤖 Autonomous AI Blog Agent

An autonomous multi-agent AI system that **researches topics, generates blog posts, creates diagrams, optimizes SEO metadata, and publishes articles** — all automatically using **LangGraph**, **Google Gemini**, and **Streamlit**.

> Runs on Gemini's **free** tier by default — no paid API key required. Set `LLM_PROVIDER=openai` to use OpenAI instead.

---
## Live Demo

Try the Autonomous AI Blog Writing Agent:

https://autonomous-ai-blog-agent-drux4b7gelp4yyine7bwzz.streamlit.app/

---

## 📖 Overview

This project implements a fully autonomous blog writing pipeline. Enter a topic, and the system will:

1. **Route** the topic — decide if web research is needed
2. **Research** the web — search and synthesize evidence via Tavily
3. **Plan** the blog — create a structured outline with exactly 7 sections
4. **Write** all sections — in parallel using LangGraph fan-out
5. **Generate diagrams** — Mermaid for structural diagrams, AI images for illustrations
6. **Optimize SEO** — generate metadata, keywords, social media previews
7. **Publish** — one-click publishing to Dev.to

---

## 🏗️ Architecture

```
START → Router ──┬── Researcher → Planner ──┐
                 └────────────→ Planner    │
                                           ↓
                                   Writers (×N parallel)
                                           ↓
                                   Compiler Subgraph:
                                     merge_sections
                                         ↓
                                     plan_images
                                         ↓
                                   generate_and_export
                                           ↓
                                    SEO Optimizer → END
```

```
autonomous_blog_agent/
├── app.py                         # Streamlit UI
├── main.py                        # CLI entry point
├── requirements.txt
├── .env.example
│
├── blog_agent/
│   ├── config.py                  # Centralized settings (pydantic-settings)
│   ├── design.py                  # Design tokens: palettes, type scale, CSS
│   ├── llm.py                     # LLM client factory & invocation helpers
│   ├── prompts.py                 # All system prompts
│   ├── schemas.py                 # Pydantic models & LangGraph state
│   ├── state.py                   # Initial state factory
│   │
│   ├── agents/
│   │   ├── router.py              # Topic classifier & research decision
│   │   ├── researcher.py          # Web search + evidence synthesis
│   │   ├── planner.py             # Blog outline generator
│   │   ├── writer.py              # Section writer (runs in parallel)
│   │   ├── compiler.py            # Merge, image planning, generation, export
│   │   └── seo_optimizer.py       # SEO metadata generator
│   │
│   ├── graph/
│   │   └── pipeline.py            # LangGraph state-graph wiring
│   │
│   └── tools/
│       ├── search.py              # Tavily web search wrapper
│       ├── images.py              # Image gen (Cloudflare / OpenRouter / Pillow)
│       └── publisher.py           # Dev.to publishing
│
└── output/                        # Generated blogs and images
```

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| **Smart Routing** | Classifies topics as closed-book, hybrid, or open-book |
| **Web Research** | Tavily-powered search with evidence synthesis |
| **Parallel Writing** | LangGraph fan-out writes all sections simultaneously |
| **Diagrams & Images** | Free Mermaid diagrams + free Cloudflare FLUX images |
| **Retro-Arcade UI** | Six swappable pixel-art palettes, shared by the app and the generated article |
| **Citation Verification** | Every cited link checked for invented URLs and dead links — zero LLM calls |
| **SEO Optimization** | Auto-generates title, meta description, keywords, slug, social previews |
| **One-Click Publishing** | Publish directly to Dev.to |
| **Export Options** | Download as Markdown, HTML, or JSON package |

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|-----------|
| Agent Framework | [LangGraph](https://github.com/langchain-ai/langgraph) |
| LLM | Gemini Flash pool w/ quota failover (free) — OpenAI optional |
| Web Search | [Tavily](https://tavily.com/) |
| Diagrams | Mermaid (free) |
| Image Generation | Cloudflare FLUX.2 (free) / OpenRouter / OpenAI |
| Schemas | Pydantic v2 |
| Configuration | pydantic-settings |
| UI | [Streamlit](https://streamlit.io/) |
| Publishing | Dev.to REST API |

---

## 🚀 Installation

```bash
# Clone the repository
git clone https://github.com/shvhjSB/Autonomous-AI-blog-agent.git
cd Autonomous-AI-blog-agent

# Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS / Linux

# Install dependencies
pip install -r requirements.txt
```

---

## ▶️ Running the App

### Streamlit UI (recommended)

```bash
streamlit run app.py
```

### CLI

```bash
python main.py --topic "Introduction to Transformer Architecture"
python main.py --topic "Latest AI breakthroughs in robotics" --verbose
```

---

## 🎨 Design system

`blog_agent/design.py` is the single source of truth for the look, shared by
four surfaces: the Streamlit chrome, the exported HTML article, the Mermaid
diagrams, and the AI illustration prompts. Change a token there and all four
follow.

### Type scale — 16px root, 1.25 ratio

| Token | Size | Use |
|---|---|---|
| `xs` | 12px | Pixel HUD labels, badges |
| `sm` | 14px | Captions, meta |
| `base` | **17px** | Article body, line-height 1.7 |
| `lg` | 20px | Lead paragraph |
| `h3` / `h2` / `h1` | 22 / 28 / 36px | Headings, line-height 1.25 |

**Press Start 2P** for chrome accents only · **Outfit** headings ·
**Inter** body · **JetBrains Mono** code. The pixel font never touches running
text — it has no lowercase rhythm and is unreadable at paragraph length.

### Palettes

| Theme | Primary | Secondary | Accent | Link |
|---|---|---|---|---|
| 🕹️ Arcade *(default)* | `#7C3AED` | `#FF4D8D` | `#22D3EE` | `#6D28D9` |
| 🍄 Mario | `#E5352B` | `#43B047` | `#FBD000` | `#C62828` |
| 🍭 Candy | `#FF4D8D` | `#A855F7` | `#5EEAD4` | `#C2185B` |
| 🌊 Ocean | `#0EA5E9` | `#14B8A6` | `#6366F1` | `#0369A1` |
| 🌅 Sunset | `#F97316` | `#F43F5E` | `#FBBF24` | `#C2410C` |
| ⚡ Neon | `#FF00E5` | `#00F0FF` | `#A3FF12` | `#A21CAF` |

**Accents are decoration, never body text.** Article body is `#14142B` on
`#FFFFFF` (18:1). Each theme carries a separately darkened `link` colour because
several accents — Mario yellow, Neon cyan — fail contrast as text on white; all
six links are verified ≥ 4.5:1.

Switch live from the sidebar, or set `UI_THEME` for CLI runs. The app chrome is
a dark "arcade cabinet"; the article stays light for reading.

### Notes for future edits

- The chrome is styled through Streamlit's **native theme options** in
  `.streamlit/config.toml` (`fontFaces`, `buttonRadius`, `headingFontSizes`, …)
  plus CSS scoped to stable `[data-testid=...]` hooks — not the generated
  `.st-emotion-cache-*` names, which change between releases.
- Streamlit only injects `[[theme.fontFaces]]` families referenced by
  `font`/`headingFont`/`codeFont`. Press Start 2P is used only from custom CSS,
  so `app.py` declares that one itself as a data URI.
- Mermaid diagrams are themed with a `%%{init}%%` directive injected at
  emission. That is the only styling that survives publishing raw markdown to
  Dev.to or GitHub, where stylesheets are stripped.
- The directive also sets `htmlLabels:false`. With HTML labels Mermaid sizes the
  label box from its own text measurement, which disagrees with the browser's
  once a webfont is involved, and every caption loses its last character.

---

## 🔑 Environment Variables

Copy the example file and fill in your API keys:

```bash
cp .env.example .env
```

| Variable | Required | Description |
|----------|----------|-------------|
| `GOOGLE_API_KEY` | ✅ | Gemini API key — powers all LLM calls, and the image fallback. [Free, no card](https://aistudio.google.com/apikey) |
| `TAVILY_API_KEY` | ✅ | Tavily API key (web research) |
| `OPENAI_API_KEY` | ❌ | Only for `LLM_PROVIDER=openai`; also preferred for image generation when set |
| `LLM_PROVIDER` | ❌ | `google` (free, default) or `openai` (paid) |
| `LLM_MODEL` | ❌ | Pin a single model, disabling pool rotation |
| `LLM_MODEL_POOL` | ❌ | Comma-separated main-tier models, walked as each daily quota runs out |
| `LLM_MODEL_LIGHT` | ❌ | Model for router / research / SEO (default: `gemini-flash-lite-latest`) |
| `SECTIONS_PER_POST` | ❌ | Sections per post (default: `7`) |
| `LLM_REQUESTS_PER_MINUTE` | ❌ | Client-side throttle shared by the parallel writers; `0` disables (defaults: `4` / `0`) |
| `LLM_MAX_RETRIES` | ❌ | Retries on transient errors such as 429 (default: `5`) |
| `CLOUDFLARE_ACCOUNT_ID` | ❌ | Cloudflare account ID — **free** image generation |
| `CLOUDFLARE_API_TOKEN` | ❌ | Cloudflare Workers AI token ([free, 10k neurons/day](https://dash.cloudflare.com/profile/api-tokens)) |
| `OPENROUTER_API_KEY` | ❌ | Paid image fallback (~$0.068/image) |
| `DIAGRAM_MODE` | ❌ | `auto` (default), `mermaid`, or `image` |
| `IMAGE_PROVIDER` | ❌ | `cloudflare` (default), `openrouter`, `pollinations`, `openai`, `gemini`, `none` |
| `MAX_IMAGES` | ❌ | Max images per post (default: `5`) |
| `OUTPUT_DIR` | ❌ | Output directory (default: `output`) |
| `UI_THEME` | ❌ | Palette for app, article, diagrams and illustrations: `arcade` (default), `mario`, `candy`, `ocean`, `sunset`, `neon` |
| `CITATION_POLICY` | ❌ | `report` (default), `strip`, or `off` |
| `CITATION_CHECK_LIVE` | ❌ | HTTP-check each cited URL (default: `true`) |
| `DEVTO_API_KEY` | ❌ | Dev.to API key (publishing) |

### Running on the free tier

One blog post makes ~11 LLM calls: router, research, planner, **one per
section** (7), image/diagram planning, and SEO.

**Every Gemini Flash model is capped at 20 requests/day** on the free tier
(measured 2026-08-17 — `gemini-3.7-flash`, `gemini-3.6-flash` and
`gemini-3-flash-preview` all report `RPD=20`). One model alone therefore gets
you about one post per day. Two things fix that without touching quality:

**1. Two tiers.** Quotas are counted *per model*, so the cheap nodes — router,
research synthesis, SEO metadata — run on `gemini-flash-lite-latest`, which has
its own much larger allowance. That leaves the scarce Flash quota entirely for
planning and writing, cutting main-tier usage from ~11 calls to **9**.

**2. A model pool with automatic failover.** Each Flash model has its own
independent 20/day. When one reports its daily quota spent,
`blog_agent/llm.py` moves to the next and carries on:

```
gemini-3-flash-preview → gemini-3.6-flash → gemini-flash-latest → gemini-3.5-flash
```

Four models × 20/day ÷ 9 calls ≈ **8 posts/day**, and quality is unchanged
because any single post is still written end-to-end by one model — rotation
only happens when a model actually runs dry. Override with `LLM_MODEL_POOL`
(comma-separated), or set `LLM_MODEL` to pin one model and disable rotation.

Only *daily* exhaustion rotates. Per-minute limits are waited out by the shared
token-bucket limiter (4 req/min, under the measured 5 RPM ceiling), because
burning a model over a transient blip would waste its remaining allowance.

Practical effect: **a post takes roughly 2–3.5 minutes**. If the whole pool runs
dry, wait for the reset (midnight PT) or set `LLM_PROVIDER=openai`.

> **Model availability:** Google retires pinned Gemini versions for new
> accounts (`gemini-2.5-flash` now returns *"no longer available to new
> users"*), so the defaults use the `-latest` aliases. To see exactly what
> your key can call: `client.models.list()` via `google-genai`.

### Citation verification

The writer is told to cite as `(Source Title – URL)` and to use **only** URLs
from the research evidence. Nothing used to enforce that, so a model inventing
a plausible-looking URL shipped straight into the post — the single most
damaging failure mode for AI-written technical content.

Every generated post is now checked on two independent axes:

- **Grounded?** — the URL genuinely came from the Tavily evidence pack
- **Live?** — the URL resolves over HTTP

Both are string and network work, so verification makes **no LLM calls** and
costs nothing against the free-tier quota. Results appear in the CLI log, in
the Streamlit UI, and in `citation_report` on the returned state.

| `CITATION_POLICY` | Behaviour |
|---|---|
| `report` (default) | Flag invented and dead citations, leave the text alone |
| `strip` | Also remove them, keeping the sentence and its anchor text intact |
| `off` | Skip verification |

Set `CITATION_CHECK_LIVE=false` to keep it fully offline and instant — grounding
is still checked against the evidence pack.

Comparison is scheme-, `www.`- and trailing-slash-insensitive, URLs inside
fenced code blocks are ignored (illustrative, not claims), and an HTTP 403/5xx
is reported as *unverified* rather than dead, since bot-blocking and outages say
nothing about whether a citation is real.

### Diagrams and images

Visuals are split by **what they are**, controlled with `DIAGRAM_MODE` (default
`auto`):

- **Structural diagrams** — architecture, flowcharts, pipelines, comparisons —
  are emitted as **Mermaid** fenced blocks. The LLM writes diagram *code*, so
  labels are always legible and it costs **nothing**. Renders natively on
  GitHub, and the Streamlit UI + HTML export render it via
  mermaid.js.
- **Pictorial illustrations** go to an image backend (`IMAGE_PROVIDER`).

In practice most technical posts come out 100% Mermaid and spend $0.

This split exists because **no image model renders labels reliably**. Mermaid
handles everything that needs readable text; the image backend only gets
label-free illustrations, where a free model is perfectly good.

| Image backend | Cost | Verdict (measured 2026-08-17) |
|---|---|---|
| `cloudflare` (default, **FLUX.2 klein 4B**) | **free** — 10,000 neurons/day | ~9s. Good structure, occasional label typos |
| `openrouter` (Nano Banana 2) | ~$0.068/image → $0.20–0.34/post | ~10s. Near-perfect labels, but paid |

Cloudflare model choice (`CLOUDFLARE_IMAGE_MODEL`) — all draw on the same free
10,000 neurons/day:

| Model | Speed | Label accuracy | Rough images/day |
|---|---|---|---|
| `flux-2-klein-4b` (default) | ~9s | Good — minor typos ("API Gatwey") | dozens |
| `flux-2-dev` | ~60s | **Perfect** — all four labels correct | **~3** |
| `flux-1-schnell` | ~3s | Poor — "Backend" → "Bactvicre" | ~170 |

> **Neuron cost is not what the price list implies.** Cloudflare's published
> per-tile figures suggest flux-2-dev costs ~150 neurons; measured, it burns
> roughly **3,000** and exhausts the daily allocation in about three images.
> Budget from observed usage, not arithmetic. When the allocation runs out the
> API returns `429 ... used up your daily free allocation`, the pipeline falls
> through to the next backend, and finally to a placeholder — the post still
> completes.

Use `flux-2-dev` when a single diagram really must have correct labels;
`flux-1-schnell` when you want volume and don't need text.

> FLUX.2 needs a **multipart** request (it rejects a JSON body with
> `required properties at '/' are 'multipart'`), while flux-1-schnell needs
> JSON. `blog_agent/tools/images.py` picks the right shape per model.
| `openai` (`gpt-image-1`) | ~$0.04–0.16/post | Also very good |
| `gemini` | paid-only | Free-tier keys get `limit: 0` on **every** image model |
| `pollinations` | free, keyless | Only model is `sana` — **cannot render readable labels**; concept art only |
| `none` | free | No images at all |

> The $0.068/image figure is measured, not quoted: two generations moved an
> OpenRouter balance by $0.136. Token-rate arithmetic understates it by ~17x,
> because these models bill far more output tokens per image than a naive
> 1,290-token estimate suggests. Check real spend with `/api/v1/key`.

OpenRouter is **prepaid** — credits are bought upfront and requests 402 when the
balance runs out. There is no invoice and no negative balance, so image spend
cannot exceed what you have loaded.

Because `auto` sends structural diagrams to Mermaid, typical technical posts
generate **no images at all** and cost $0. Set `DIAGRAM_MODE=mermaid` to
guarantee that — pictorial visuals are then skipped entirely. `MAX_IMAGES`
caps the worst case.

> Verified 2026-08-17: every generated Mermaid block was checked against the
> real `mermaid.parse()` and rendered correctly.

If you hit the daily cap, either wait for the reset or set
`LLM_PROVIDER=openai` with an OpenAI key to fall back to the paid path.

---

## ☁️ Deploy on Streamlit Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Connect your GitHub account
3. Select this repository: `shvhjSB/Autonomous-AI-blog-agent`
4. Set **Main file path** to `app.py`
5. Open **Advanced settings → Secrets** and add your API keys:

```toml
GOOGLE_API_KEY = "AIza..."
TAVILY_API_KEY = "tvly-..."
```

6. Click **Deploy**

> **Note:** Streamlit Cloud injects secrets as environment variables. The app uses `pydantic-settings` which reads environment variables automatically — no code changes needed.

---

## 📄 License

MIT
