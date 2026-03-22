"""
Video assembly module — builds video segments and final video using ffmpeg.

Each scene becomes a video segment:
  - The image is shown with a Ken Burns effect (smooth zoom/pan with ease in/out)
  - TTS audio plays over the image
  - Segment duration matches the audio length (+ padding)

All segments are produced with identical audio/video specs so concatenation works.
Images maintain aspect ratio — fitted inside the frame with black padding if needed.

The Ken Burns approach:
  Instead of using ffmpeg's zoompan filter (which has jankiness issues at low frame
  rates of movement), we pre-render the Ken Burns as a series of frame-accurate
  crops using ffmpeg's expression-based crop+scale. The key to smoothness is:
  1. High zoom range (25-35%) so movement is clearly visible
  2. Cosine easing for acceleration/deceleration
  3. Working at native resolution to avoid sub-pixel jitter
"""

import random
import subprocess
from pathlib import Path
from typing import Optional


# Default video settings — can be overridden via set_video_size()
VIDEO_SIZE = 1080  # square by default
FPS = 30
COVER_DURATION = 7  # seconds for cover intro (longer for title narration)
PADDING = 3.0  # extra seconds after narration ends — gives breathing room between pages
IMAGE_ONLY_DURATION = 5  # seconds for scenes with no narration

# Audio normalization — all segments must match for concat
AUDIO_RATE = 44100
AUDIO_CHANNELS = 2


def set_video_size(size: int) -> None:
    """Set the output video size (square). Call before building any segments."""
    global VIDEO_SIZE
    VIDEO_SIZE = size


def _get_image_dimensions(image_path: str) -> tuple[int, int]:
    """Get image width and height."""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "stream=width,height",
         "-of", "csv=p=0", str(image_path)],
        capture_output=True, text=True,
    )
    parts = result.stdout.strip().split(",")
    return int(parts[0]), int(parts[1])


def build_scene_video(
    image_path: str,
    audio_path: Optional[str],
    output_path: str,
    duration: Optional[float] = None,
    effect: str = "auto",
    focal_point: tuple[float, float] = (0.5, 0.4),
) -> None:
    """Create a single scene video clip with smooth Ken Burns effect.

    The image is scaled to cover the square frame (preserving aspect ratio),
    then a smooth zoom+pan is applied using cosine easing for buttery motion.
    The zoom range is 25-35% for clearly visible, cinematic movement.

    Args:
        image_path: Path to the scene image.
        audio_path: Path to narration audio (None for silent scenes).
        output_path: Path to save output MP4.
        duration: Override duration (auto from audio if None).
        effect: "auto", "zoom_in", "zoom_out", "pan_down", "pan_up".
        focal_point: (x%, y%) where 0-1, center of interest in the image.
    """
    if duration is None and audio_path:
        from tts import get_audio_duration
        duration = get_audio_duration(audio_path) + PADDING
    elif duration is None:
        duration = IMAGE_ONLY_DURATION

    total_frames = int(duration * FPS)
    w, h = _get_image_dimensions(image_path)
    aspect = w / h
    portrait = h > w

    # Pick effect
    if effect == "auto":
        if portrait:
            effect = random.choice(["pan_down", "pan_up"])
        else:
            effect = random.choice(["zoom_in", "zoom_out"])

    # Strategy: scale image large, pad to square, then zoompan.
    # The zoompan filter stretches its input to match s=WxH, so we must
    # ensure the input is ALREADY square (with black padding) to preserve
    # the original aspect ratio.

    # Scale image to 2.5x output size (gives room for 30%+ zoom range)
    scale_factor = 2.5
    canvas = int(VIDEO_SIZE * scale_factor)
    # Make canvas even
    canvas += canvas % 2

    if aspect >= 1.0:
        # Landscape or square: fit width to canvas, height follows
        scale_w = canvas
        scale_h = int(canvas / aspect)
    else:
        # Portrait: fit height to canvas, width follows
        scale_h = canvas
        scale_w = int(canvas * aspect)

    # Even dimensions
    scale_w += scale_w % 2
    scale_h += scale_h % 2

    D = total_frames
    pi = "3.14159265"
    S = VIDEO_SIZE
    fx, fy = focal_point

    # Zoompan expressions with dramatic, smooth movement
    # Zoom range 1.0 → 1.35 for clearly visible movement
    # Cosine easing for smooth acceleration/deceleration

    if effect == "zoom_in":
        # Start wide (1.0), smoothly zoom to 1.35x centered on focal point
        zp = (
            f"zoompan="
            f"z='1.0+0.35*(1-cos(on/{D}*{pi}))/2':"
            f"x='(iw-iw/zoom)*{fx:.3f}':"
            f"y='(ih-ih/zoom)*{fy:.3f}':"
            f"d={D}:s={S}x{S}:fps={FPS}"
        )
    elif effect == "zoom_out":
        # Start zoomed at 1.35x on focal point, smoothly pull back to 1.0
        zp = (
            f"zoompan="
            f"z='1.35-0.35*(1-cos(on/{D}*{pi}))/2':"
            f"x='(iw-iw/zoom)*{fx:.3f}':"
            f"y='(ih-ih/zoom)*{fy:.3f}':"
            f"d={D}:s={S}x{S}:fps={FPS}"
        )
    elif effect == "pan_down":
        # Slight zoom (1.15x), pan from top toward focal y
        # Start at y=0, end at y=max, with cosine easing
        zp = (
            f"zoompan="
            f"z='1.15':"
            f"x='(iw-iw/zoom)*{fx:.3f}':"
            f"y='(ih-ih/zoom)*(1-cos(on/{D}*{pi}))/2':"
            f"d={D}:s={S}x{S}:fps={FPS}"
        )
    elif effect == "pan_up":
        # Slight zoom (1.15x), pan from bottom toward top
        zp = (
            f"zoompan="
            f"z='1.15':"
            f"x='(iw-iw/zoom)*{fx:.3f}':"
            f"y='(ih-ih/zoom)*(1-(1-cos(on/{D}*{pi}))/2)':"
            f"d={D}:s={S}x{S}:fps={FPS}"
        )
    else:
        # Fallback: zoom in
        zp = (
            f"zoompan="
            f"z='1.0+0.3*(1-cos(on/{D}*{pi}))/2':"
            f"x='(iw-iw/zoom)*{fx:.3f}':"
            f"y='(ih-ih/zoom)*{fy:.3f}':"
            f"d={D}:s={S}x{S}:fps={FPS}"
        )

    # Filter: scale → pad to square canvas → zoompan → output
    # The pad makes the input square so zoompan's s=SxS doesn't distort
    vf = (
        f"scale={scale_w}:{scale_h}:flags=lanczos,"
        f"pad={canvas}:{canvas}:(ow-iw)/2:(oh-ih)/2:black,"
        f"{zp},format=yuv420p"
    )

    # Build ffmpeg command
    cmd = ["ffmpeg", "-y", "-loop", "1", "-i", str(image_path)]

    if audio_path:
        # Pad the audio with silence to fill the full duration (audio + PADDING),
        # so the image stays on screen for a beat after narration ends.
        # The apad filter extends audio with silence, -t cuts everything at duration.
        af = (
            f"aresample={AUDIO_RATE},"
            f"aformat=sample_fmts=fltp:channel_layouts=stereo,"
            f"apad=whole_dur={duration}"
        )
        cmd += ["-i", str(audio_path)]
        cmd += [
            "-vf", vf,
            "-af", af,
            "-t", str(duration),
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k", "-ar", str(AUDIO_RATE), "-ac", str(AUDIO_CHANNELS),
            str(output_path),
        ]
    else:
        cmd += [
            "-f", "lavfi", "-i", f"anullsrc=r={AUDIO_RATE}:cl=stereo",
            "-vf", vf,
            "-t", str(duration),
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k", "-ar", str(AUDIO_RATE), "-ac", str(AUDIO_CHANNELS),
            str(output_path),
        ]

    _run_ffmpeg(cmd)


def build_cover_video(
    cover_image_path: str,
    output_path: str,
    duration: float = COVER_DURATION,
    audio_path: Optional[str] = None,
) -> None:
    """Create a cover art intro — slow zoom out reveal with optional narration."""
    D = int(duration * FPS)
    pi = "3.14159265"
    S = VIDEO_SIZE

    w, h = _get_image_dimensions(cover_image_path)
    aspect = w / h
    scale_factor = 2.5
    if aspect >= 1.0:
        scale_h = int(S * scale_factor)
        scale_w = int(scale_h * aspect)
    else:
        scale_w = int(S * scale_factor)
        scale_h = int(scale_w / aspect)
    scale_w += scale_w % 2
    scale_h += scale_h % 2

    # Cover: NO Ken Burns. Just show the full cover image, static, fitted to frame.
    # Scale to fit inside the square (letterbox/pillarbox if needed).
    if aspect >= 1.0:
        # Landscape: fit width, pad top/bottom
        vf = f"scale={S}:-2:flags=lanczos,pad={S}:{S}:(ow-iw)/2:(oh-ih)/2:black,format=yuv420p"
    else:
        # Portrait: fit height, pad left/right
        vf = f"scale=-2:{S}:flags=lanczos,pad={S}:{S}:(ow-iw)/2:(oh-ih)/2:black,format=yuv420p"

    cmd = ["ffmpeg", "-y", "-loop", "1", "-framerate", str(FPS), "-i", str(cover_image_path)]

    if audio_path:
        af = (
            f"aresample={AUDIO_RATE},"
            f"aformat=sample_fmts=fltp:channel_layouts=stereo,"
            f"apad=whole_dur={duration}"
        )
        cmd += ["-i", str(audio_path)]
        cmd += [
            "-vf", vf,
            "-af", af,
            "-t", str(duration),
            "-r", str(FPS),
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k", "-ar", str(AUDIO_RATE), "-ac", str(AUDIO_CHANNELS),
            str(output_path),
        ]
    else:
        cmd += [
            "-f", "lavfi", "-i", f"anullsrc=r={AUDIO_RATE}:cl=stereo",
            "-vf", vf,
            "-t", str(duration),
            "-r", str(FPS),
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k", "-ar", str(AUDIO_RATE), "-ac", str(AUDIO_CHANNELS),
            str(output_path),
        ]

    _run_ffmpeg(cmd)


def concatenate_videos(segment_paths: list[str], output_path: str) -> None:
    """Concatenate video segments into one final video.

    Uses stream copy for exact duration preservation. All segments must
    have identical codecs, framerate, resolution, and audio format
    (enforced by build_scene_video and build_cover_video).
    """
    concat_file = Path(output_path).parent / "concat_list.txt"
    with open(concat_file, "w") as f:
        for seg in segment_paths:
            safe_path = str(Path(seg).resolve()).replace("\\", "/")
            f.write(f"file '{safe_path}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_file),
        "-c", "copy",
        "-movflags", "+faststart",
        str(output_path),
    ]
    _run_ffmpeg(cmd)
    concat_file.unlink(missing_ok=True)


def _run_ffmpeg(cmd: list[str]) -> None:
    """Run an ffmpeg command, suppressing output unless there's an error."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ffmpeg FAILED: {' '.join(cmd[:6])}...")
        # Show last 1000 chars of stderr for debugging
        print(f"  stderr: {result.stderr[-1000:]}")
        raise RuntimeError(f"ffmpeg failed with exit code {result.returncode}")
