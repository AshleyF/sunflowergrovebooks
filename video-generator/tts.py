"""
Text-to-Speech module — generates narration audio using OpenAI's TTS API.

Supports two models:
  - tts-1 / tts-1-hd: basic TTS, no tone control
  - gpt-4o-mini-tts: supports 'instructions' parameter for tone, pacing,
    and style control via natural language (e.g., "Read warmly like a grandmother")

The 'instructions' field in the storyboard controls how each scene is read.
"""

import hashlib
import os
from pathlib import Path
from typing import Optional


def get_cache_path(cache_dir: Path, text: str, voice: str, model: str,
                   instructions: str = "") -> Path:
    """Generate a deterministic cache file path from text + settings."""
    content = f"{text}|{voice}|{model}|{instructions}"
    hash_val = hashlib.md5(content.encode()).hexdigest()[:16]
    return cache_dir / f"{hash_val}.mp3"


def generate_speech(
    text: str,
    output_dir: str,
    voice: str = "nova",
    model: str = "gpt-4o-mini-tts",
    instructions: str = "",
    api_key: Optional[str] = None,
) -> Path:
    """Generate speech audio from text using OpenAI's TTS API.

    Args:
        text: The text to speak.
        output_dir: Directory for cached audio files.
        voice: Voice to use (alloy, echo, fable, onyx, nova, shimmer, coral, etc.).
        model: TTS model. Use 'gpt-4o-mini-tts' for tone/style control.
        instructions: Natural language instructions for tone/style/pacing.
                      Only works with gpt-4o-mini-tts model.
                      Example: "Read like a warm, gentle storyteller for children."
        api_key: OpenAI API key (falls back to OPENAI_API_KEY env var).

    Returns:
        Path to the generated MP3 file.
    """
    cache_dir = Path(output_dir) / "audio_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    cache_path = get_cache_path(cache_dir, text, voice, model, instructions)
    if cache_path.exists():
        return cache_path

    api_key = api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "OpenAI API key required. Set OPENAI_API_KEY env var "
            "or pass api_key parameter."
        )

    from openai import OpenAI
    client = OpenAI(api_key=api_key, timeout=60.0)

    kwargs = {
        "model": model,
        "voice": voice,
        "input": text,
    }
    # Only gpt-4o-mini-tts supports the instructions parameter
    if instructions and "4o" in model:
        kwargs["instructions"] = instructions

    response = client.audio.speech.create(**kwargs)
    response.stream_to_file(str(cache_path))
    return cache_path


def get_audio_duration(audio_path: str) -> float:
    """Get duration of an audio file in seconds using ffprobe."""
    import subprocess
    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(audio_path),
        ],
        capture_output=True, text=True,
    )
    return float(result.stdout.strip())


# Available voices for reference
VOICES = {
    "alloy": "Neutral, balanced",
    "echo": "Warm, conversational",
    "fable": "Expressive, British",
    "onyx": "Deep, authoritative",
    "nova": "Friendly, upbeat",
    "shimmer": "Clear, pleasant",
}
