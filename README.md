# 🤖 Autonomous AI Blog Agent

An autonomous multi-agent AI system that **researches topics, generates blog posts, creates diagrams, optimizes SEO metadata, and publishes articles** — all automatically using **LangGraph**, **OpenAI**, and **Streamlit**.

---

## 📖 Overview

This project implements a fully autonomous blog writing pipeline. Enter a topic, and the system will:

1. **Route** the topic — decide if web research is needed
2. **Research** the web — search and synthesize evidence via Tavily
3. **Plan** the blog — create a structured outline with 5–9 sections
4. **Write** all sections — in parallel using LangGraph fan-out
5. **Generate diagrams** — AI-created images per section (architecture diagrams, flowcharts, charts)
6. **Optimize SEO** — generate metadata, keywords, social media previews
7. **Publish** — one-click publishing to Dev.to or Hashnode

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
│       ├── images.py              # Image generation (Gemini / OpenAI / Pillow)
│       └── publisher.py           # Dev.to & Hashnode publishing
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
| **AI Image Generation** | 3-tier fallback: Gemini → OpenAI → Pillow placeholder |
| **SEO Optimization** | Auto-generates title, meta description, keywords, slug, social previews |
| **One-Click Publishing** | Publish directly to Dev.to or Hashnode |
| **Export Options** | Download as Markdown, HTML, or JSON package |

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|-----------|
| Agent Framework | [LangGraph](https://github.com/langchain-ai/langgraph) |
| LLM | OpenAI GPT-4o-mini |
| Web Search | [Tavily](https://tavily.com/) |
| Image Generation | Google Gemini / OpenAI / Pillow |
| Schemas | Pydantic v2 |
| Configuration | pydantic-settings |
| UI | [Streamlit](https://streamlit.io/) |
| Publishing | Dev.to REST API, Hashnode GraphQL API |

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

## 🔑 Environment Variables

Copy the example file and fill in your API keys:

```bash
cp .env.example .env
```

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | ✅ | OpenAI API key (powers all LLM calls) |
| `TAVILY_API_KEY` | ✅ | Tavily API key (web research) |
| `GOOGLE_API_KEY` | ❌ | Google Gemini API key (image generation) |
| `LLM_MODEL` | ❌ | Override LLM model (default: `gpt-4o-mini`) |
| `DEVTO_API_KEY` | ❌ | Dev.to API key (publishing) |
| `HASHNODE_TOKEN` | ❌ | Hashnode personal access token |
| `HASHNODE_PUBLICATION_ID` | ❌ | Hashnode publication ID |

---

## ⚠️ Demo Publishing Notice

> **Blogs published from this app's Streamlit UI will appear on the developer's Hashnode blog** unless you provide your own tokens.
>
> To publish to your own blog:
> 1. Add your own `DEVTO_API_KEY` or `HASHNODE_TOKEN` + `HASHNODE_PUBLICATION_ID` to your environment (`.env` locally, or Secrets on Streamlit Cloud)
> 2. Or download the Markdown and upload it manually to your platform

---

## ☁️ Deploy on Streamlit Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Connect your GitHub account
3. Select this repository: `shvhjSB/Autonomous-AI-blog-agent`
4. Set **Main file path** to `app.py`
5. Open **Advanced settings → Secrets** and add your API keys:

```toml
OPENAI_API_KEY = "sk-..."
TAVILY_API_KEY = "tvly-..."
GOOGLE_API_KEY = "AIza..."
HASHNODE_TOKEN = "your_token"
HASHNODE_PUBLICATION_ID = "your_pub_id"
```

6. Click **Deploy**

> **Note:** Streamlit Cloud injects secrets as environment variables. The app uses `pydantic-settings` which reads environment variables automatically — no code changes needed.

---

## 📄 License

MIT
