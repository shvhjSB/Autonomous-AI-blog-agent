"""
Streamlit UI for the Autonomous Blog Writing Agent.

Run with:
    streamlit run app.py
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

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

st.markdown(
"""
<style>
.block-container { max-width: 900px; }

h1 { color: #7c3aed; }

img {
    display:block;
    margin:auto;
    max-width:90%;
    border-radius:12px;
}

img:hover{
    transform:scale(1.03);
}

em{
    display:block;
    text-align:center;
    color:gray;
    margin-bottom:20px;
}
</style>
""",
unsafe_allow_html=True,
)

# -------------------------------------------------------
# Sidebar
# -------------------------------------------------------

with st.sidebar:

    st.header("⚙️ Settings")
    st.caption("API keys loaded from `.env`")

    st.divider()

    st.markdown("### Pipeline")

    st.markdown(
"""
1️⃣ Router  
2️⃣ Research  
3️⃣ Planner  
4️⃣ Writers (parallel)  
5️⃣ Image Planner  
6️⃣ Compiler  
7️⃣ SEO Optimizer  
"""
    )


# -------------------------------------------------------
# TOC
# -------------------------------------------------------

def generate_toc(md: str):

    headers = re.findall(r"^## (.*)", md, re.MULTILINE)

    if not headers:
        return ""

    toc = "## Table of Contents\n\n"

    for h in headers:
        anchor = h.lower().replace(" ", "-")
        toc += f"- [{h}](#{anchor})\n"

    return toc


# -------------------------------------------------------
# Blog renderer
# -------------------------------------------------------

def render_blog(md: str):

    lines = md.split("\n")

    for line in lines:

        stripped = line.strip()

        # Skip empty lines
        if not stripped:
            continue

        # Detect markdown image: ![alt](path)
        img_match = re.search(r"!\[(.*?)\]\((.*?)\)", stripped)

        if img_match:

            alt = img_match.group(1)
            path = img_match.group(2)

            img_path = Path("output") / path

            if img_path.exists():

                st.image(
                    str(img_path),
                    caption=alt,
                    use_container_width=True
                )

            else:
                st.warning(f"Image missing: {img_path}")

            continue

        # Fallback: surviving [IMAGE: slug] placeholder
        placeholder_match = re.match(r"\[IMAGE:\s*([^\]]+)\]", stripped)

        if placeholder_match:

            slug = placeholder_match.group(1).strip()
            img_path = Path("output") / "images" / f"{slug}.png"

            if img_path.exists():
                st.image(
                    str(img_path),
                    caption=slug.replace("_", " ").title(),
                    use_container_width=True
                )
            else:
                st.info(f"📷 Diagram: {slug.replace('_', ' ').title()}")

            continue

        st.markdown(line)


# -------------------------------------------------------
# Main UI
# -------------------------------------------------------

st.title("✍️ Autonomous Blog Writing Agent")

st.caption(
"Enter a topic and the AI pipeline will research, plan, write, and illustrate a blog post."
)

topic = st.text_input(
    "Blog Topic",
    placeholder="latest AI breakthroughs in robotics",
)

generate = st.button("🚀 Generate Blog")

# -------------------------------------------------------
# Run Pipeline
# -------------------------------------------------------

if generate and topic:

    logging.basicConfig(level=logging.INFO)

    from blog_agent.graph.pipeline import build_graph
    from blog_agent.state import make_initial_state

    app = build_graph()

    initial_state = make_initial_state(topic)

    with st.spinner("Running autonomous pipeline..."):

        result = app.invoke(initial_state)

    st.session_state.final_md = result.get("final")
    st.session_state.plan_data = result.get("plan")
    st.session_state.seo_meta = result.get("seo_metadata")
    st.session_state.topic = topic


# -------------------------------------------------------
# Display blog
# -------------------------------------------------------

final_md = st.session_state.final_md
plan = st.session_state.plan_data
seo = st.session_state.seo_meta

if final_md:

    st.success(f"Blog generated ({len(final_md):,} characters)")

    if plan:

        with st.expander("📋 Blog Plan"):

            st.write(f"**Title:** {plan.blog_title}")
            st.write(f"**Audience:** {plan.audience}")
            st.write(f"**Tone:** {plan.tone}")
            st.write(f"**Kind:** {plan.blog_kind}")
            st.write(f"**Sections:** {len(plan.tasks)}")

    toc = generate_toc(final_md)

    st.divider()

    render_blog(toc + final_md)

    # --------------------------------------------------
    # Download buttons
    # --------------------------------------------------

    safe_topic = re.sub(r"[^a-zA-Z0-9_ ]", "", st.session_state.topic or "blog")[:40].replace(" ", "_").lower()

    col1, col2 = st.columns(2)

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
            final_md,
            file_name=f"blog_{safe_topic}.html",
            mime="text/html",
        )

    # --------------------------------------------------
    # SEO metadata
    # --------------------------------------------------

    if seo:

        st.divider()

        st.subheader("🔍 SEO Metadata")

        col1, col2 = st.columns(2)

        with col1:

            st.markdown("**SEO Title**")
            st.code(seo.seo_title)

            st.markdown("**Meta Description**")
            st.code(seo.meta_description)

            st.markdown("**Slug**")
            st.code(seo.slug)

            st.markdown("**Keywords**")
            st.write(", ".join(seo.keywords))

        with col2:

            st.markdown("🐦 Twitter Preview")
            st.info(f"**{seo.twitter_title}**\n\n{seo.twitter_description}")

            st.markdown("💼 LinkedIn Preview")
            st.info(f"**{seo.linkedin_title}**\n\n{seo.linkedin_description}")

    # --------------------------------------------------
    # Publish section
    # --------------------------------------------------

    st.divider()
    st.subheader("🚀 Publish Blog")

    st.info(
    
        "⚠️ Demo Mode: Blogs published from this app will appear on the developer's Hashnode blog. "
        "To publish to your own blog, download the Markdown and upload it manually."
    ) 



    blog_title = seo.seo_title if seo else st.session_state.topic
    tags = seo.keywords[:5] if seo else []

    col1, col2 = st.columns(2)

    with col1:

        if st.button("🔷 Publish to Dev.to"):

            from blog_agent.tools.publisher import publish_to_devto

            with st.spinner("Publishing..."):

                res = publish_to_devto(blog_title, final_md, tags)

            if res["success"]:
                st.success("Published to Dev.to!")
                st.link_button("View Post", res["url"])
            else:
                st.error(res["error"])

    with col2:

        if st.button("🟢 Publish to Hashnode"):

            from blog_agent.tools.publisher import publish_to_hashnode

            with st.spinner("Publishing..."):

                res = publish_to_hashnode(blog_title, final_md, tags)

            if res["success"]:
                st.success("Published to Hashnode!")
                st.link_button("View Post", res["url"])
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