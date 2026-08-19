"""
Streamlit UI for the Autonomous Blog Writing Agent.

Run with:
    streamlit run app.py
"""

from __future__ import annotations

import base64
import html
import json
import logging
import re
from pathlib import Path

import markdown as md_lib
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

from blog_agent import design

load_dotenv()

# -------------------------------------------------------
# Session State
# -------------------------------------------------------

if "final_md" not in st.session_state:
    st.session_state.final_md = None

if "seo_meta" not in st.session_state:
    st.session_state.seo_meta = None

if "plan_data" not in st.session_state:
    st.session_state.plan_data = None

if "topic" not in st.session_state:
    st.session_state.topic = ""

if "citations" not in st.session_state:
    st.session_state.citations = None

if "ui_theme" not in st.session_state:
    st.session_state.ui_theme = design.DEFAULT_THEME

if "podcast_script" not in st.session_state:
    st.session_state.podcast_script = None

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "transformed_content" not in st.session_state:
    st.session_state.transformed_content = None

if "published_url" not in st.session_state:
    st.session_state.published_url = None



# -------------------------------------------------------
# Page Config
# -------------------------------------------------------

st.set_page_config(
    page_title="Autonomous Blog Writing Agent",
    page_icon="✍️",
    layout="wide",
)

# -------------------------------------------------------
# Styling
# -------------------------------------------------------

_FONT_DIR = Path(__file__).parent / "static" / "fonts"


@st.cache_data(show_spinner=False)
def _pixel_font_face() -> str:
    """Declare Press Start 2P ourselves, as a data URI.

    Streamlit only injects the `[[theme.fontFaces]]` families that are named in
    `theme.font` / `headingFont` / `codeFont`; a family referenced only from
    custom CSS never reaches `document.fonts`, so the pixel text silently fell
    back to Courier. Embedding it here removes that dependency.
    """
    path = _FONT_DIR / "PressStart2P.woff2"
    if not path.exists():
        return ""

    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return (
        '@font-face{font-family:"Press Start 2P";'
        f'src:url(data:font/woff2;base64,{b64}) format("woff2");'
        "font-weight:400;font-style:normal;font-display:swap;}"
    )


def _chrome_css(theme: str) -> str:
    """Arcade cabinet styling layered on top of the native Streamlit theme.

    Only gaps the theme config cannot reach are handled here, and selectors are
    limited to stable `[data-testid=...]` hooks rather than the generated
    `.st-emotion-cache-*` class names, which change between releases.
    """
    return f"""
<style>
{_pixel_font_face()}
{design.css_variables(theme)}

/* Streamlit's own toolbar breaks the cabinet illusion — but the button that
   reopens a collapsed sidebar (stExpandSidebarButton) lives INSIDE that same
   header. Hiding the whole header with visibility:hidden cascades to it too,
   with no way to override it back on — collapse the sidebar once and it's
   gone for good. So the header itself stays laid out (just made invisible as
   a background), and only its decorative children are hidden by name; the
   sidebar toggle is explicitly forced back to visible. */
#MainMenu, footer {{ visibility: hidden; height: 0; }}
header[data-testid="stHeader"] {{ background: transparent; }}
header[data-testid="stHeader"] [data-testid="stMainMenuButton"],
header[data-testid="stHeader"] [data-testid="stToolbarActions"],
header[data-testid="stHeader"] [data-testid="stStatusWidget"] {{ visibility: hidden; }}
header[data-testid="stHeader"] [data-testid="stExpandSidebarButton"] {{
  visibility: visible !important;
}}

.block-container {{ max-width: 1040px; padding-top: 2.2rem; }}

/* ---- Scanline texture over the cabinet ---------------------------------- */
[data-testid="stAppViewContainer"]::before {{
  content: ""; position: fixed; inset: 0; pointer-events: none; z-index: 0;
  background: repeating-linear-gradient(
    180deg, rgba(255,255,255,.022) 0 1px, transparent 1px 3px);
}}
[data-testid="stAppViewContainer"] > * {{ position: relative; z-index: 1; }}

/* ---- Pixel accents ------------------------------------------------------ */
.pixel {{
  font-family: var(--font-pixel);
  letter-spacing: .04em;
  line-height: 1.55;
  text-transform: uppercase;
}}

/* ---- Buttons: chunky, with a hard arcade shadow that depresses on click -- */
[data-testid="stBaseButton-secondary"],
[data-testid="stBaseButton-primary"],
[data-testid="stDownloadButton"] button,
[data-testid="stLinkButton"] a {{
  padding: .95rem 1.15rem !important;
  border: 2px solid var(--pri) !important;
  background: linear-gradient(180deg, var(--cab-panel), #16152a) !important;
  color: var(--cab-text) !important;
  box-shadow: 0 4px 0 0 var(--pri);
  transition: transform .06s ease, box-shadow .06s ease, background .18s ease;
}}
/* Typography has to reach the descendants as well: Streamlit nests the label
   in a stMarkdownContainer that re-declares its own font, so setting this on
   the <button> alone silently loses to the child. Kept separate from the box
   styling above, or every nested node would draw its own border. */
[data-testid="stBaseButton-secondary"],
[data-testid="stBaseButton-primary"],
[data-testid="stDownloadButton"] button,
[data-testid="stLinkButton"] a,
[data-testid="stBaseButton-secondary"] *,
[data-testid="stBaseButton-primary"] *,
[data-testid="stDownloadButton"] button *,
[data-testid="stLinkButton"] a * {{
  font-family: var(--font-pixel) !important;
  font-size: .62rem !important;
  line-height: 1.6 !important;
  text-transform: uppercase;
  letter-spacing: .03em;
  color: var(--cab-text) !important;
}}
[data-testid="stBaseButton-secondary"]:hover,
[data-testid="stBaseButton-primary"]:hover,
[data-testid="stDownloadButton"] button:hover,
[data-testid="stLinkButton"] a:hover {{
  background: linear-gradient(180deg, var(--pri), var(--link)) !important;
  border-color: var(--acc) !important;
  box-shadow: 0 4px 0 0 var(--acc);
}}
[data-testid="stBaseButton-secondary"]:active,
[data-testid="stBaseButton-primary"]:active,
[data-testid="stDownloadButton"] button:active {{
  transform: translateY(4px);
  box-shadow: 0 0 0 0 var(--acc);
}}

/* ---- Text input: cartridge slot ---------------------------------------- */
[data-testid="stTextInput"] input {{
  font-family: var(--font-body) !important;
  font-size: 1.02rem !important;
  padding: .85rem 1rem !important;
  border: 2px solid var(--cab-border) !important;
  background: #0E0E1A !important;
}}
[data-testid="stTextInput"] input:focus {{
  border-color: var(--acc) !important;
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--acc) 22%, transparent) !important;
}}

/* ---- Panels ------------------------------------------------------------- */
[data-testid="stExpander"] {{
  border: 2px solid var(--cab-border) !important;
  border-radius: var(--radius) !important;
  background: var(--cab-panel);
  overflow: hidden;
}}
[data-testid="stExpander"] summary {{
  font-family: var(--font-heading); font-weight: 700; font-size: .95rem;
}}
[data-testid="stExpander"] summary:hover {{ color: var(--acc); }}

/* Alert boxes get a thick left rail instead of Streamlit's pastel fill. */
[data-testid="stAlert"] {{
  border-radius: var(--radius-sm) !important;
  border-left: 5px solid var(--pri) !important;
}}

hr, [data-testid="stDivider"] hr {{
  border: none; height: 2px; opacity: .5;
  background: repeating-linear-gradient(
    90deg, var(--cab-border) 0 8px, transparent 8px 14px);
}}

/* ---- Sidebar control panel --------------------------------------------- */
[data-testid="stSidebar"] {{ border-right: 2px solid var(--cab-border); }}
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {{
  font-family: var(--font-pixel) !important;
  color: var(--acc);
  letter-spacing: .02em;
}}

/* ---- Arcade HUD components (custom markup below) ------------------------ */
.hud {{
  border: 2px solid var(--cab-border);
  border-radius: var(--radius);
  background: linear-gradient(180deg, var(--cab-panel), #17162a);
  padding: 1.1rem 1.25rem;
}}
.hero {{
  border: 2px solid var(--pri);
  border-radius: 18px;
  background:
    radial-gradient(120% 140% at 0% 0%,
      color-mix(in srgb, var(--pri) 26%, transparent) 0%, transparent 55%),
    linear-gradient(180deg, var(--cab-panel), #141327);
  padding: 1.6rem 1.75rem;
  margin-bottom: 1.4rem;
  box-shadow: 0 6px 0 0 color-mix(in srgb, var(--pri) 55%, transparent);
}}
.hero-title {{
  font-family: var(--font-pixel);
  font-size: 1.32rem; line-height: 1.5;
  margin: 0 0 .7rem 0; color: var(--cab-text);
  text-shadow: 3px 3px 0 color-mix(in srgb, var(--pri) 85%, transparent);
}}
.hero-sub {{
  font-family: var(--font-body); font-size: .96rem;
  color: var(--cab-muted); margin: 0;
}}
.badge {{
  display: inline-block; font-family: var(--font-pixel); font-size: .55rem;
  text-transform: uppercase; padding: .42rem .6rem; margin: 0 .35rem .35rem 0;
  border-radius: 999px; border: 2px solid var(--cab-border);
  background: #0F0E1D; color: var(--cab-muted);
}}
.badge.on {{ border-color: var(--acc); color: var(--acc); }}

/* Score tiles replace st.metric, whose internals resist restyling. */
.tiles {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: .7rem; }}
.tile {{
  border: 2px solid var(--cab-border); border-radius: var(--radius);
  background: linear-gradient(180deg, var(--cab-panel), #16152a);
  padding: .85rem .6rem; text-align: center;
}}
.tile .v {{
  font-family: var(--font-pixel); font-size: 1.3rem; color: var(--acc);
  display: block; margin-bottom: .45rem;
}}
.tile .k {{
  font-family: var(--font-pixel); font-size: .48rem; color: var(--cab-muted);
  text-transform: uppercase; letter-spacing: .04em;
}}
.tile.warn {{ border-color: var(--sec); }}
.tile.warn .v {{ color: var(--sec); }}

.steps {{ list-style: none; padding: 0; margin: 0; }}
.steps li {{
  font-family: var(--font-body); font-size: .84rem; color: var(--cab-muted);
  padding: .32rem 0; border-bottom: 1px dashed var(--cab-border);
}}
.steps li:last-child {{ border-bottom: none; }}
.steps .n {{
  font-family: var(--font-pixel); font-size: .5rem;
  color: var(--pri); margin-right: .55rem;
}}

@media (max-width: 900px) {{
  .tiles {{ grid-template-columns: repeat(2, 1fr); }}
  .hero-title {{ font-size: 1rem; }}
}}
@media (prefers-reduced-motion: reduce) {{
  * {{ transition: none !important; }}
  [data-testid="stAppViewContainer"]::before {{ display: none; }}
}}

/* ---- Article preview ----------------------------------------------------
   Scoped to the st.container(key="blog_body") wrapper. These rules used to be
   bare `img`/`em` selectors that leaked into every element on the page, which
   is why captions elsewhere were grey and centred. */
.st-key-blog_body img {{
  display: block; margin: 1.4rem auto; max-width: 92%;
  border-radius: var(--radius); border: 2px solid var(--cab-border);
}}
.st-key-blog_body em {{ color: var(--cab-muted); }}
.st-key-blog_body h1 {{ font-size: 2rem; }}
.st-key-blog_body h2 {{
  border-left: 5px solid var(--pri); padding-left: .6rem; margin-top: 2rem;
}}
.st-key-blog_body a {{ color: var(--acc); }}
[data-testid="stImageCaption"] {{
  font-family: var(--font-body) !important;
  font-size: var(--fs-sm) !important;
  color: var(--cab-muted) !important;
  text-align: center;
}}
</style>
""".strip()


st.markdown(_chrome_css(st.session_state.ui_theme), unsafe_allow_html=True)

# -------------------------------------------------------
# Sidebar
# -------------------------------------------------------

_PIPELINE_STEPS = [
    "Router", "Research", "Planner", "Writers ×7",
    "Diagrams", "Compiler", "SEO",
]


def _port_status() -> list[tuple[str, bool]]:
    """Which credentials are present — read-only, never shows key material."""
    from blog_agent.config import get_settings

    s = get_settings()
    return [
        ("Gemini", bool(s.google_api_key)),
        ("Tavily", bool(s.tavily_api_key)),
        ("Images", bool(s.cloudflare_api_token or s.openrouter_api_key
                        or s.openai_api_key)),
        ("Dev.to", bool(s.devto_api_key)),
    ]

with st.sidebar:

    st.markdown("### 🎛️ Cabinet")

    # Theme picker. Chrome and the HTML export update instantly; newly
    # generated diagrams/illustrations pick this up via UI_THEME at run time.
    chosen = st.radio(
        "Palette",
        options=design.theme_names(),
        format_func=lambda k: design.THEMES[k]["label"],
        index=design.theme_names().index(st.session_state.ui_theme),
        label_visibility="collapsed",
    )

    if chosen != st.session_state.ui_theme:
        st.session_state.ui_theme = chosen
        st.rerun()

    st.divider()

    st.markdown("### 🕹️ Pipeline")
    st.html(
        '<ul class="steps">'
        + "".join(
            f'<li><span class="n">{i}</span>{name}</li>'
            for i, name in enumerate(_PIPELINE_STEPS, start=1)
        )
        + "</ul>"
    )

    st.divider()

    st.markdown("### 🔌 Ports")
    st.html(
        '<div>'
        + "".join(
            f'<span class="badge {"on" if ok else ""}">{"● " if ok else "○ "}{name}</span>'
            for name, ok in _port_status()
        )
        + "</div>"
    )
    st.caption("Loaded from `.env`")


# -------------------------------------------------------
# TOC
# -------------------------------------------------------

def generate_toc(md: str):
    """Build a Table of Contents from the H2 headings in ``md``."""

    # Ignore headings inside fenced code blocks.
    without_code = re.sub(r"(?ms)^[ \t]*```.*?^[ \t]*```[ \t]*$", "", md)

    headers = re.findall(r"^## (.*)", without_code, re.MULTILINE)

    # Skip a TOC we generated on a previous pass.
    headers = [h.strip() for h in headers if h.strip().lower() != "table of contents"]

    if not headers:
        return ""

    toc = "## Table of Contents\n\n"

    for h in headers:
        # GitHub-style anchors: lowercase, punctuation dropped, spaces hyphenated.
        anchor = re.sub(r"[^\w\s-]", "", h.lower()).strip()
        anchor = re.sub(r"\s+", "-", anchor)
        toc += f"- [{h}](#{anchor})\n"

    return toc + "\n"


# -------------------------------------------------------
# HTML export
# -------------------------------------------------------

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
{fonts}
{css}
</style>
</head>
<body>
{body}
</body>
</html>
"""


def _inline_images(html: str) -> str:
    """Replace relative <img src="..."> paths with base64 data URIs.

    Makes the downloaded HTML self-contained, since the reader will not have
    the local ``output/images/`` directory.
    """

    def repl(match: re.Match) -> str:
        src = match.group(1)

        if src.startswith(("http://", "https://", "data:")):
            return match.group(0)

        img_path = Path("output") / src

        if not img_path.exists():
            return match.group(0)

        try:
            encoded = base64.b64encode(img_path.read_bytes()).decode("ascii")
        except Exception:
            return match.group(0)

        suffix = img_path.suffix.lower().lstrip(".") or "png"
        mime = "jpeg" if suffix in ("jpg", "jpeg") else suffix

        return f'src="data:image/{mime};base64,{encoded}"'

    return re.sub(r'src="([^"]+)"', repl, html)


_MERMAID_SCRIPT = """
<script type="module">
  // Dynamic import inside try/catch: a static top-level import that fails
  // (offline reader, blocked CDN) kills the whole module silently and leaves
  // the raw diagram source on the page.
  try {
    const mermaid = (await import(
      "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs")).default;
    // Wait for the embedded webfonts first. Otherwise Mermaid measures label
    // widths using the fallback font, the real font swaps in slightly wider,
    // and every caption loses its last character.
    await document.fonts.ready;
    mermaid.initialize({ startOnLoad: false, securityLevel: "strict" });
    await mermaid.run({ querySelector: "pre.mermaid" });
  } catch (e) {
    document.querySelectorAll("pre.mermaid").forEach(el => {
      el.style.whiteSpace = "pre-wrap";
      el.style.fontSize = "12px";
      el.style.opacity = ".7";
    });
  }
</script>
"""


_EMBEDDED_FONTS = (
    ("Outfit", "Outfit.woff2", "400 800"),
    ("Inter", "Inter.woff2", "400 700"),
    ("JetBrains Mono", "JetBrainsMono.woff2", "400 500"),
)


def _font_faces() -> str:
    """Emit @font-face rules with the woff2 payloads inlined as data URIs.

    The download has to render correctly on a machine that has never seen this
    app, so the fonts travel inside the file rather than being linked.
    """
    rules = []
    for family, filename, weight in _EMBEDDED_FONTS:
        path = _FONT_DIR / filename
        if not path.exists():
            continue
        b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        rules.append(
            f'@font-face{{font-family:"{family}";'
            f'src:url(data:font/woff2;base64,{b64}) format("woff2");'
            f"font-weight:{weight};font-style:normal;font-display:swap;}}"
        )
    return "\n".join(rules)


def build_html(md: str, title: str, theme: str | None = None) -> str:
    """Convert blog markdown into a standalone, self-contained HTML document."""

    # The "toc" extension gives headings id attributes, so the Table of
    # Contents links generated by generate_toc() actually resolve. Its slug
    # rules are the ones generate_toc() mirrors.
    body = md_lib.markdown(
        md,
        extensions=["fenced_code", "tables", "sane_lists", "attr_list", "toc"],
    )

    # python-markdown renders ```mermaid as a highlighted code block; mermaid.js
    # expects <pre class="mermaid"> instead.
    body, n_mermaid = re.subn(
        r'<pre><code class="language-mermaid">(.*?)</code></pre>',
        lambda m: f'<pre class="mermaid">{m.group(1)}</pre>',
        body,
        flags=re.S,
    )

    body = _inline_images(body)

    if n_mermaid:
        body += _MERMAID_SCRIPT

    return _HTML_TEMPLATE.format(
        title=html.escape(title, quote=True),
        fonts=_font_faces(),
        css=design.article_css(theme),
        body=body,
    )


# -------------------------------------------------------
# Mermaid rendering
# -------------------------------------------------------

@st.cache_data(show_spinner=False)
def _cached_html(md: str, title: str, theme: str) -> str:
    """Memoised HTML export.

    `build_html` base64-inlines every image, and Streamlit re-runs the whole
    script on any interaction — including a theme switch — so without this the
    export was rebuilt on every click.
    """
    return build_html(md, title, theme)


def render_mermaid(code: str, height: int = 420):
    """Render a Mermaid diagram inside the Streamlit page."""

    if not code.strip():
        return

    escaped = html.escape(code.strip())

    doc = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<style>
  body {{ margin: 0; background: transparent;
         font-family: Inter, "Segoe UI", sans-serif; font-size: 15px; }}
  .mermaid {{ text-align: center; }}
  .mermaid svg {{ max-width: 100%; height: auto; }}
  /* Sequence-diagram notes carry a fill attribute that beats noteBkgColor. */
  .mermaid .note {{ fill: {design._tint(design.get_theme(
        st.session_state.get("ui_theme"))["accent"], 0.84)} !important;
                    stroke: {design.get_theme(
        st.session_state.get("ui_theme"))["accent"]} !important; }}
  .mermaid .noteText, .mermaid .noteText tspan {{ fill: {design.INK} !important; }}
</style>
</head><body>
<div class="mermaid">{escaped}</div>
<pre id="mmerr" style="display:none;color:#B91C1C;font-size:12px;
     white-space:pre-wrap;text-align:left"></pre>
<script type="module">
  // A diagram that fails should say so rather than dumping raw source.
  try {{
    const mermaid = (await import(
      "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs")).default;
    await document.fonts.ready;   // otherwise labels render clipped
    mermaid.initialize({{ startOnLoad: false, securityLevel: "strict" }});
    await mermaid.run({{ querySelector: ".mermaid" }});
  }} catch (e) {{
    const box = document.getElementById("mmerr");
    box.style.display = "block";
    box.textContent = "Diagram failed to render: " + (e && e.message || e);
  }}
</script>
</body></html>"""

    # components.html is soft-deprecated in favour of st.iframe, but st.iframe
    # takes a src rather than markup — and serving this as a data: URL gives the
    # document an opaque origin, which blocks the cross-origin ES-module import
    # of mermaid.js. The diagram then renders as raw source text. Keep
    # components.html (srcdoc) until st.iframe can accept inline markup.
    components.html(doc, height=height, scrolling=True)

    with st.expander("View diagram source"):
        st.code(code.strip(), language="text")


# -------------------------------------------------------
# Blog renderer
# -------------------------------------------------------

def render_blog(md: str):
    """Render blog markdown, substituting real images for image lines.

    Text is accumulated into blocks and rendered with a single ``st.markdown``
    call per block so that multi-line constructs — fenced code, tables, nested
    lists — survive intact. Only stand-alone image lines are pulled out.
    """

    buffer: list[str] = []
    in_code_fence = False
    mermaid_buf: list[str] | None = None

    def flush():
        if buffer:
            block = "\n".join(buffer).strip()
            if block:
                st.markdown(block)
            buffer.clear()

    for line in md.split("\n"):

        stripped = line.strip()

        # Mermaid blocks are rendered as diagrams rather than shown as code.
        if mermaid_buf is not None:
            if stripped.startswith("```"):
                render_mermaid("\n".join(mermaid_buf))
                mermaid_buf = None
            else:
                mermaid_buf.append(line)
            continue

        if stripped.lower().startswith("```mermaid"):
            flush()
            mermaid_buf = []
            continue

        # Track fenced code blocks — never treat their contents as markup.
        if stripped.startswith("```"):
            in_code_fence = not in_code_fence
            buffer.append(line)
            continue

        if in_code_fence:
            buffer.append(line)
            continue

        # Stand-alone markdown image: ![alt](path)
        img_match = re.fullmatch(r"!\[(.*?)\]\((.*?)\)", stripped)

        if img_match:

            flush()

            alt = img_match.group(1)
            path = img_match.group(2)

            img_path = Path("output") / path

            if img_path.exists():
                st.image(str(img_path), caption=alt, use_container_width=True)
            else:
                st.warning(f"Image missing: {img_path}")

            continue

        # Fallback: surviving [IMAGE: slug] placeholder
        placeholder_match = re.fullmatch(r"\[IMAGE:\s*([^\]]+)\]", stripped)

        if placeholder_match:

            flush()

            slug = placeholder_match.group(1).strip()
            img_path = Path("output") / "images" / f"{slug}.png"

            if img_path.exists():
                st.image(
                    str(img_path),
                    caption=slug.replace("_", " ").title(),
                    use_container_width=True,
                )
            else:
                st.info(f"📷 Diagram: {slug.replace('_', ' ').title()}")

            continue

        buffer.append(line)

    flush()


# -------------------------------------------------------
# Main UI
# -------------------------------------------------------

st.html(
    '<div class="hero">'
    '<p class="hero-title">✍️ Blog&nbsp;Agent</p>'
    '<p class="hero-sub">Seven agents research, plan, write and illustrate a '
    'technical post. Drop in a topic and hit start.</p>'
    "</div>"
)

topic = st.text_input(
    "▸ INSERT TOPIC",
    placeholder="how vector databases power retrieval-augmented generation",
)

generate = st.button("▶ Press Start", type="primary")

# -------------------------------------------------------
# Run Pipeline
# -------------------------------------------------------

if generate and topic:

    logging.basicConfig(level=logging.INFO)

    # Theme the run's diagrams and illustrations to the selected palette. The
    # pipeline still reads settings exactly as it always has — only the value
    # it reads changes.
    import os

    from blog_agent.config import get_settings

    os.environ["UI_THEME"] = st.session_state.ui_theme
    get_settings.cache_clear()

    from blog_agent.graph.pipeline import build_graph
    from blog_agent.state import make_initial_state

    app = build_graph()

    initial_state = make_initial_state(topic)

    with st.spinner("⚡ AGENTS WORKING — researching, writing, illustrating…"):

        result = app.invoke(initial_state)

    st.session_state.final_md = result.get("final")
    st.session_state.plan_data = result.get("plan")
    st.session_state.seo_meta = result.get("seo_metadata")
    st.session_state.citations = result.get("citation_report")
    st.session_state.topic = topic
    st.session_state.podcast_script = None
    st.session_state.chat_history = []
    st.session_state.transformed_content = None



# -------------------------------------------------------
# Display blog
# -------------------------------------------------------

final_md = st.session_state.final_md
plan = st.session_state.plan_data
seo = st.session_state.seo_meta

if not final_md:
    st.html(
        '<div class="hud" style="text-align:center;padding:2.4rem 1.25rem">'
        '<p class="pixel" style="font-size:.8rem;color:var(--acc);margin:0 0 .6rem">'
        "▮ No Signal ▮</p>"
        '<p style="font-family:var(--font-body);color:var(--cab-muted);margin:0">'
        "Insert a topic above and press start.</p>"
        "</div>"
    )

if final_md:

    st.success(f"✅ POST COMPLETE — {len(final_md):,} characters")

    # Creator Suite Tabs
    tab_article, tab_audio, tab_viral, tab_chat, tab_analytics, tab_publish = st.tabs([
        "📖 Blog Post",
        "🎙️ Audio Studio",
        "🎨 Viral Studio",
        "💬 Ask AI & Tone",
        "📊 SEO & Analytics",
        "🚀 Publish & Export",
    ])

    with tab_article:
        if plan:
            with st.expander("📋 Blog Plan"):
                st.write(f"**Title:** {plan.blog_title}")
                st.write(f"**Audience:** {plan.audience}")
                st.write(f"**Tone:** {plan.tone}")
                st.write(f"**Kind:** {plan.blog_kind}")
                st.write(f"**Sections:** {len(plan.tasks)}")

        toc = generate_toc(final_md)

        # st.container(key=...) emits a real wrapper element carrying
        # `st-key-blog_body`. An st.html('<div>') / st.html('</div>') pair does
        # NOT work — Streamlit closes each html block in its own container, so
        # the opening div ends up empty and the article styling targets nothing.
        with st.container(key="blog_body"):
            render_blog(toc + final_md)

        cites = st.session_state.citations
        if cites and cites.get("total"):
            st.divider()
            st.subheader("🔗 Citation Check")
            def _tile(value, label, warn=False):
                cls = "tile warn" if warn else "tile"
                return (f'<div class="{cls}"><span class="v">{value}</span>'
                        f'<span class="k">{label}</span></div>')

            st.html(
                '<div class="tiles">'
                + _tile(cites["total"], "Cited")
                + _tile(cites["grounded"], "Grounded")
                + _tile(len(cites["ungrounded"]), "Invented", bool(cites["ungrounded"]))
                + _tile(len(cites["dead"]), "Dead", bool(cites["dead"]))
                + "</div>"
            )
            if cites["ungrounded"]:
                with st.expander(f"⚠️ {len(cites['ungrounded'])} not in research evidence"):
                    for u in cites["ungrounded"]:
                        st.write(f"- {u}")
            if cites["dead"]:
                with st.expander(f"💀 {len(cites['dead'])} dead link(s)"):
                    for u in cites["dead"]:
                        st.write(f"- {u}")
            if not cites["ungrounded"] and not cites["dead"]:
                st.success("All citations are grounded in the research and resolve.")

    with tab_audio:
        st.subheader("🎙️ 'The Daily AI Break' Podcast Studio")
        st.caption("Synthesize a 2-person conversational AI podcast dialogue & listen directly.")

        from blog_agent.tools.creator_suite import generate_podcast_script

        if not st.session_state.podcast_script:
            if st.button("✨ Synthesize Podcast Script", type="primary"):
                with st.spinner("Synthesizing 2-person host/guest script..."):
                    st.session_state.podcast_script = generate_podcast_script(final_md, st.session_state.topic)
                st.rerun()

        if st.session_state.podcast_script:
            track_title = seo.seo_title if seo else st.session_state.topic
            st.markdown(
                f"""
                <div style="background: linear-gradient(135deg, #1e1b4b 0%, #0f172a 100%); border: 2px solid #6366f1; border-radius: 16px; padding: 1.5rem; margin-bottom: 1.5rem; text-align: center; color: white;">
                    <div style="font-family: var(--font-pixel); font-size: 1rem; color: #a5b4fc; margin-bottom: 0.5rem;">🎙️ NOW PLAYING: THE DAILY AI BREAK</div>
                    <div style="font-size: 1.2rem; font-weight: bold; color: #ffffff; margin-bottom: 1rem;">{html.escape(track_title)}</div>
                    
                    <div style="display: flex; justify-content: center; align-items: flex-end; gap: 4px; height: 35px; margin-bottom: 1.2rem;">
                        <div style="width: 5px; height: 60%; background: #6366f1; border-radius: 3px; animation: bounce 1.2s infinite alternate;"></div>
                        <div style="width: 5px; height: 90%; background: #a855f7; border-radius: 3px; animation: bounce 0.8s infinite alternate 0.2s;"></div>
                        <div style="width: 5px; height: 40%; background: #38bdf8; border-radius: 3px; animation: bounce 1.5s infinite alternate 0.4s;"></div>
                        <div style="width: 5px; height: 100%; background: #6366f1; border-radius: 3px; animation: bounce 1.0s infinite alternate 0.1s;"></div>
                        <div style="width: 5px; height: 75%; background: #a855f7; border-radius: 3px; animation: bounce 1.3s infinite alternate 0.3s;"></div>
                    </div>

                    <style>
                        @keyframes bounce {{
                            0% {{ height: 20%; }}
                            100% {{ height: 100%; }}
                        }}
                    </style>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Speak the dialogue with two distinct voices, one per host, so it
            # sounds like a conversation rather than one narrator.
            turns = []
            for line in st.session_state.podcast_script.splitlines():
                line = line.strip()
                m = re.match(r"^\[([^\]]+)\]\s*:\s*(.+)$", line)
                if not m:
                    continue
                speaker, said = m.group(1).strip(), m.group(2).strip()
                # Keep apostrophes — stripping them turns "isn't" into "isnt".
                said = re.sub(r"[^\w\s.,!?:;'\"-]", "", said)
                if said:
                    turns.append({"speaker": speaker, "text": said})

            if not turns:  # script didn't use the [Name]: format
                turns = [{"speaker": "Narrator",
                          "text": re.sub(r"[^\w\s.,!?:;'\"-]", "",
                                         st.session_state.podcast_script)}]

            # json.dumps produces a valid JS literal. The previous version used
            # html.escape(repr(...)), but <script> contents are NOT HTML-decoded,
            # so the browser saw `&quot;...&#x27;...` — a syntax error that killed
            # the whole script, which is why the button never spoke.
            turns_js = json.dumps(turns)

            web_speech_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
            <style>
                body {{ background: transparent; font-family: sans-serif; text-align: center; margin: 0; padding: 10px; }}
                button {{
                    background: linear-gradient(180deg, #6366f1, #4f46e5); color: white; border: none;
                    padding: 10px 24px; font-size: 14px; font-weight: bold; border-radius: 8px; cursor: pointer;
                    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4); transition: transform 0.1s;
                }}
                button:hover {{ transform: scale(1.04); background: #4338ca; }}
                button:active {{ transform: scale(0.98); }}
                #status {{ color: #a5b4fc; font-size: 12px; margin-top: 8px; min-height: 16px; }}
            </style>
            </head>
            <body>
                <button id="play">▶️ Listen to Podcast</button>
                <button id="stop" style="background: #ef4444; margin-left: 8px;">⏹️ Stop</button>
                <div id="status"></div>
                <script>
                    const TURNS = {turns_js};
                    const status = document.getElementById("status");
                    const synth = window.speechSynthesis;

                    if (!synth) {{
                        status.textContent = "This browser has no speech engine. Chrome or Edge will work.";
                        document.getElementById("play").disabled = true;
                    }}

                    // Voices load asynchronously; on a cold page they are not
                    // ready on first click.
                    function pickVoices() {{
                        const all = synth.getVoices().filter(v => v.lang.startsWith("en"));
                        if (!all.length) return [null, null];
                        const female = all.find(v => /female|zira|samantha|aria|jenny/i.test(v.name));
                        const male = all.find(v => /male|david|guy|george|mark/i.test(v.name));
                        return [female || all[0], male || all[Math.min(1, all.length - 1)]];
                    }}

                    function speakAll() {{
                        synth.cancel();
                        const [vA, vB] = pickVoices();
                        const speakers = [...new Set(TURNS.map(t => t.speaker))];
                        TURNS.forEach((turn, i) => {{
                            const u = new SpeechSynthesisUtterance(turn.text);
                            const isFirst = turn.speaker === speakers[0];
                            if (vA && vB) u.voice = isFirst ? vA : vB;
                            u.rate = 1.02;
                            u.pitch = isFirst ? 1.12 : 0.92;
                            if (i === 0) u.onstart = () => status.textContent =
                                "Playing " + TURNS.length + " lines…";
                            if (i === TURNS.length - 1) u.onend = () => status.textContent = "Finished.";
                            u.onerror = e => status.textContent = "Speech error: " + e.error;
                            synth.speak(u);
                        }});
                    }}

                    document.getElementById("play").onclick = () => {{
                        if (!synth.getVoices().length) {{
                            // Trigger the async load, then start once ready.
                            synth.onvoiceschanged = () => {{ synth.onvoiceschanged = null; speakAll(); }};
                            status.textContent = "Loading voices…";
                            synth.getVoices();
                            setTimeout(() => {{ if (!synth.speaking) speakAll(); }}, 600);
                        }} else {{
                            speakAll();
                        }}
                    }};
                    document.getElementById("stop").onclick = () => {{
                        synth.cancel(); status.textContent = "Stopped.";
                    }};
                </script>
            </body>
            </html>
            """
            components.html(web_speech_html, height=110)

            st.markdown("### 📝 Podcast Transcript")
            st.text_area("Transcript", st.session_state.podcast_script, height=320)

    with tab_viral:
        st.subheader("🎨 Social Media & Viral Graphic Studio")
        st.caption("Auto-generated shareable graphics and slide decks for Twitter/X, LinkedIn & Instagram.")

        from blog_agent.tools.creator_suite import build_social_cards

        doc_title = seo.seo_title if seo else st.session_state.topic
        doc_desc = seo.meta_description if seo else "An in-depth technical analysis."
        doc_keywords = seo.keywords if seo else ["AI", "Tech", "Architecture"]

        cards = build_social_cards(
            doc_title, doc_desc, doc_keywords, st.session_state.topic,
            post_url=st.session_state.get("published_url"),
        )

        if not st.session_state.get("published_url"):
            st.caption(
                "ℹ️ Publish to Dev.to first and the cards' “read full post” "
                "becomes a real link to your article."
            )

        st.markdown("#### 🐦 Twitter / X Header Card")
        st.html(cards["twitter"])

        st.divider()
        st.markdown("#### 💼 LinkedIn Carousel Deck")
        col_l1, col_l2 = st.columns(2)
        with col_l1:
            st.html(cards["linkedin_slide1"])
        with col_l2:
            st.html(cards["linkedin_slide2"])

        st.divider()
        st.markdown("#### 📸 Instagram Quote Card")
        st.html(cards["instagram"])

    with tab_chat:
        st.subheader("💬 Interactive Reader Assistant & Tone Switcher")

        st.markdown("#### 🎭 Tone Persona Transformer")
        c1, c2, c3 = st.columns(3)
        from blog_agent.tools.creator_suite import transform_blog_tone

        with c1:
            if st.button("👶 ELI5 (Explain Like I'm 5)"):
                with st.spinner("Transforming tone to ELI5..."):
                    st.session_state.transformed_content = transform_blog_tone(final_md, "ELI5")
        with c2:
            if st.button("💼 Tech Executive Summary"):
                with st.spinner("Transforming tone to Executive..."):
                    st.session_state.transformed_content = transform_blog_tone(final_md, "Executive")
        with c3:
            if st.button("🚀 Viral Social Format"):
                with st.spinner("Transforming tone to Viral..."):
                    st.session_state.transformed_content = transform_blog_tone(final_md, "Viral")

        if st.session_state.transformed_content:
            with st.expander("✨ Transformed Article Content", expanded=True):
                st.markdown(st.session_state.transformed_content)

        st.divider()
        st.markdown("#### 💬 Ask questions about this article")
        from blog_agent.tools.creator_suite import answer_blog_question

        user_q = st.text_input("Ask a question:", placeholder="e.g. What is the main bottleneck discussed in section 3?")
        if st.button("Ask Assistant") and user_q:
            with st.spinner("Analyzing article..."):
                ans = answer_blog_question(final_md, user_q)
                st.session_state.chat_history.append({"q": user_q, "a": ans})

        if st.session_state.chat_history:
            for item in reversed(st.session_state.chat_history):
                st.info(f"**Q:** {item['q']}\n\n**A:** {item['a']}")

    with tab_analytics:
        st.subheader("📊 SEO & Readability Analytics Matrix")

        from blog_agent.tools.creator_suite import calculate_readability_metrics

        metrics = calculate_readability_metrics(final_md)

        def _tile(value, label, warn=False):
            cls = "tile warn" if warn else "tile"
            return (f'<div class="{cls}"><span class="v">{value}</span>'
                    f'<span class="k">{label}</span></div>')

        st.html(
            '<div class="tiles">'
            + _tile(f"{metrics['word_count']:,}", "Words")
            + _tile(f"{metrics['flesch_reading_ease']}", "Flesch Ease")
            + _tile(f"Grade {metrics['fk_grade_level']}", "Grade Level")
            + _tile(f"~{metrics['reading_time_minutes']} min", "Read Time")
            + "</div>"
        )

        st.write(f"**Readability Assessment:** {metrics['reading_ease_label']}")

        st.divider()
        st.markdown("#### 🗝️ Top Keyword Density Cloud")
        kw_cols = st.columns(4)
        for idx, kw in enumerate(metrics["keywords"]):
            with kw_cols[idx % 4]:
                st.metric(label=kw["word"].upper(), value=f"{kw['density']}%", delta=f"{kw['count']} mentions")

        if seo:
            st.divider()
            st.markdown("#### 🔍 SEO Metadata Summary")
            col_s1, col_s2 = st.columns(2)
            with col_s1:
                st.markdown("**SEO Title:**")
                st.code(seo.seo_title)
                st.markdown("**Meta Description:**")
                st.code(seo.meta_description)
            with col_s2:
                st.markdown("**URL Slug:**")
                st.code(seo.slug)
                st.markdown("**Target Keywords:**")
                st.write(", ".join(seo.keywords))

    with tab_publish:
        st.subheader("🚀 Download & Publish Studio")

        safe_topic = re.sub(r"[^a-zA-Z0-9_ ]", "", st.session_state.topic or "blog")[:40].replace(" ", "_").lower()
        from blog_agent.tools.publisher import create_export_package

        doc_title = seo.seo_title if seo else (st.session_state.topic or "Blog")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.download_button(
                "⬇️ Download Markdown",
                final_md,
                file_name=f"blog_{safe_topic}.md",
                mime="text/markdown",
            )
        with col2:
            st.download_button(
                "⬇️ Download HTML",
                _cached_html(final_md, doc_title, st.session_state.ui_theme),
                file_name=f"blog_{safe_topic}.html",
                mime="text/html",
            )
        with col3:
            st.download_button(
                "⬇️ Download JSON Package",
                create_export_package(
                    doc_title,
                    final_md,
                    seo.model_dump() if seo else None,
                ),
                file_name=f"blog_{safe_topic}.json",
                mime="application/json",
            )

        st.divider()
        st.markdown("#### 🔷 Dev.to One-Click Publishing")
        st.info("Publishing uses the `DEVTO_API_KEY` from your `.env` to publish directly to your Dev.to account.")
        blog_title = seo.seo_title if seo else st.session_state.topic
        tags = seo.keywords[:5] if seo else []

        if st.button("🔷 Publish to Dev.to Now"):
            from blog_agent.tools.publisher import publish_to_devto
            with st.spinner("Publishing..."):
                res = publish_to_devto(blog_title, final_md, tags)
            if res["success"]:
                # Remember it: the social cards link "read full post" here.
                st.session_state.published_url = res["url"]
                st.success("Published to Dev.to!")
                st.link_button("View Post on Dev.to", res["url"])
                st.caption("The Viral Studio cards now link to this post.")
            else:
                st.error(res["error"])



# -------------------------------------------------------
# Previous blogs
# -------------------------------------------------------

output_dir = Path("output")

if output_dir.exists() and not generate:

    md_files = sorted(output_dir.glob("*.md"))

    if md_files:

        st.divider()
        st.subheader("📚 Previous Blogs")

        for f in md_files[:5]:

            with st.expander(f.stem.replace("_", " ").title()):

                md = f.read_text(encoding="utf-8")

                toc = generate_toc(md)

                render_blog(toc + md[:3000])