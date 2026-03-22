"""
PDF extraction module — extracts text and images from a children's book PDF
and groups them into narrated "scenes" for video generation.

Each scene has:
  - text: the narration for this scene (may be empty for image-only pages)
  - image_path: path to the extracted image file

Supports two pairing modes:
  - sequential (default): text accumulates until the next image
  - spread: pages are paired as book spreads [LEFT, RIGHT], where text on
    one side of a spread goes with the image on the other side
"""

import fitz  # PyMuPDF
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Scene:
    """A single scene in the video — one image with optional narration."""
    index: int
    text: str
    image_path: Optional[Path] = None
    source_pages: list[int] = field(default_factory=list)


def _extract_page_image(doc, page, page_num: int, images_dir: Path,
                         seen_xrefs: set) -> Optional[Path]:
    """Extract the largest image from a page, return its path or None."""
    images = page.get_images(full=True)
    if not images:
        return None

    best = None
    best_area = 0
    for img_info in images:
        xref = img_info[0]
        if xref in seen_xrefs:
            continue
        try:
            pix = fitz.Pixmap(doc, xref)
            area = pix.width * pix.height
            if area > best_area and area > 10000:  # skip tiny images
                best_area = area
                best = (xref, pix)
        except Exception:
            continue

    if not best:
        return None

    xref, pix = best
    seen_xrefs.add(xref)
    if pix.n - pix.alpha > 3:
        pix = fitz.Pixmap(fitz.csRGB, pix)
    img_filename = f"page_{page_num + 1:03d}.png"
    img_path = images_dir / img_filename
    pix.save(str(img_path))
    return img_path


def extract_pdf(pdf_path: str, output_dir: str,
                spread_aware: bool = False) -> list[Scene]:
    """Extract images and text from a PDF, grouping into scenes.

    Args:
        pdf_path: Path to the PDF file.
        output_dir: Directory to save extracted images.
        spread_aware: If True, pair text/images within book spreads (R-L-R-L).

    Returns:
        List of Scene objects in reading order.
    """
    if spread_aware:
        return _extract_spread_aware(pdf_path, output_dir)
    else:
        return _extract_sequential(pdf_path, output_dir)


def _extract_spread_aware(pdf_path: str, output_dir: str) -> list[Scene]:
    """Spread-aware extraction: pages alternate R-L-R-L.

    Spreads are [LEFT, RIGHT] pairs that the reader sees side by side.
    Page 1 is RIGHT, so spreads are: [P2,P3], [P4,P5], [P6,P7], ...

    Within a spread:
      - If one page has an image and the other has text → pair them
      - If both pages have their own text+image → two scenes
      - If only text → accumulate for the next spread's image
      - If only images → use accumulated text
    """
    doc = fitz.open(pdf_path)
    out = Path(output_dir)
    images_dir = out / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    scenes: list[Scene] = []
    scene_index = 0
    seen_xrefs = set()
    pending_text = ""
    pending_pages: list[int] = []

    # Page 1 (index 0) is title/RIGHT page — skip it
    # Build spreads: [P2,P3], [P4,P5], ...
    # In 0-indexed: [1,2], [3,4], [5,6], ...
    page_count = len(doc)
    spread_start = 1  # start from page 2 (index 1)

    for si in range(spread_start, page_count, 2):
        left_idx = si
        right_idx = si + 1 if si + 1 < page_count else None

        # Extract content from each page in the spread
        spread_pages = []
        for idx in [left_idx, right_idx]:
            if idx is None:
                continue
            page = doc[idx]
            text = page.get_text().strip()
            img_path = _extract_page_image(doc, page, idx, images_dir, seen_xrefs)
            spread_pages.append({
                'idx': idx,
                'page_num': idx + 1,
                'text': text,
                'image': img_path,
            })

        # Gather all text and images from this spread
        spread_texts = [(p['page_num'], p['text']) for p in spread_pages if p['text']]
        spread_images = [(p['page_num'], p['image']) for p in spread_pages if p['image']]
        all_text = " ".join(t for _, t in spread_texts)
        all_pages = [p['page_num'] for p in spread_pages]

        if not spread_images and not all_text:
            continue  # blank spread

        if not spread_images:
            # Text-only spread — accumulate
            pending_text += (" " + all_text) if pending_text else all_text
            pending_pages.extend(all_pages)
            continue

        # We have image(s) in this spread
        if len(spread_images) == 1:
            # One image — combine all text (spread + pending)
            combined_text = (pending_text + " " + all_text).strip() if pending_text else all_text
            combined_pages = pending_pages + all_pages
            _, img_path = spread_images[0]
            scenes.append(Scene(
                index=scene_index,
                text=combined_text,
                image_path=img_path,
                source_pages=combined_pages,
            ))
            scene_index += 1
            pending_text = ""
            pending_pages = []
        else:
            # Two images — try to pair each with its own text
            # First flush any pending text with the first image
            if pending_text:
                _, img_path = spread_images[0]
                scenes.append(Scene(
                    index=scene_index,
                    text=pending_text.strip(),
                    image_path=img_path,
                    source_pages=pending_pages + [spread_images[0][0]],
                ))
                scene_index += 1
                pending_text = ""
                pending_pages = []
                # Second image gets spread text
                remaining_imgs = spread_images[1:]
            else:
                remaining_imgs = spread_images

            # Pair each remaining image with text from its own page
            for pg_num, img_path in remaining_imgs:
                page_text = ""
                for tpn, t in spread_texts:
                    if tpn == pg_num:
                        page_text = t
                        break
                if not page_text:
                    # Use combined spread text for first unmatched image
                    page_text = all_text
                    all_text = ""  # consumed
                scenes.append(Scene(
                    index=scene_index,
                    text=page_text,
                    image_path=img_path,
                    source_pages=[pg_num],
                ))
                scene_index += 1

    # Handle trailing text
    if pending_text.strip():
        if scenes and scenes[-1].image_path:
            scenes.append(Scene(
                index=scene_index,
                text=pending_text.strip(),
                image_path=scenes[-1].image_path,
                source_pages=pending_pages,
            ))

    doc.close()
    return scenes


def _extract_sequential(pdf_path: str, output_dir: str) -> list[Scene]:
    """Sequential extraction: text accumulates until next image."""
    doc = fitz.open(pdf_path)
    out = Path(output_dir)
    images_dir = out / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    scenes: list[Scene] = []
    pending_text = ""
    pending_pages: list[int] = []
    scene_index = 0
    seen_xrefs = set()

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text().strip()
        if page_num == 0:
            continue
        if not text and not page.get_images(full=True):
            continue

        image_path = _extract_page_image(doc, page, page_num, images_dir, seen_xrefs)

        if image_path:
            if text:
                combined_text = (pending_text + " " + text).strip() if pending_text else text
                combined_pages = pending_pages + [page_num + 1]
            else:
                combined_text = pending_text.strip()
                combined_pages = pending_pages + [page_num + 1]

            scenes.append(Scene(
                index=scene_index,
                text=combined_text,
                image_path=image_path,
                source_pages=combined_pages,
            ))
            scene_index += 1
            pending_text = ""
            pending_pages = []
        else:
            pending_text += (" " + text) if pending_text else text
            pending_pages.append(page_num + 1)

    if pending_text.strip():
        if scenes and scenes[-1].image_path:
            scenes.append(Scene(
                index=scene_index,
                text=pending_text.strip(),
                image_path=scenes[-1].image_path,
                source_pages=pending_pages,
            ))

    doc.close()
    return scenes


def print_scenes(scenes: list[Scene]) -> None:
    """Debug helper — print scene summary."""
    for s in scenes:
        img = s.image_path.name if s.image_path else "(no image)"
        text_preview = (s.text[:80] + "...") if len(s.text) > 80 else s.text
        print(f"  Scene {s.index:2d} | pages {s.source_pages} | {img} | {text_preview or '(no text)'}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python extract_pdf.py <pdf_path> [output_dir] [--spread]")
        sys.exit(1)
    pdf = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("-") else "."
    spread = "--spread" in sys.argv
    scenes = extract_pdf(pdf, out, spread_aware=spread)
    print(f"\nExtracted {len(scenes)} scenes (spread_aware={spread}):")
    print_scenes(scenes)
