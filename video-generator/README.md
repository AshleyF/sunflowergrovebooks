# Sunflower Grove Books — Video Generator

Generates YouTube-ready read-aloud videos from children's book PDFs. Each page's illustration is shown with a gentle Ken Burns effect (slow zoom/pan) while TTS narration reads the story aloud.

## Quick Start

```bash
cd video-generator
pip install -r requirements.txt

# Two-stage workflow (recommended — lets you edit the storyboard):
python generate_video.py prepare "book.pdf" --cover "cover.jpg" --spread
# ... edit work_dir/storyboard.json to tweak text, scenes, focal points ...
python generate_video.py render work_dir/storyboard.json -o "video.mp4"

# One-shot (convenience):
python generate_video.py generate "book.pdf" --cover "cover.jpg" -o "video.mp4" --spread
```

## Architecture

The pipeline has three stages with an editable intermediate form:

```
                    ┌──────────────────────┐
  PDF + Cover ──→   │  PREPARE             │ ──→  storyboard.json
                    │  extract_pdf.py      │      (editable intermediate form)
                    │  tts.py              │
                    │  focal_detect.py     │
                    └──────────────────────┘
                              │
                    ┌─── edit storyboard.json ───┐
                    │  - change narration text    │
                    │  - reorder/remove scenes    │
                    │  - adjust focal points      │
                    │  - pick Ken Burns effects    │
                    │  - add title screens         │
                    │  - change voice              │
                    └─────────────────────────────┘
                              │
                    ┌──────────────────────┐
  storyboard.json ──→ │  RENDER              │ ──→  video.mp4
                    │  video_builder.py    │
                    │  tts.py (if changed) │
                    └──────────────────────┘
```

### Why an intermediate form?

The storyboard.json decouples PDF extraction from video rendering. This lets you:
- **Iterate on the video** without re-processing the PDF or re-running focal detection
- **Tweak narration text** — fix pronunciation, reword sentences, add/remove text
- **Reassign images** — swap which image goes with which text
- **Adjust focal points** — if the AI picked a bad center of interest, adjust the x/y
- **Choose Ken Burns effects** — override "auto" with specific zoom_in, zoom_out, pan_down, pan_up
- **Set explicit durations** — override the auto-from-audio timing
- **Add scenes** that aren't in the PDF — title cards, credits, etc.

### Storyboard JSON Format

```json
{
  "title": "Little Pita's Adventure",
  "voice": "nova",
  "tts_model": "tts-1-hd",
  "work_dir": "C:/path/to/work",
  "cover": {
    "image": "images/cover.jpg",
    "duration": 5.0,
    "effect": "zoom_out"
  },
  "scenes": [
    {
      "index": 0,
      "text": "It was a drizzly morning...",
      "image": "images/page_003.png",
      "source_pages": [2, 3],
      "focal_point": [0.5, 0.47],
      "effect": "auto",
      "duration": null
    }
  ]
}
```

| Field | Description |
|-------|-------------|
| `text` | Original narration text from the PDF. This is the "source of truth." |
| `tts_text` | **TTS override** — if set, this is what gets sent to the TTS engine instead of `text`. Use for pronunciation fixes, pause markup, and tone directions. Set to `null` to use `text` as-is. |
| `image` | Path to image file (relative to work_dir). Swap to use a different image. |
| `focal_point` | `[x, y]` as 0.0–1.0 from top-left. Where the camera centers attention. |
| `effect` | `"auto"`, `"zoom_in"`, `"zoom_out"`, `"pan_down"`, `"pan_up"`. Auto picks based on image aspect ratio. |
| `duration` | `null` = auto from audio length + padding. Set a number (seconds) to override. |
| `source_pages` | Informational — which PDF pages this scene came from. |

### TTS Text Markup

The `tts_text` field lets you control exactly how the narration sounds without changing the original `text`. OpenAI's TTS doesn't support SSML, but responds well to these plain-text techniques:

| Technique | Example | Effect |
|-----------|---------|--------|
| Phonetic spelling | `"Pee-tah"` instead of `"Pita"` | Forces correct pronunciation |
| Ellipsis pause | `"...end of page. ..."` | Adds a natural pause between scenes |
| Em-dash pause | `"She looked — and gasped"` | Brief dramatic pause |
| Tone directions | `"(cheerfully) I can't wait!"` | Adjusts vocal tone/emotion |
| Word emphasis | `"It was a HUGE fish!"` | Stresses the capitalized word |

**Example:** For a character named "Pita" (pronounced like pita bread):
```json
{
  "text": "Little Pita ran to the door.",
  "tts_text": "Little Pee-tah ran to the door. ..."
}
```

```
video-generator/
├── generate_video.py    # Main CLI (prepare / render / generate)
├── extract_pdf.py       # PDF → scenes (text + images)
├── tts.py               # OpenAI TTS audio generation
├── focal_detect.py      # GPT-4o-mini focal point detection
├── video_builder.py     # ffmpeg video assembly (Ken Burns + concat)
├── requirements.txt     # Python dependencies
└── README.md            # This file
```

### Pipeline

```
PDF ──→ extract_pdf.py ──→ Scenes (text + image pairs)
                                │
                                ├──→ tts.py ──→ Audio clips (MP3, cached)
                                │
                                └──→ video_builder.py
                                        │
                                        ├── Cover art intro (zoom out, 5s, silent)
                                        ├── Scene segments (Ken Burns + audio)
                                        └── Concatenate ──→ Final MP4
```

### Module Details

#### `extract_pdf.py`
- Uses **PyMuPDF** (fitz) to extract text and images from the PDF.
- Groups consecutive pages into **scenes** — each scene has one image and optional narration text.
- Logic: text-only pages accumulate until the next image page, then pair together. Pages with both text and image form their own scene. Image-only pages become brief (4s) silent scenes.
- Extracts the largest image per page (skips tiny decorative elements).
- Outputs `Scene` objects with: `index`, `text`, `image_path`, `source_pages`.

#### `tts.py`
- Adapted from [VimFu's TTS module](https://github.com/AshleyF/vimfu/blob/main/shellpilot/tts.py).
- Uses **OpenAI's TTS API** (`tts-1-hd` model by default for quality).
- **Caches** generated audio by content hash — re-running won't re-generate existing clips.
- Available voices: `alloy`, `echo`, `fable`, `onyx`, `nova` (default), `shimmer`.
- Returns path to MP3 file. Uses `ffprobe` to get audio duration.

#### `video_builder.py`
- Uses **ffmpeg** to create video segments and concatenate them.
- **Ken Burns effects**: randomly applies effects per scene with **smooth cosine easing** (no jerkiness):
  - `zoom_in` — smooth zoom from 1.0x to 1.2x, centered
  - `zoom_out` — smooth zoom from 1.2x to 1.0x, centered
  - `pan_down` — for portrait images: start at top, smooth pan down
  - `pan_up` — for portrait images: start at bottom, smooth pan up
  - `drift_left` / `drift_right` — slight zoom + horizontal drift
  - Auto-selects: portrait images get vertical pans, landscape images get zooms
- **Aspect ratio preservation**: images are scaled to **cover** the 16:9 frame (with 1.3x margin for movement) using Lanczos resampling. No stretching or distortion.
- **Audio normalization**: all segments are encoded with identical audio specs (44100Hz stereo AAC) so concatenation works correctly.
- Each segment duration = audio length + 1s padding (or 4s for silent scenes).
- Cover art gets a special zoom-out reveal (1.2x → 1.0x).
- Concatenation uses ffmpeg's `concat` demuxer for fast lossless joining.
- Output: 1920×1080 @ 30fps, H.264 video, AAC audio @ 192kbps.

#### `generate_video.py`
- Main CLI orchestrator that runs the full pipeline.
- Steps: Extract PDF → Generate TTS → Build segments → Concatenate.
- Creates a work directory for intermediate files (auto-cleaned unless `--keep-work`).

## CLI Reference

```
python generate_video.py <command> [options]

Commands:
  prepare    PDF → storyboard.json (editable intermediate form)
  render     storyboard.json → video.mp4
  generate   One-shot: PDF → storyboard → video

prepare <pdf_path>:
  --cover, -c PATH       Cover art image
  --voice, -v NAME       TTS voice (default: nova)
  --tts-model MODEL      tts-1 or tts-1-hd (default)
  --cover-duration SECS  Cover intro duration (default: 5)
  --work-dir PATH        Working directory
  --spread               Spread-aware R-L-R-L page pairing

render <storyboard.json>:
  --output, -o PATH      Output video path
  --keep-work            Keep segment files

generate <pdf_path>:
  (all prepare options + all render options)
```

## Examples

```bash
# Two-stage workflow:
python generate_video.py prepare "Little Pita's Adventure.pdf" \
  --cover "cover.jpg" --spread --work-dir ./pita_work

# Edit storyboard.json to taste, then render:
python generate_video.py render ./pita_work/storyboard.json -o "pita_video.mp4"

# One-shot with different voice:
python generate_video.py generate book.pdf --voice shimmer -o book_video.mp4

# Fast generation (lower quality audio):
python generate_video.py generate book.pdf --tts-model tts-1 -o fast_video.mp4
```

## Prerequisites

- **Python 3.10+**
- **ffmpeg** (must be on PATH) — used for video encoding and concatenation
- **OpenAI API key** — set as `OPENAI_API_KEY` environment variable
- Python packages: `PyMuPDF`, `openai`, `python-dotenv`

### Environment Setup (Windows)

```powershell
pip install -r requirements.txt

# Set OpenAI API key (persistent, user-level)
[Environment]::SetEnvironmentVariable('OPENAI_API_KEY', 'sk-...your-key...', 'User')
# Restart terminal after setting
```

## How It Works (for future LLM agents)

If you're an LLM coding agent asked to generate a book video, here's what to do:

1. **Prepare the storyboard** from the PDF:
   ```bash
   cd C:\source\sunflowergrovebooks\video-generator
   python generate_video.py prepare "<pdf_path>" --cover "<cover_path>" --spread
   ```
   This creates `storyboard.json` in the work directory.

2. **Review/edit storyboard.json** if the user wants changes:
   - Fix text that doesn't match the right image
   - Adjust `focal_point` coordinates if cropping is off
   - Change `effect` from `"auto"` to specific Ken Burns effects
   - Set `duration` to override auto-timing
   - Reorder or remove scenes
   - Change the `voice` field to use a different TTS voice

3. **Render the video**:
   ```bash
   python generate_video.py render work_dir/storyboard.json -o "<output.mp4>"
   ```

4. If the user wants changes, **edit storyboard.json and re-render** — no need to
   re-extract the PDF or re-run focal detection. TTS audio is cached by text content,
   so only changed text generates new audio.

### Key files
- `storyboard.json` — the editable intermediate form (this is what you iterate on)
- `images/` — extracted page images from the PDF
- `audio_cache/` — cached TTS audio (keyed by text hash)

## Cost Estimate

- **TTS**: ~$0.015 per 1000 characters (tts-1-hd). A typical 50-page children's book has ~3000-5000 characters of text → ~$0.05-0.08.
- **Total time**: ~5-10 minutes for a 50-page book (most time is TTS generation + ffmpeg encoding).
