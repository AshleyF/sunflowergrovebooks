"""
Sunflower Grove Books — Video Generator

Three-stage pipeline for generating read-aloud videos from children's book PDFs:

  1. PREPARE: PDF → storyboard.json (intermediate form)
     Extracts images, text, detects focal points, generates TTS.
     The storyboard can be manually edited to tweak text, reorder scenes, etc.

  2. RENDER: storyboard.json → video.mp4
     Builds video segments with Ken Burns effects and concatenates.

  3. GENERATE: convenience command that runs prepare + render in one go.

Usage:
    # Two-stage (recommended — allows editing storyboard between steps):
    python generate_video.py prepare "book.pdf" --cover cover.jpg --spread
    # ... edit storyboard.json to taste ...
    python generate_video.py render work_dir/storyboard.json -o video.mp4

    # One-shot:
    python generate_video.py generate "book.pdf" --cover cover.jpg -o video.mp4 --spread
"""

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

from extract_pdf import extract_pdf, print_scenes
from tts import generate_speech, get_audio_duration
from focal_detect import batch_detect_focal_points
from video_builder import (
    build_scene_video,
    build_cover_video,
    concatenate_videos,
)


# ── Storyboard JSON format ──────────────────────────────────────────────
#
# {
#   "title": "Little Pita's Adventure",
#   "voice": "nova",
#   "tts_model": "tts-1-hd",
#   "work_dir": "C:/path/to/work",
#   "cover": {
#     "image": "images/cover.jpg",      # relative to work_dir
#     "duration": 5.0,
#     "effect": "zoom_out"
#   },
#   "scenes": [
#     {
#       "index": 0,
#       "text": "It was a drizzly morning...",
#       "image": "images/page_003.png",  # relative to work_dir
#       "source_pages": [2, 3],
#       "focal_point": [0.5, 0.47],
#       "effect": "auto",                # or zoom_in, zoom_out, pan_down, pan_up
#       "duration": null                  # null = auto from audio length
#     },
#     ...
#   ]
# }


def prepare_storyboard(
    pdf_path: str,
    work_dir: str = None,
    cover_path: str = None,
    voice: str = "nova",
    tts_model: str = "tts-1-hd",
    spread_aware: bool = False,
    cover_duration: float = 7.0,
    video_size: int = 1080,
) -> Path:
    """Stage 1: Extract PDF → storyboard.json.

    Extracts images and text, generates TTS audio, detects focal points,
    and writes storyboard.json. This intermediate form can be manually
    edited before rendering.

    Returns:
        Path to the storyboard.json file.
    """
    pdf = Path(pdf_path)

    if work_dir:
        work = Path(work_dir)
    else:
        work = pdf.parent / f"{pdf.stem}_work"
    work.mkdir(parents=True, exist_ok=True)

    print(f"Book:     {pdf.name}")
    print(f"Voice:    {voice}")
    print(f"Spread:   {spread_aware}")
    print(f"Size:     {video_size}x{video_size}")
    print(f"Work dir: {work}")
    print()

    # --- Extract title/dedication from page 1 ---
    import fitz
    doc = fitz.open(pdf_path)
    page1_text = doc[0].get_text().strip() if len(doc) > 0 else ""
    doc.close()

    # Parse title and dedication from page 1
    title_text = pdf.stem
    dedication_text = ""
    if page1_text:
        lines = [l.strip() for l in page1_text.split("\n") if l.strip()]
        if lines:
            title_text = lines[0]
        for line in lines[1:]:
            if line.lower().startswith("dedicated") or line.lower().startswith("for "):
                dedication_text = line
                break

    cover_narration = title_text
    if dedication_text:
        cover_narration += f". {dedication_text}"
    print(f"Title:    {title_text}")
    if dedication_text:
        print(f"Dedic:    {dedication_text}")
    print()

    # --- Extract PDF ---
    print("=" * 60)
    print("Step 1: Extracting PDF content")
    print("=" * 60)
    scenes = extract_pdf(str(pdf), str(work), spread_aware=spread_aware)
    print(f"Extracted {len(scenes)} scenes:")
    print_scenes(scenes)
    print()

    # --- Generate TTS audio ---
    print("=" * 60)
    print("Step 2: Generating narration audio")
    print("=" * 60)
    for scene in scenes:
        if scene.text:
            print(f"  Scene {scene.index}: TTS ({len(scene.text)} chars)...", end="", flush=True)
            t0 = time.time()
            audio_path = generate_speech(
                text=scene.text,
                output_dir=str(work),
                voice=voice,
                model=tts_model,
            )
            dur = get_audio_duration(str(audio_path))
            print(f" {dur:.1f}s ({time.time() - t0:.1f}s)")
        else:
            print(f"  Scene {scene.index}: (no text)")
    print()

    # --- Detect focal points ---
    print("=" * 60)
    print("Step 3: Detecting focal points")
    print("=" * 60)
    focal_points = batch_detect_focal_points(scenes)
    print()

    # --- Build storyboard JSON ---
    storyboard = {
        "title": title_text,
        "voice": voice,
        "tts_model": tts_model,
        "video_size": video_size,
        "work_dir": str(work.resolve()),
        "cover": None,
        "scenes": [],
    }

    # Cover
    if cover_path:
        cover = Path(cover_path)
        cover_dest = work / "images" / cover.name
        (work / "images").mkdir(parents=True, exist_ok=True)
        if not cover_dest.exists():
            shutil.copy2(str(cover), str(cover_dest))
        storyboard["cover"] = {
            "image": f"images/{cover.name}",
            "text": cover_narration,
            "duration": None,  # auto from audio
            "effect": "zoom_out",
        }

    # Scenes
    for scene in scenes:
        focal = focal_points.get(scene.index, (0.5, 0.4))
        img_rel = f"images/{scene.image_path.name}" if scene.image_path else None

        entry = {
            "index": scene.index,
            "text": scene.text,
            "tts_text": None,  # set this to override TTS pronunciation/pacing
            "image": img_rel,
            "source_pages": scene.source_pages,
            "focal_point": list(focal),
            "effect": "auto",
            "duration": None,  # auto from audio
        }
        storyboard["scenes"].append(entry)

    # Write storyboard
    sb_path = work / "storyboard.json"
    sb_path.write_text(
        json.dumps(storyboard, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Storyboard saved: {sb_path}")
    print(f"  {len(storyboard['scenes'])} scenes")
    print(f"  Edit this file to tweak text, reorder scenes, adjust focal points, etc.")
    print(f"  Then run: python generate_video.py render \"{sb_path}\" -o output.mp4")

    return sb_path


def render_video(
    storyboard_path: str,
    output_path: str,
    keep_work_dir: bool = False,
) -> None:
    """Stage 2: Render storyboard.json → video.mp4.

    Reads the storyboard, generates any needed TTS audio, builds video
    segments with Ken Burns effects, and concatenates into final video.
    """
    sb_path = Path(storyboard_path)
    sb = json.loads(sb_path.read_text(encoding="utf-8"))
    work = Path(sb["work_dir"])
    output = Path(output_path)
    voice = sb.get("voice", "nova")
    tts_model = sb.get("tts_model", "tts-1-hd")
    video_size = sb.get("video_size", 1080)

    # Set video size for this render
    from video_builder import set_video_size
    set_video_size(video_size)

    segments_dir = work / "segments"
    segments_dir.mkdir(exist_ok=True)

    print(f"Storyboard: {sb_path.name}")
    print(f"Title:      {sb.get('title', '(untitled)')}")
    print(f"Scenes:     {len(sb['scenes'])}")
    print(f"Voice:      {voice}")
    print(f"Size:       {video_size}x{video_size}")
    print(f"Output:     {output}")
    print()

    # --- Generate TTS for any scenes with text ---
    print("=" * 60)
    print("Step 1: Generating narration audio")
    print("=" * 60)
    default_instructions = sb.get("tts_instructions", "")
    scene_audio: dict[int, str] = {}
    for scene in sb["scenes"]:
        tts_input = scene.get("tts_text") or scene.get("text")
        if tts_input:
            # Per-scene instructions override default
            instructions = scene.get("tts_instructions") or default_instructions
            audio_path = generate_speech(
                text=tts_input,
                output_dir=str(work),
                voice=voice,
                model=tts_model,
                instructions=instructions,
            )
            dur = get_audio_duration(str(audio_path))
            scene_audio[scene["index"]] = str(audio_path)
            print(f"  Scene {scene['index']}: {dur:.1f}s audio")
        else:
            print(f"  Scene {scene['index']}: (silent)")
    print()

    # --- Build video segments ---
    print("=" * 60)
    print("Step 2: Building video segments")
    print("=" * 60)
    segment_paths = []

    # Cover
    cover = sb.get("cover")
    if cover and cover.get("image"):
        cover_img = work / cover["image"]
        cover_seg = segments_dir / "000_cover.mp4"
        cover_audio = None
        cover_duration = cover.get("duration")

        # Generate TTS for cover narration (title + dedication)
        cover_text = cover.get("tts_text") or cover.get("text")
        if cover_text:
            cover_instructions = cover.get("tts_instructions") or default_instructions
            cover_audio_path = generate_speech(
                text=cover_text,
                output_dir=str(work),
                voice=voice,
                model=tts_model,
                instructions=cover_instructions,
            )
            cover_audio = str(cover_audio_path)
            audio_dur = get_audio_duration(cover_audio)
            if cover_duration is None:
                cover_duration = audio_dur + 3.0  # extra pause after title
            print(f"  Cover: {cover['image']} + narration ({audio_dur:.1f}s)...", flush=True)
        else:
            cover_duration = cover_duration or 5.0
            print(f"  Cover: {cover['image']} ({cover_duration}s)...", flush=True)

        build_cover_video(
            str(cover_img), str(cover_seg),
            duration=cover_duration,
            audio_path=cover_audio,
        )
        segment_paths.append(str(cover_seg))

    # Scenes
    for scene in sb["scenes"]:
        if not scene.get("image"):
            continue

        idx = scene["index"]
        seg_path = segments_dir / f"{idx + 1:03d}_scene.mp4"
        img_path = str(work / scene["image"])
        audio = scene_audio.get(idx)
        focal = tuple(scene.get("focal_point", [0.5, 0.4]))
        effect = scene.get("effect", "auto")
        duration = scene.get("duration")  # None = auto

        print(f"  Scene {idx}: {scene['image']} focal=({focal[0]:.2f},{focal[1]:.2f})", end="", flush=True)
        if audio:
            print(f" + audio", end="")
        print("...", flush=True)

        build_scene_video(
            image_path=img_path,
            audio_path=audio,
            output_path=str(seg_path),
            duration=duration,
            effect=effect,
            focal_point=focal,
        )
        segment_paths.append(str(seg_path))

    print(f"\n  Built {len(segment_paths)} segments")
    print()

    # --- Concatenate ---
    print("=" * 60)
    print("Step 3: Concatenating final video")
    print("=" * 60)
    concatenate_videos(segment_paths, str(output))
    print(f"  Final video: {output}")
    print(f"  File size: {output.stat().st_size / (1024 * 1024):.1f} MB")

    if not keep_work_dir:
        # Only clean segments, keep storyboard and images for re-renders
        shutil.rmtree(segments_dir, ignore_errors=True)

    print("\nDone!")


def generate_book_video(
    pdf_path: str,
    output_path: str,
    cover_path: str = None,
    voice: str = "nova",
    tts_model: str = "tts-1-hd",
    work_dir: str = None,
    cover_duration: float = 7.0,
    keep_work_dir: bool = False,
    spread_aware: bool = False,
    video_size: int = 1080,
) -> None:
    """Convenience: runs prepare + render in one go."""
    sb_path = prepare_storyboard(
        pdf_path=pdf_path,
        work_dir=work_dir,
        cover_path=cover_path,
        voice=voice,
        tts_model=tts_model,
        spread_aware=spread_aware,
        cover_duration=cover_duration,
        video_size=video_size,
    )
    print()
    render_video(
        storyboard_path=str(sb_path),
        output_path=output_path,
        keep_work_dir=keep_work_dir,
    )


def _add_common_args(parser):
    """Add arguments shared by prepare and generate subcommands."""
    parser.add_argument("pdf", type=str, help="Path to the book PDF file")
    parser.add_argument(
        "--cover", "-c", type=str, default=None,
        help="Path to cover art image"
    )
    parser.add_argument(
        "--voice", "-v", type=str, default="nova",
        help="TTS voice: alloy, echo, fable, onyx, nova, shimmer (default: nova)"
    )
    parser.add_argument(
        "--tts-model", type=str, default="tts-1-hd",
        help="TTS model: tts-1 (fast) or tts-1-hd (quality, default)"
    )
    parser.add_argument(
        "--cover-duration", type=float, default=5.0,
        help="Cover art intro duration in seconds (default: 5)"
    )
    parser.add_argument(
        "--work-dir", type=str, default=None,
        help="Working directory for intermediate files"
    )
    parser.add_argument(
        "--spread", action="store_true",
        help="Spread-aware page pairing (R-L-R-L)"
    )
    parser.add_argument(
        "--video-size", type=int, default=1080,
        help="Square video size in pixels (default: 1080 for 1080x1080)"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Generate read-aloud videos from children's book PDFs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # --- prepare ---
    p_prepare = subparsers.add_parser(
        "prepare",
        help="Stage 1: PDF → storyboard.json (editable intermediate form)",
    )
    _add_common_args(p_prepare)

    # --- render ---
    p_render = subparsers.add_parser(
        "render",
        help="Stage 2: storyboard.json → video.mp4",
    )
    p_render.add_argument("storyboard", type=str, help="Path to storyboard.json")
    p_render.add_argument(
        "--output", "-o", type=str, default=None,
        help="Output video path (default: <title>.mp4)"
    )
    p_render.add_argument(
        "--keep-work", action="store_true",
        help="Keep segment files after completion"
    )

    # --- generate (one-shot) ---
    p_gen = subparsers.add_parser(
        "generate",
        help="One-shot: PDF → storyboard → video (prepare + render)",
    )
    _add_common_args(p_gen)
    p_gen.add_argument(
        "--output", "-o", type=str, default=None,
        help="Output video path (default: <pdf_stem>.mp4)"
    )
    p_gen.add_argument(
        "--keep-work", action="store_true",
        help="Keep intermediate files"
    )

    args = parser.parse_args()

    if args.command == "prepare":
        prepare_storyboard(
            pdf_path=args.pdf,
            work_dir=args.work_dir,
            cover_path=args.cover,
            voice=args.voice,
            tts_model=args.tts_model,
            spread_aware=args.spread,
            cover_duration=args.cover_duration,
            video_size=args.video_size,
        )

    elif args.command == "render":
        output = args.output
        if not output:
            sb = json.loads(Path(args.storyboard).read_text(encoding="utf-8"))
            output = str(Path(args.storyboard).parent / f"{sb.get('title', 'output')}.mp4")
        render_video(
            storyboard_path=args.storyboard,
            output_path=output,
            keep_work_dir=args.keep_work,
        )

    elif args.command == "generate":
        output = args.output or str(Path(args.pdf).with_suffix(".mp4"))
        generate_book_video(
            pdf_path=args.pdf,
            output_path=output,
            cover_path=args.cover,
            voice=args.voice,
            tts_model=args.tts_model,
            work_dir=args.work_dir,
            cover_duration=args.cover_duration,
            keep_work_dir=args.keep_work,
            spread_aware=args.spread,
            video_size=args.video_size,
        )

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
