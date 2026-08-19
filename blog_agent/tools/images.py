"""
Image generation tool.

Backends are tried in an order derived from ``IMAGE_PROVIDER``, falling back
to a Pillow-drawn placeholder if they all fail.

Note that as of August 2026 both Gemini and OpenAI image models are paid-only
(every Gemini image model reports ``limit: 0`` on the free tier), which is why
the keyless Pollinations endpoint is the default.
"""

from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

from blog_agent import design
from blog_agent.config import get_settings

logger = logging.getLogger(__name__)

# Order to try backends in, keyed by the configured preference.
#
# Pollinations is deliberately NOT in any automatic chain: its only model
# (sana) cannot render readable labels, so it yields a plausible-looking but
# useless image. A Pillow placeholder is more honest. It is used only when
# selected explicitly.
_FALLBACK_ORDER: dict[str, list[str]] = {
    "cloudflare": ["cloudflare", "openrouter", "openai", "gemini"],
    "openrouter": ["openrouter", "cloudflare", "openai", "gemini"],
    "pollinations": ["pollinations"],
    "openai": ["openai", "openrouter", "cloudflare", "gemini"],
    "gemini": ["gemini", "openrouter", "cloudflare", "openai"],
    "none": [],
}


def _to_png(raw: bytes) -> bytes:
    """Re-encode arbitrary image bytes as PNG.

    Backends return JPEG or WebP, but the pipeline writes ``.png`` filenames,
    so the container has to match what the markdown claims.
    """
    from PIL import Image

    img = Image.open(BytesIO(raw))
    if img.format == "PNG":
        return raw

    buf = BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()


def _parse_size(size: str) -> tuple[int, int]:
    """Turn a '1024x1536' spec into a (width, height) pair."""
    try:
        w, h = size.lower().split("x")
        return int(w), int(h)
    except Exception:
        return 1024, 1024


# Pollinations renders to a fixed pixel budget (768x768) and silently scales
# anything larger, so ask for dimensions that already fit it.
_POLLINATIONS_PIXEL_BUDGET = 768 * 768


def _fit_pixel_budget(
    width: int, height: int, budget: int = _POLLINATIONS_PIXEL_BUDGET
) -> tuple[int, int]:
    """Scale (width, height) down to ``budget`` pixels, preserving aspect.

    Dimensions are rounded to multiples of 8, which diffusion backends prefer.
    """
    area = max(1, width * height)
    if area <= budget:
        return width, height

    scale = (budget / area) ** 0.5

    def snap(v: int) -> int:
        return max(8, int(round(v * scale / 8)) * 8)

    return snap(width), snap(height)


# ---------------------------------------------------------------------------
# Cloudflare Workers AI (free tier)
# ---------------------------------------------------------------------------

def _cloudflare_generate_image_bytes(prompt: str, size: str) -> bytes:
    """Generate an image with FLUX-1-schnell on Cloudflare Workers AI.

    The free allocation is 10,000 neurons/day and a schnell image costs roughly
    50 neurons, so this comfortably covers day-to-day blogging at no cost.
    """

    import base64

    import requests

    settings = get_settings()

    if not (settings.cloudflare_account_id and settings.cloudflare_api_token):
        raise RuntimeError("CLOUDFLARE_ACCOUNT_ID / CLOUDFLARE_API_TOKEN not set")

    model = settings.cloudflare_image_model

    url = (
        f"https://api.cloudflare.com/client/v4/accounts/"
        f"{settings.cloudflare_account_id}/ai/run/{model}"
    )
    auth = {"Authorization": f"Bearer {settings.cloudflare_api_token}"}

    # Neither family accepts width/height — both emit a fixed square — so
    # `size` is taken for interface parity but cannot be honoured here.
    if "flux-2" in model:
        # FLUX.2 rejects a JSON body ("required properties at '/' are
        # 'multipart'") and wants multipart form fields instead.
        resp = requests.post(
            url, headers=auth, files={"prompt": (None, prompt)}, timeout=300
        )
    else:
        # flux-1-schnell takes JSON. It is distilled for very few steps;
        # 8 is its maximum and gives the best text it can manage.
        resp = requests.post(
            url,
            headers={**auth, "Content-Type": "application/json"},
            json={"prompt": prompt, "steps": 8},
            timeout=300,
        )

    if resp.status_code != 200:
        raise RuntimeError(f"Cloudflare HTTP {resp.status_code}: {resp.text[:200]}")

    # Newer models stream raw image bytes; flux-1-schnell returns JSON with a
    # base64 payload. Handle both.
    if resp.headers.get("content-type", "").startswith("image/"):
        return _to_png(resp.content)

    data = resp.json()

    if not data.get("success", True):
        errors = data.get("errors") or data.get("messages")
        raise RuntimeError(f"Cloudflare error: {str(errors)[:200]}")

    result = data.get("result") or {}
    b64 = result.get("image")

    if not b64:
        raise RuntimeError("Cloudflare returned no image data")

    return _to_png(base64.b64decode(b64))


# ---------------------------------------------------------------------------
# OpenRouter
# ---------------------------------------------------------------------------

def _openrouter_generate_image_bytes(prompt: str, size: str) -> bytes:
    """Generate an image through OpenRouter's chat-completions endpoint.

    Image models are driven by asking for the ``image`` output modality; the
    result comes back as a data: URI on ``message.images``.
    """

    import base64
    import re

    import requests

    settings = get_settings()

    if not settings.openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY not set")

    width, height = _parse_size(size)

    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": settings.openrouter_image_model,
            "messages": [{"role": "user", "content": prompt}],
            "modalities": ["image", "text"],
            "image_config": {"aspect_ratio": _aspect_ratio(width, height)},
            # OpenRouter reserves credit up front from max_tokens. Left
            # unset it reserves the model's full window (~59k tokens) and
            # small balances get a 402 before generation even starts. An
            # image costs a few thousand tokens, so cap the reservation.
            "max_tokens": settings.openrouter_max_tokens,
        },
        timeout=300,
    )

    if resp.status_code != 200:
        raise RuntimeError(f"OpenRouter HTTP {resp.status_code}: {resp.text[:200]}")

    data = resp.json()

    if "error" in data:
        raise RuntimeError(f"OpenRouter error: {str(data['error'])[:200]}")

    try:
        images = data["choices"][0]["message"].get("images") or []
    except (KeyError, IndexError) as exc:
        raise RuntimeError(f"Unexpected OpenRouter response shape: {exc}") from exc

    for item in images:
        url = (item.get("image_url") or {}).get("url", "")
        if url.startswith("data:"):
            b64 = re.sub(r"^data:[^,]*,", "", url)
            return _to_png(base64.b64decode(b64))
        if url.startswith("http"):
            got = requests.get(url, timeout=120)
            got.raise_for_status()
            return _to_png(got.content)

    raise RuntimeError("OpenRouter returned no image data")


def _aspect_ratio(width: int, height: int) -> str:
    """Map pixel dimensions onto the nearest aspect ratio string."""
    ratio = width / height if height else 1.0
    options = {"1:1": 1.0, "4:3": 4 / 3, "3:4": 0.75, "16:9": 16 / 9, "9:16": 0.5625}
    return min(options, key=lambda k: abs(options[k] - ratio))


# ---------------------------------------------------------------------------
# Pollinations (free, no API key)
# ---------------------------------------------------------------------------

def _pollinations_generate_image_bytes(prompt: str, size: str) -> bytes:
    """Generate an image via Pollinations and return PNG bytes.

    The endpoint answers with JPEG, so the result is re-encoded to PNG to match
    the ``.png`` filenames used throughout the pipeline.
    """

    import requests
    from PIL import Image

    width, height = _fit_pixel_budget(*_parse_size(size))

    url = (
        f"https://image.pollinations.ai/prompt/{quote(prompt)}"
        f"?width={width}&height={height}&nologo=true&model=flux"
    )

    resp = requests.get(url, timeout=180)
    resp.raise_for_status()

    if not resp.headers.get("content-type", "").startswith("image/"):
        raise RuntimeError(
            f"Pollinations returned {resp.headers.get('content-type')!r}, not an image"
        )

    return _to_png(resp.content)


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

    # NOTE: plain `gemini-2.0-flash` cannot emit images — an image-capable
    # model id is required (configurable via IMAGE_MODEL). Image-capable
    # Gemini models also require TEXT alongside IMAGE in response_modalities.
    response = client.models.generate_content(
        model=settings.image_model,
        contents=[prompt],
        config=types.GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"]
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

def _openai_generate_image_bytes(
    prompt: str,
    size: str = "1024x1024",
    quality: str = "medium",
) -> bytes:

    import base64

    from openai import OpenAI

    settings = get_settings()

    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY not set")

    client = OpenAI(api_key=settings.openai_api_key)

    result = client.images.generate(
        model="gpt-image-1",
        prompt=prompt,
        size=size,          # type: ignore[arg-type]
        quality=quality,    # type: ignore[arg-type]
    )

    if not result.data or not result.data[0].b64_json:
        raise RuntimeError("OpenAI returned no image data")

    return base64.b64decode(result.data[0].b64_json)


# ---------------------------------------------------------------------------
# Placeholder fallback
# ---------------------------------------------------------------------------

def _create_placeholder_image(text: str) -> bytes:

    from PIL import Image, ImageDraw, ImageFont

    # Cabinet palette, so a failed generation still looks intentional.
    img = Image.new("RGB", (1024, 512), color=(18, 18, 31))   # design.CAB_BG
    draw = ImageDraw.Draw(img)

    accent = tuple(
        int(design.get_theme(get_settings().ui_theme)["primary"].lstrip("#")[i:i + 2], 16)
        for i in (0, 2, 4)
    )
    draw.rectangle([0, 0, 1023, 7], fill=accent)
    draw.rectangle([16, 16, 1007, 495], outline=(46, 43, 71), width=2)

    try:
        font = ImageFont.truetype("arial.ttf", 30)
    except Exception:
        font = ImageFont.load_default()

    # Keep the label short enough to fit on one line.
    text = text.strip() or "Image Placeholder"
    if len(text) > 48:
        text = text[:45].rstrip() + "..."

    bbox = draw.textbbox((0, 0), text, font=font)

    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]

    # Centre against the real canvas, not the old 800x400 one.
    width, height = img.size
    draw.text(((width - w) // 2, (height - h) // 2), text,
              fill=(232, 230, 245), font=font)   # design.CAB_TEXT

    buf = BytesIO()
    img.save(buf, format="PNG")

    return buf.getvalue()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def normalize_filename(filename: str) -> str:
    """Return ``filename`` guaranteed to carry a ``.png`` extension.

    Shared with the compiler so the file written to disk and the filename
    referenced in the exported markdown can never drift apart.
    """
    name = (filename or "").strip() or "image"
    return name if name.lower().endswith(".png") else f"{name}.png"


def generate_image(spec: dict, output_dir: Path) -> Path:
    """Generate one image, trying each backend in the configured order.

    Always returns a path — a Pillow placeholder is written if every backend
    fails, so a missing image never breaks the exported markdown.
    """

    settings = get_settings()

    filename = normalize_filename(spec["filename"])

    # Single choke point for house art direction: every backend below receives
    # the prompt from here, so appending the style once keeps the whole set
    # visually consistent and on-palette.
    prompt = f"{spec['prompt']}\n\n{design.image_style_suffix(settings.ui_theme)}"

    size = spec.get("size") or "1024x1024"
    quality = spec.get("quality") or "medium"

    path = output_dir / filename

    if path.exists():
        return path

    backends = {
        "cloudflare": lambda: _cloudflare_generate_image_bytes(prompt, size),
        "openrouter": lambda: _openrouter_generate_image_bytes(prompt, size),
        "pollinations": lambda: _pollinations_generate_image_bytes(prompt, size),
        "openai": lambda: _openai_generate_image_bytes(prompt, size=size, quality=quality),
        "gemini": lambda: _gemini_generate_image_bytes(prompt),
    }

    for name in _FALLBACK_ORDER.get(settings.image_provider, []):
        try:
            path.write_bytes(backends[name]())
            logger.info("Image generated via %s: %s", name, path)
            return path
        except Exception as exc:
            logger.warning("%s image generation failed: %s", name, exc)

    # Placeholder fallback
    path.write_bytes(_create_placeholder_image(spec.get("alt") or "Image Placeholder"))
    logger.info("Placeholder image created: %s", path)

    return path