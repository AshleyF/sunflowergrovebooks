"""
Smart focal point detection — uses GPT-4o vision to find the interesting
subject in each image and return crop coordinates for Ken Burns framing.

Given an image and optional context text, returns the (x%, y%) focal point
where the camera should center its attention (e.g., a character's face,
a key object mentioned in the text).
"""

import base64
import json
import os
from pathlib import Path
from typing import Optional


def detect_focal_point(
    image_path: str,
    context_text: str = "",
    api_key: Optional[str] = None,
) -> tuple[float, float]:
    """Use GPT-4o vision to find the focal point of an image.

    Args:
        image_path: Path to the image file.
        context_text: Optional story text that goes with this image.
        api_key: OpenAI API key (falls back to OPENAI_API_KEY env var).

    Returns:
        (x_pct, y_pct) — focal point as percentages (0.0–1.0) from top-left.
        For example (0.5, 0.3) means center horizontally, 30% from top.
    """
    api_key = api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return (0.5, 0.4)  # default: center, slightly above middle

    # Read and encode image
    img_data = Path(image_path).read_bytes()
    b64 = base64.b64encode(img_data).decode("utf-8")

    # Determine mime type
    ext = Path(image_path).suffix.lower()
    mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
            "webp": "image/webp"}.get(ext.lstrip("."), "image/png")

    context_hint = ""
    if context_text:
        context_hint = f'\nThe story text for this image is: "{context_text[:200]}"'

    prompt = f"""Look at this children's book illustration. Find the most important visual subject — typically a character's face, or the main object the story is about.{context_hint}

Return ONLY a JSON object with the focal point as x and y percentages (0.0 to 1.0) from the top-left corner. For example, if the main character's face is in the center-left at 30% from the top, return {{"x": 0.35, "y": 0.3}}.

Return ONLY the JSON, nothing else."""

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, timeout=30.0)

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {
                        "url": f"data:{mime};base64,{b64}",
                        "detail": "low",
                    }},
                ],
            }],
            max_tokens=100,
        )

        text = response.choices[0].message.content.strip()
        # Parse JSON from response (handle markdown code blocks)
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        data = json.loads(text)
        x = max(0.1, min(0.9, float(data.get("x", 0.5))))
        y = max(0.1, min(0.9, float(data.get("y", 0.4))))
        return (x, y)

    except Exception as e:
        print(f"    [focal] Error detecting focal point: {e}")
        return (0.5, 0.4)  # fallback to center-ish


def batch_detect_focal_points(
    scenes: list,
    api_key: Optional[str] = None,
) -> dict[int, tuple[float, float]]:
    """Detect focal points for all scenes with images.

    Args:
        scenes: List of Scene objects from extract_pdf.
        api_key: OpenAI API key.

    Returns:
        Dict mapping scene index → (x_pct, y_pct) focal point.
    """
    results = {}
    for scene in scenes:
        if not scene.image_path:
            continue
        print(f"    [focal] Scene {scene.index}: {scene.image_path.name}...", end="", flush=True)
        x, y = detect_focal_point(
            str(scene.image_path),
            context_text=scene.text,
            api_key=api_key,
        )
        results[scene.index] = (x, y)
        print(f" ({x:.2f}, {y:.2f})")
    return results
