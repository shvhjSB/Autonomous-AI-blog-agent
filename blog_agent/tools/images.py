"""
Image generation tool.

Generation priority:
1. Gemini image generation
2. OpenAI image generation
3. Pillow placeholder fallback
"""

from __future__ import annotations

import logging
from pathlib import Path
from io import BytesIO

from blog_agent.config import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Gemini image generation
# ---------------------------------------------------------------------------

def _gemini_generate_image_bytes(prompt: str) -> bytes:
    from google import genai
    from google.genai import types

    settings = get_settings()

    if not settings.google_api_key:
        raise RuntimeError("GOOGLE_API_KEY not set")

    client = genai.Client(api_key=settings.google_api_key)

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[prompt],
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"]
        ),
    )

    parts = None

    if getattr(response, "candidates", None):
        try:
            parts = response.candidates[0].content.parts
        except Exception:
            pass

    if not parts:
        raise RuntimeError("Gemini returned no image")

    for part in parts:
        inline = getattr(part, "inline_data", None)
        if inline and getattr(inline, "data", None):
            return inline.data

    raise RuntimeError("No image bytes found in Gemini response")


# ---------------------------------------------------------------------------
# OpenAI image generation
# ---------------------------------------------------------------------------

def _openai_generate_image_bytes(prompt: str) -> bytes:

    from openai import OpenAI

    settings = get_settings()

    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY not set")

    client = OpenAI(api_key=settings.openai_api_key)

    result = client.images.generate(
        model="gpt-image-1",
        prompt=prompt,
        size="1024x1024",
    )

    image_base64 = result.data[0].b64_json

    import base64
    return base64.b64decode(image_base64)


# ---------------------------------------------------------------------------
# Placeholder fallback
# ---------------------------------------------------------------------------

def _create_placeholder_image(text: str) -> bytes:

    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (800, 400), color=(40, 40, 55))
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("arial.ttf", 24)
    except:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)

    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]

    x = (800 - w) // 2
    y = (400 - h) // 2

    draw.text((x, y), text, fill=(220, 220, 220), font=font)

    buf = BytesIO()
    img.save(buf, format="PNG")

    return buf.getvalue()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_image(spec: dict, output_dir: Path) -> Path:

    filename = spec["filename"]
    prompt = spec["prompt"]

    path = output_dir / filename

    if path.exists():
        return path

    # Try OpenAI first
    try:
        img = _openai_generate_image_bytes(prompt)

        path.write_bytes(img)

        logger.info("Image generated via OpenAI: %s", path)

        return path

    except Exception as e:
        logger.warning("OpenAI image generation failed: %s", e)

    # Try Gemini as fallback
    try:
        img = _gemini_generate_image_bytes(prompt)

        path.write_bytes(img)

        logger.info("Image generated via Gemini: %s", path)

        return path

    except Exception as e:
        logger.warning("Gemini image generation failed: %s", e)

    # Placeholder fallback
    img = _create_placeholder_image("Image Placeholder")

    path.write_bytes(img)

    logger.info("Placeholder image created: %s", path)

    return path