"""
Creator Suite Tools for Autonomous AI Blog Agent.

Provides:
1. Podcast script generation (2-person conversation)
2. Pure Python readability & SEO analytics calculation
3. Blog tone transformer (ELI5, Tech Executive, Viral Social)
4. Article Q&A assistant
5. HTML/CSS Social Media Card & Carousel renderer
"""

from __future__ import annotations

import math
import re
from typing import Any

from blog_agent.llm import invoke_text


# ---------------------------------------------------------------------------
# 1. Readability & Analytics Matrix (Pure Python - 0 API Cost)
# ---------------------------------------------------------------------------

_STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "can't", "cannot", "could",
    "did", "do", "does", "doing", "down", "during", "each", "few", "for", "from",
    "further", "had", "has", "have", "having", "he", "her", "here", "him", "his",
    "how", "i", "if", "in", "into", "is", "it", "its", "just", "me", "more", "most",
    "my", "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or",
    "other", "our", "ours", "out", "over", "own", "same", "she", "should", "so",
    "some", "such", "than", "that", "the", "their", "theirs", "them", "then", "there",
    "these", "they", "this", "those", "through", "to", "too", "under", "until",
    "up", "very", "was", "we", "were", "what", "when", "where", "which", "while",
    "who", "whom", "why", "with", "would", "you", "your", "yours", "yourself",
}


def _count_syllables(word: str) -> int:
    """Estimate syllables in a single English word."""
    word = word.lower().strip()
    if not word:
        return 0
    if len(word) <= 3:
        return 1
    word = re.sub(r'(?:[^laeiouy]|ed|es|e)$', '', word)
    word = re.sub(r'^y', '', word)
    syllables = len(re.findall(r'[aeiouy]{1,2}', word))
    return max(1, syllables)


def calculate_readability_metrics(md_text: str) -> dict[str, Any]:
    """Calculate Flesch Reading Ease, Flesch-Kincaid Grade Level, and keyword density."""

    # 1. Clean markdown elements to get pure prose
    cleaned = re.sub(r"```.*?```", "", md_text, flags=re.S)  # remove code blocks
    cleaned = re.sub(r"!\[.*?\]\(.*?\)", "", cleaned)       # remove images
    cleaned = re.sub(r"\[.*?\]\(.*?\)", "", cleaned)       # remove links
    cleaned = re.sub(r"[#*`_>-]", " ", cleaned)            # remove markdown syntax

    words = [w.lower() for w in re.findall(r"\b[a-zA-Z]{2,}\b", cleaned)]
    sentences = [s.strip() for s in re.split(r"[.!?]+", cleaned) if s.strip()]

    total_words = max(1, len(words))
    total_sentences = max(1, len(sentences))
    total_syllables = sum(_count_syllables(w) for w in words)

    # 2. Formula calculations
    words_per_sentence = total_words / total_sentences
    syllables_per_word = total_syllables / total_words

    flesch_reading_ease = 206.835 - (1.015 * words_per_sentence) - (84.6 * syllables_per_word)
    flesch_reading_ease = max(0.0, min(100.0, flesch_reading_ease))

    fk_grade_level = (0.39 * words_per_sentence) + (11.8 * syllables_per_word) - 15.59
    fk_grade_level = max(1.0, min(18.0, fk_grade_level))

    reading_time_min = math.ceil(total_words / 200.0)

    # 3. Keyword density analysis
    filtered_words = [w for w in words if w not in _STOP_WORDS and len(w) > 3]
    freq: dict[str, int] = {}
    for w in filtered_words:
        freq[w] = freq.get(w, 0) + 1

    sorted_keywords = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:8]
    keyword_cloud = [
        {"word": w, "count": c, "density": round((c / total_words) * 100, 2)}
        for w, c in sorted_keywords
    ]

    # Grade description mapping
    if flesch_reading_ease >= 80:
        ease_label = "Very Easy (5th Grade)"
    elif flesch_reading_ease >= 65:
        ease_label = "Plain English (8th-9th Grade)"
    elif flesch_reading_ease >= 50:
        ease_label = "Fairly Difficult (High School)"
    elif flesch_reading_ease >= 30:
        ease_label = "Difficult (College Level)"
    else:
        ease_label = "Very Academic / Technical"

    # Section counts
    sections = re.findall(r"^##\s+(.*)", md_text, re.MULTILINE)

    return {
        # Report the real counts, not the divide-by-zero guards above —
        # otherwise an empty article claims 1 word and 1 sentence.
        "word_count": len(words),
        "sentence_count": len(sentences),
        "section_count": len(sections),
        "reading_time_minutes": reading_time_min,
        "flesch_reading_ease": round(flesch_reading_ease, 1),
        "reading_ease_label": ease_label,
        "fk_grade_level": round(fk_grade_level, 1),
        "avg_words_per_sentence": round(words_per_sentence, 1),
        "avg_syllables_per_word": round(syllables_per_word, 2),
        "keywords": keyword_cloud,
    }


# ---------------------------------------------------------------------------
# 2. Podcast Script Generator
# ---------------------------------------------------------------------------

def generate_podcast_script(md_text: str, topic: str) -> str:
    """Synthesize a dynamic 2-person podcast audio conversation script."""
    system_prompt = (
        "You are an expert audio script producer for a top technology podcast named 'The Daily AI Break'. "
        "Create an engaging, fast-paced, conversational 2-person podcast dialogue based on the provided technical article.\n\n"
        "Hosts:\n"
        "- [Alex]: The energetic podcast host who asks insightful questions and keeps the conversation fun and accessible.\n"
        "- [Dr. Morgan]: The expert lead engineer who breaks down technical concepts with vivid analogies.\n\n"
        "Rules:\n"
        "1. Start with an exciting intro hook introducing the podcast and the topic.\n"
        "2. Break down 3 major key takeaways or structural insights from the post.\n"
        "3. Use natural dialogue with back-and-forth reactions (e.g. 'That makes so much sense!', 'Here is the kicker...').\n"
        "4. Keep it focused, punchy, and under 400 words total.\n"
        "5. Output ONLY lines starting with [Alex]: or [Dr. Morgan]: without extra commentary."
    )

    user_prompt = f"Topic: {topic}\n\nArticle Content:\n{md_text[:4000]}"

    # invoke_text() carries the model-pool failover (each Gemini Flash model
    # allows only 20 requests/day) and flattens list-form message content,
    # which a bare llm.invoke(...).content.strip() would crash on.
    return invoke_text(system_prompt, user_prompt, tier="light")


# ---------------------------------------------------------------------------
# 3. Tone Transformer
# ---------------------------------------------------------------------------

def transform_blog_tone(md_text: str, target_tone: str) -> str:
    """Rewrite article content into a specific target tone."""
    tone_descriptions = {
        "ELI5": "Rewrite the key concepts of this article so a 5-year-old or beginner can easily understand. Use fun analogies, super simple vocabulary, and zero jargon.",
        "Executive": "Rewrite this article into a high-level C-Suite Executive Summary. Focus on business value, strategic impact, ROI, efficiency gains, and bulleted takeaways.",
        "Viral": "Rewrite this article into a high-energy Viral LinkedIn/Twitter post format. Use short punchy lines, compelling hooks, relevant emojis, and a call-to-action.",
    }

    desc = tone_descriptions.get(target_tone, "Rewrite this article cleanly.")

    system_prompt = (
        f"You are a master content editor. {desc}\n"
        "Maintain markdown formatting with clean headings and bullet points where appropriate."
    )

    return invoke_text(system_prompt, md_text[:4000], tier="light")


# ---------------------------------------------------------------------------
# 4. Article Q&A Assistant
# ---------------------------------------------------------------------------

def answer_blog_question(md_text: str, question: str) -> str:
    """Answer a user question strictly based on the generated blog article."""
    system_prompt = (
        "You are an interactive AI assistant embedded in this blog article. "
        "Answer the user's question accurately and concisely using ONLY facts and details present in the article text below. "
        "If the answer is not mentioned in the article, state that clearly."
    )

    return invoke_text(
        f"{system_prompt}\n\nARTICLE:\n{md_text[:5000]}", question, tier="light"
    )


# ---------------------------------------------------------------------------
# 5. Social Card & Carousel Generator (HTML/CSS)
# ---------------------------------------------------------------------------

def build_social_cards(seo_title: str, description: str, keywords: list[str],
                       topic: str, post_url: str | None = None) -> dict[str, str]:
    """Generate modern, eye-pleasing HTML/CSS templates for Twitter, LinkedIn Carousel, and Instagram."""

    clean_title = seo_title or topic
    clean_desc = description or "An in-depth technical analysis and step-by-step breakdown."
    tags_html = "".join(f'<span class="card-tag">#{k.replace(" ", "")}</span>' for k in keywords[:3])

    # 1. Twitter / X Header Card
    twitter_card = f"""
    <div style="
        width: 100%; max-width: 650px; margin: 0 auto;
        background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #311042 100%);
        border: 2px solid #6366f1; border-radius: 16px; padding: 2rem;
        box-shadow: 0 10px 25px -5px rgba(99, 102, 241, 0.4);
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        color: #ffffff; box-sizing: border-box; text-align: left;
    ">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.2rem;">
            <span style="background: rgba(99, 102, 241, 0.2); color: #a5b4fc; border: 1px solid #6366f1; padding: 0.35rem 0.8rem; border-radius: 999px; font-size: 0.75rem; font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase;">
                🤖 AI Tech Deep Dive
            </span>
            <span style="color: #94a3b8; font-size: 0.85rem;">blog.agent</span>
        </div>
        <h2 style="font-size: 1.5rem; font-weight: 800; line-height: 1.35; margin: 0 0 1rem 0; color: #f8fafc; text-shadow: 0 2px 4px rgba(0,0,0,0.5);">
            {clean_title}
        </h2>
        <p style="font-size: 0.92rem; line-height: 1.5; color: #cbd5e1; margin: 0 0 1.5rem 0;">
            {clean_desc[:140]}...
        </p>
        <div style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
            <style>
                .card-tag {{
                    background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.15);
                    color: #38bdf8; font-size: 0.75rem; font-weight: 600; padding: 0.25rem 0.6rem; border-radius: 6px;
                }}
            </style>
            {tags_html}
        </div>
    </div>
    """

    # 2. LinkedIn Carousel 3-Slide Preview
    linkedin_slide1 = f"""
    <div style="width: 100%; max-width: 580px; margin: 0 auto; background: #090d16; border: 2px solid #38bdf8; border-radius: 16px; padding: 2.2rem; font-family: sans-serif; color: #ffffff; text-align: center;">
        <div style="font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.1em; color: #38bdf8; font-weight: 700; margin-bottom: 1rem;">
            SWIPE LEFT ➔ [Slide 1/3]
        </div>
        <h3 style="font-size: 1.4rem; font-weight: 800; color: #f8fafc; margin-bottom: 1rem; line-height: 1.4;">
            💡 {clean_title}
        </h3>
        <div style="background: rgba(56, 189, 248, 0.1); border-left: 4px solid #38bdf8; padding: 1rem; text-align: left; border-radius: 0 8px 8px 0; color: #e2e8f0; font-size: 0.9rem;">
            "{clean_desc[:120]}..."
        </div>
    </div>
    """

    linkedin_slide2 = f"""
    <div style="width: 100%; max-width: 580px; margin: 0 auto; background: #090d16; border: 2px solid #a855f7; border-radius: 16px; padding: 2.2rem; font-family: sans-serif; color: #ffffff; text-align: left;">
        <div style="font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.1em; color: #a855f7; font-weight: 700; margin-bottom: 1rem;">
            KEY TAKEAWAYS ➔ [Slide 2/3]
        </div>
        <ul style="list-style: none; padding: 0; margin: 0; font-size: 0.92rem; color: #e2e8f0;">
            <li style="margin-bottom: 0.8rem; padding-left: 1.4rem; position: relative;">
                <span style="position: absolute; left: 0; color: #a855f7;">⚡</span> <strong>Automated Pipeline:</strong> Researched & verified via real-time Tavily search.
            </li>
            <li style="margin-bottom: 0.8rem; padding-left: 1.4rem; position: relative;">
                <span style="position: absolute; left: 0; color: #a855f7;">📐</span> <strong>Structural Diagrams:</strong> High-legibility Mermaid architecture diagrams.
            </li>
            <li style="padding-left: 1.4rem; position: relative;">
                <span style="position: absolute; left: 0; color: #a855f7;">🎯</span> <strong>SEO Optimized:</strong> Pre-built slug, social metadata & keyword targeting.
            </li>
        </ul>
    </div>
    """

    # 3. Instagram Quote Card
    # "read full post" was a bare <span>, so it looked like a link but did
    # nothing. Render a real anchor once the post has actually been published
    # somewhere; before that there is no destination, so keep it plain rather
    # than shipping a dead link.
    if post_url:
        read_more = (
            f'<a href="{post_url}" target="_blank" rel="noopener noreferrer" '
            'style="font-size: 0.75rem; color: #fdba74; text-decoration: underline; '
            'font-weight: 600;">read full post ➔</a>'
        )
    else:
        read_more = (
            '<span style="font-size: 0.75rem; color: #fdba74; opacity: .75;">'
            "read full post ➔</span>"
        )

    instagram_card = f"""
    <div style="
        width: 100%; max-width: 500px; margin: 0 auto; aspect-ratio: 1/1;
        background: radial-gradient(circle at 10% 20%, #431407 0%, #180905 50%, #000000 100%);
        border: 2px solid #f97316; border-radius: 20px; padding: 2.5rem; display: flex; flex-direction: column;
        justify-content: space-between; font-family: sans-serif; color: #ffffff; box-shadow: 0 15px 35px rgba(249, 115, 22, 0.3);
    ">
        <div style="font-size: 2.5rem; color: #f97316; font-family: Georgia, serif; line-height: 1;">“</div>
        <div style="font-size: 1.2rem; font-weight: 700; line-height: 1.4; color: #ffedd5; text-align: left;">
            {clean_title}
        </div>
        <div style="border-top: 1px solid rgba(249, 115, 22, 0.3); padding-top: 1rem; display: flex; align-items: center; justify-content: space-between;">
            <span style="font-size: 0.8rem; font-weight: 600; color: #f97316;">AUTONOMOUS AI BLOG AGENT</span>
            {read_more}
        </div>
    </div>
    """

    return {
        "twitter": twitter_card,
        "linkedin_slide1": linkedin_slide1,
        "linkedin_slide2": linkedin_slide2,
        "instagram": instagram_card,
    }
