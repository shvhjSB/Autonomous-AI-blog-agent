"""Shared design system — the single source of truth for how things look.

Four surfaces need to agree visually: the Streamlit chrome, the exported HTML
article, the Mermaid diagrams, and the AI illustrations. Before this module the
brand colour was a `#7C3AED` literal copy-pasted into four files, so they drifted.

Everything here is presentation only. Nothing in this module touches the agent
pipeline; the generators below just emit CSS strings, a Mermaid init directive,
and a prompt fragment.

Readability rules baked in:

* The article body is always near-black on white (~15.8:1). Theme colours are
  decoration — accent bars, links, borders, diagram fills — never body text.
* Each theme carries a deliberately darkened ``link`` colour, because several
  accents (Mario yellow, Neon cyan) fail contrast as text on white.
* The pixel font is chrome-only. It has no lowercase rhythm and is painful for
  more than a few words.
"""

from __future__ import annotations

from typing import Dict

# ---------------------------------------------------------------------------
# Type scale — 16px root, 1.25 ratio
# ---------------------------------------------------------------------------

TYPE_SCALE: Dict[str, str] = {
    "xs": "0.75rem",        # pixel HUD labels, badges
    "sm": "0.875rem",       # captions, meta, figure text
    "base": "1.0625rem",    # article body (17px)
    "lg": "1.25rem",        # lead paragraph
    "h3": "1.375rem",
    "h2": "1.75rem",
    "h1": "2.25rem",        # article h1 (app hero is larger, set in config.toml)
}

LINE_HEIGHT = {"body": "1.7", "heading": "1.25", "tight": "1.15"}

# Font stacks. Families are registered with Streamlit via [[theme.fontFaces]]
# and with the exported HTML via @font-face / system fallbacks.
FONT_PIXEL = '"Press Start 2P", "Courier New", monospace'
FONT_HEADING = '"Outfit", "Segoe UI", system-ui, sans-serif'
FONT_BODY = '"Inter", -apple-system, "Segoe UI", Roboto, sans-serif'
FONT_MONO = '"JetBrains Mono", ui-monospace, SFMono-Regular, Consolas, monospace'


# ---------------------------------------------------------------------------
# Neutrals
# ---------------------------------------------------------------------------

INK = "#14142B"          # article body text
INK_MUTED = "#4A4A6A"    # captions, secondary text
PAPER = "#FFFFFF"        # article background
SURFACE = "#F7F6FD"      # subtle fills (code blocks, table stripes)
BORDER = "#E4E1F5"

# Dark "arcade cabinet" chrome, used by the app only.
CAB_BG = "#12121F"
CAB_PANEL = "#1C1B2E"
CAB_BORDER = "#2E2B47"
CAB_TEXT = "#E8E6F5"
CAB_MUTED = "#9C97C4"


# ---------------------------------------------------------------------------
# Swappable themes
# ---------------------------------------------------------------------------

THEMES: Dict[str, dict] = {
    "arcade": {
        "label": "🕹️ Arcade",
        "primary": "#7C3AED",
        "secondary": "#FF4D8D",
        "accent": "#22D3EE",
        "link": "#6D28D9",
        "illustration": "electric violet, hot pink and cyan",
    },
    "mario": {
        "label": "🍄 Mario",
        "primary": "#E5352B",
        "secondary": "#43B047",
        "accent": "#FBD000",
        "link": "#C62828",
        "illustration": "bright red, grass green and coin yellow",
    },
    "candy": {
        "label": "🍭 Candy",
        "primary": "#FF4D8D",
        "secondary": "#A855F7",
        "accent": "#5EEAD4",
        "link": "#C2185B",
        "illustration": "bubblegum pink, orchid purple and mint",
    },
    "ocean": {
        "label": "🌊 Ocean",
        "primary": "#0EA5E9",
        "secondary": "#14B8A6",
        "accent": "#6366F1",
        "link": "#0369A1",
        "illustration": "sky blue, teal and deep indigo",
    },
    "sunset": {
        "label": "🌅 Sunset",
        "primary": "#F97316",
        "secondary": "#F43F5E",
        "accent": "#FBBF24",
        "link": "#C2410C",
        "illustration": "burnt orange, rose and golden amber",
    },
    "neon": {
        "label": "⚡ Neon",
        "primary": "#FF00E5",
        "secondary": "#00F0FF",
        "accent": "#A3FF12",
        "link": "#A21CAF",
        "illustration": "magenta, electric cyan and acid green on near-black",
    },
}

DEFAULT_THEME = "arcade"


def get_theme(name: str | None = None) -> dict:
    """Return a theme dict, falling back to the default for unknown names."""
    return THEMES.get((name or "").strip().lower(), THEMES[DEFAULT_THEME])


def theme_names() -> list[str]:
    """Theme keys in display order."""
    return list(THEMES.keys())


# ---------------------------------------------------------------------------
# CSS custom properties — shared by app chrome and article
# ---------------------------------------------------------------------------

def css_variables(theme: str | None = None) -> str:
    """Emit the design tokens as CSS custom properties on ``:root``."""
    t = get_theme(theme)

    return f"""
:root {{
  --pri: {t['primary']};
  --sec: {t['secondary']};
  --acc: {t['accent']};
  --link: {t['link']};

  --ink: {INK};
  --ink-muted: {INK_MUTED};
  --paper: {PAPER};
  --surface: {SURFACE};
  --border: {BORDER};

  --cab-bg: {CAB_BG};
  --cab-panel: {CAB_PANEL};
  --cab-border: {CAB_BORDER};
  --cab-text: {CAB_TEXT};
  --cab-muted: {CAB_MUTED};

  --font-pixel: {FONT_PIXEL};
  --font-heading: {FONT_HEADING};
  --font-body: {FONT_BODY};
  --font-mono: {FONT_MONO};

  --fs-xs: {TYPE_SCALE['xs']};
  --fs-sm: {TYPE_SCALE['sm']};
  --fs-base: {TYPE_SCALE['base']};
  --fs-lg: {TYPE_SCALE['lg']};
  --fs-h3: {TYPE_SCALE['h3']};
  --fs-h2: {TYPE_SCALE['h2']};
  --fs-h1: {TYPE_SCALE['h1']};

  --lh-body: {LINE_HEIGHT['body']};
  --lh-heading: {LINE_HEIGHT['heading']};

  --radius: 14px;
  --radius-sm: 8px;
}}
""".strip()


# ---------------------------------------------------------------------------
# Exported article stylesheet
# ---------------------------------------------------------------------------

def article_css(theme: str | None = None) -> str:
    """Stylesheet for the downloadable HTML article.

    Deliberately restrained compared to the app chrome: the pixel font never
    touches running text, the measure is capped near 68 characters, and colour
    is used for structure (accent bars, rules, links) rather than for the prose
    itself.
    """
    t = get_theme(theme)

    return f"""
{css_variables(theme)}

*, *::before, *::after {{ box-sizing: border-box; }}

body {{
  max-width: 68ch;
  margin: 0 auto;
  padding: 3.5rem 1.25rem 6rem;
  font-family: var(--font-body);
  font-size: var(--fs-base);
  line-height: var(--lh-body);
  color: var(--ink);
  background: var(--paper);
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}}

h1, h2, h3, h4 {{
  font-family: var(--font-heading);
  line-height: var(--lh-heading);
  color: var(--ink);
  margin: 2.6rem 0 .85rem;
  text-wrap: balance;
}}
h1 {{
  font-size: var(--fs-h1); font-weight: 800; letter-spacing: -.02em;
  margin-top: 0; padding-bottom: 1rem;
  border-bottom: 4px solid var(--pri);
}}
h2 {{ font-size: var(--fs-h2); font-weight: 700; }}
/* Accent bar in the left margin — the article's main brand cue. */
h2::before {{
  content: ""; display: inline-block;
  width: .32em; height: .82em; margin-right: .5em;
  vertical-align: -.04em; border-radius: 2px;
  background: var(--pri);
}}
h3 {{ font-size: var(--fs-h3); font-weight: 700; color: #2A2A47; }}

p {{ margin: 0 0 1.15rem; }}
/* Lead paragraph: the first one after the title. */
h1 + p {{ font-size: var(--fs-lg); color: #33334F; }}

a {{ color: var(--link); text-underline-offset: .16em;
     text-decoration-thickness: .08em; }}
a:hover {{ background: color-mix(in srgb, var(--acc) 24%, transparent); }}

strong {{ font-weight: 650; }}

ul, ol {{ padding-left: 1.35rem; margin: 0 0 1.15rem; }}
li {{ margin: .35rem 0; }}
li::marker {{ color: var(--pri); }}

blockquote {{
  margin: 1.6rem 0; padding: .9rem 1.15rem;
  border-left: 5px solid var(--pri);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  background: var(--surface);
  color: #3A3A5C;
}}
blockquote p:last-child {{ margin-bottom: 0; }}

/* Code ------------------------------------------------------------------- */
code {{
  font-family: var(--font-mono);
  font-size: .9em;
  background: var(--surface);
  padding: .12em .38em; border-radius: 5px;
  border: 1px solid var(--border);
}}
/* :not(.mermaid) matters — Mermaid renders into a <pre>, and giving it the
   code-block treatment both darkened the diagram and set a monospace size that
   Mermaid measured labels against before drawing them in Inter, which clipped
   every node caption. */
pre:not(.mermaid) {{
  background: #16162A; color: #E6E4F5;
  padding: 1.15rem 1.25rem; border-radius: var(--radius);
  overflow-x: auto; margin: 1.5rem 0;
  border: 1px solid #23223D;
  border-top: 4px solid var(--pri);
  font-size: .875rem; line-height: 1.6;
}}
pre:not(.mermaid) code {{ background: none; padding: 0; border: none;
                          font-size: inherit; color: inherit; }}

pre.mermaid {{
  background: none; border: none; padding: 0;
  margin: 1.9rem auto .6rem; text-align: center;
  /* Family AND size must match the Mermaid themeVariables exactly. Mermaid
     measures node boxes at its configured 15px, but the label <div> inside the
     SVG foreignObject inherits from here — leave this at the article's 17px
     body size and every caption renders wider than its box and gets clipped. */
  font-family: var(--font-body);
  font-size: 15px;
}}
pre.mermaid svg {{ max-width: 100%; height: auto; }}

/* Sequence-diagram notes ship a fill attribute on the rect that beats the
   noteBkgColor theme variable, so they stay Mermaid's default yellow-green
   whatever palette is selected. Override it here. (Only affects our own
   surfaces — on GitHub the notes fall back to Mermaid's default, which is
   still perfectly legible.) */
pre.mermaid .note {{
  fill: {_tint(t['accent'], 0.84)} !important;
  stroke: {t['accent']} !important;
}}
pre.mermaid .noteText, pre.mermaid .noteText tspan {{
  fill: var(--ink) !important;
}}

/* Figures ---------------------------------------------------------------- */
img {{
  display: block; margin: 1.9rem auto .6rem;
  max-width: 100%; height: auto;
  border-radius: var(--radius); border: 1px solid var(--border);
}}
/* The compiler emits captions as a standalone italic line under each figure,
   which markdown wraps in its own <p> — so the caption is `p > em:only-child`,
   not a sibling of the image. */
p > em:only-child, figcaption {{
  display: block; text-align: center;
  font-family: var(--font-body); font-style: normal;
  font-size: var(--fs-sm); color: var(--ink-muted);
  margin: 0 auto 2rem; max-width: 52ch;
  padding-top: .55rem; border-top: 2px solid var(--border);
}}

.mermaid {{ margin: 1.9rem auto .6rem; text-align: center; }}

/* Tables ------------------------------------------------------------------ */
table {{
  border-collapse: collapse; width: 100%; margin: 1.6rem 0;
  font-size: .94rem; display: block; overflow-x: auto;
}}
th, td {{ border: 1px solid var(--border); padding: .6rem .7rem;
          text-align: left; }}
th {{ background: var(--pri); color: #FFF; font-family: var(--font-heading);
      font-weight: 700; }}
tbody tr:nth-child(even) {{ background: var(--surface); }}

hr {{ border: none; height: 3px; margin: 2.6rem 0;
      background: repeating-linear-gradient(
        90deg, var(--pri) 0 10px, transparent 10px 18px); }}

/* Table of contents ------------------------------------------------------- */
h2#table-of-contents + ul {{
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 1rem 1rem 1rem 2.2rem;
  list-style: decimal;
}}

/* Dark mode --------------------------------------------------------------- */
@media (prefers-color-scheme: dark) {{
  body {{ background: #101020; color: #E4E2F2; }}
  h1, h2, h4 {{ color: #F2F0FF; }}
  h3 {{ color: #CFCBEA; }}
  h1 + p {{ color: #B9B5D8; }}
  a {{ color: {t['accent']}; }}
  code {{ background: #1B1B30; border-color: #2A2947; color: #E4E2F2; }}
  blockquote {{ background: #1A1930; color: #C6C2E0; }}
  th, td {{ border-color: #2A2947; }}
  tbody tr:nth-child(even) {{ background: #17162B; }}
  img {{ border-color: #2A2947; }}
  p > em:only-child, figcaption {{ color: #A6A1C8;
                                   border-top-color: #2A2947; }}
  h2#table-of-contents + ul {{ background: #17162B; border-color: #2A2947; }}
}}

/* Print ------------------------------------------------------------------- */
@media print {{
  body {{ max-width: none; padding: 0; font-size: 11pt; color: #000; }}
  pre {{ background: #F4F4F8; color: #111; border-color: #CCC; }}
  a {{ color: #000; text-decoration: underline; }}
  a[href^="http"]::after {{ content: " (" attr(href) ")";
                            font-size: .8em; color: #555; word-break: break-all; }}
  h2 {{ break-after: avoid; }}
  pre, blockquote, img, table {{ break-inside: avoid; }}
}}
""".strip()


# ---------------------------------------------------------------------------
# Mermaid theming
# ---------------------------------------------------------------------------

def _tint(hex_color: str, amount: float) -> str:
    """Mix a colour toward white. ``amount`` 0 = unchanged, 1 = white."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    mix = lambda c: round(c + (255 - c) * amount)  # noqa: E731
    return f"#{mix(r):02X}{mix(g):02X}{mix(b):02X}"


def mermaid_init(theme: str | None = None) -> str:
    """Return a ``%%{init}%%`` directive that themes a Mermaid diagram.

    This is the only styling that survives publishing raw markdown to Dev.to or
    GitHub, where stylesheets are stripped — so it carries the brand on the one
    surface CSS cannot reach.

    Must be prepended at *emission* time, after ``_clean_mermaid`` has validated
    the source: that guard requires the first line to be a diagram keyword and
    would reject a directive-first block.
    """
    t = get_theme(theme)

    # Light tinted fills with a strong themed border, rather than solid blocks
    # of primary: far more legible as body content, and it keeps node labels
    # dark on light instead of white-on-saturated.
    fill = _tint(t["primary"], 0.88)
    fill_alt = _tint(t["secondary"], 0.88)

    variables = {
        "primaryColor": fill,
        "primaryTextColor": INK,
        "primaryBorderColor": t["primary"],
        "secondaryColor": fill_alt,
        "secondaryTextColor": INK,
        "secondaryBorderColor": t["secondary"],
        "tertiaryColor": SURFACE,
        "tertiaryTextColor": INK,
        "tertiaryBorderColor": BORDER,
        "lineColor": INK_MUTED,
        "textColor": INK,
        "mainBkg": fill,
        "nodeBorder": t["primary"],
        "clusterBkg": SURFACE,
        "clusterBorder": BORDER,
        # Without this, edge captions pick up a saturated fill and read as
        # error badges.
        "edgeLabelBackground": PAPER,

        # Sequence diagrams have their own variable set and default to a
        # mustard yellow for notes and section labels, which fights every
        # palette. Pin them too.
        "actorBkg": fill,
        "actorBorder": t["primary"],
        "actorTextColor": INK,
        "actorLineColor": t["primary"],
        "signalColor": INK_MUTED,
        "signalTextColor": INK,
        "labelBoxBkgColor": fill_alt,
        "labelBoxBorderColor": t["secondary"],
        "labelTextColor": INK,
        "loopTextColor": INK,
        "noteBkgColor": _tint(t["accent"], 0.82),
        "noteBorderColor": t["accent"],
        "noteTextColor": INK,
        "activationBkgColor": fill,
        "activationBorderColor": t["primary"],
        "sequenceNumberColor": "#FFFFFF",

        "fontFamily": "Inter, Segoe UI, sans-serif",
        "fontSize": "15px",
    }

    pairs = ",".join(f'"{k}":"{v}"' for k, v in variables.items())

    # htmlLabels:false renders captions as real SVG <text> instead of a <div>
    # inside a <foreignObject>. With HTML labels Mermaid sizes that box from its
    # own text measurement, which disagrees with the browser's once a webfont is
    # involved — measured 21.2px of box for 26px of text — and every label loses
    # its last character. SVG text is laid out by the browser, so it cannot clip.
    # Living in the directive means it also applies on GitHub and Dev.to.
    config = (
        '{"theme":"base","themeVariables":{' + pairs + "},"
        '"htmlLabels":false,"flowchart":{"htmlLabels":false,"useMaxWidth":true}}'
    )
    return "%%{init: " + config + "}%%"


# ---------------------------------------------------------------------------
# Illustration art direction
# ---------------------------------------------------------------------------

def image_style_suffix(theme: str | None = None) -> str:
    """House art-style directive appended to every image prompt.

    Applied at the single choke point in ``images.py`` so all backends produce a
    visually consistent set. Deliberately discourages text: no current model
    renders labels reliably, which is why structural diagrams go to Mermaid.
    """
    t = get_theme(theme)

    return (
        "ART DIRECTION (follow exactly): flat vector illustration, bold rounded "
        f"outlines, generous whitespace, {t['illustration']} accent palette on a "
        "clean white background. Geometric and friendly, subtle grain, no "
        "gradients, no photorealism, no 3D render, no drop shadows. "
        "Do not include any text, letters, numbers or labels in the image."
    )
