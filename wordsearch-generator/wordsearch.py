"""
Word Search Puzzle Generator
=============================
Generates kid-friendly word search puzzles as SVG files.

Words are placed only in easy directions (left-to-right, top-to-bottom,
diagonal top-left to bottom-right) — never backward or upward.

Usage:
    from wordsearch import generate_wordsearch
    generate_wordsearch(["CAT", "DOG", "FISH"], "puzzle.svg")
"""

import random
import string
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# Kid-friendly directions only: right, down, diagonal-down-right
DIRECTIONS = [
    (0, 1),   # right
    (1, 0),   # down
    (1, 1),   # diagonal down-right
]


@dataclass
class PlacedWord:
    word: str
    row: int
    col: int
    dr: int
    dc: int


class WordSearchGrid:
    """A letter grid with hidden words."""

    def __init__(self, size: int = 10, seed: Optional[int] = None):
        self.size = size
        self.grid: list[list[Optional[str]]] = [
            [None] * size for _ in range(size)
        ]
        self.placed: list[PlacedWord] = []
        if seed is not None:
            random.seed(seed)

    def _can_place(self, word: str, row: int, col: int, dr: int, dc: int) -> bool:
        """Check if word fits at position in the given direction."""
        for i, ch in enumerate(word):
            r = row + dr * i
            c = col + dc * i
            if r < 0 or r >= self.size or c < 0 or c >= self.size:
                return False
            existing = self.grid[r][c]
            if existing is not None and existing != ch:
                return False
        return True

    def _place(self, word: str, row: int, col: int, dr: int, dc: int):
        """Place a word on the grid."""
        for i, ch in enumerate(word):
            self.grid[row + dr * i][col + dc * i] = ch
        self.placed.append(PlacedWord(word, row, col, dr, dc))

    def build(self, words: list[str], max_attempts: int = 100) -> bool:
        """
        Place all words on the grid. Returns True if all words fit.
        Tries longest words first for better packing.
        """
        sorted_words = sorted(words, key=len, reverse=True)

        for word in sorted_words:
            word = word.upper()
            placed = False

            for _ in range(max_attempts):
                dr, dc = random.choice(DIRECTIONS)
                # Pick a random starting position that could fit
                max_r = self.size - (len(word) - 1) * max(dr, 0) if dr >= 0 else self.size
                max_c = self.size - (len(word) - 1) * max(dc, 0) if dc >= 0 else self.size
                if max_r <= 0 or max_c <= 0:
                    continue
                row = random.randint(0, max_r - 1)
                col = random.randint(0, max_c - 1)

                if self._can_place(word, row, col, dr, dc):
                    self._place(word, row, col, dr, dc)
                    placed = True
                    break

            if not placed:
                return False

        self._fill_blanks()
        return True

    def _fill_blanks(self):
        """Fill remaining empty cells with random letters."""
        for r in range(self.size):
            for c in range(self.size):
                if self.grid[r][c] is None:
                    self.grid[r][c] = random.choice(string.ascii_uppercase)

    def word_cells(self, pw: PlacedWord) -> list[tuple[int, int]]:
        """Return the list of (row, col) cells occupied by a placed word."""
        return [(pw.row + pw.dr * i, pw.col + pw.dc * i) for i in range(len(pw.word))]


class WordSearchPuzzle:
    """
    High-level word search generator.

    Parameters
    ----------
    words : list of str
        Words to hide in the grid.
    size : int
        Grid size (default 10x10).
    seed : int, optional
        Random seed for reproducibility.
    """

    CELL_SIZE = 36
    MARGIN = 24
    FONT_FAMILY = "Comic Sans MS, Comic Neue, cursive, sans-serif"
    LETTER_COLOR = "#000000"
    HEADER_COLOR = "#000000"
    WORD_LIST_COLOR = "#000000"
    HIGHLIGHT_COLOR = "#000000"

    def __init__(self, words: list[str], size: int = 10, seed: Optional[int] = None):
        self.words = [w.upper() for w in words]
        self.size = size
        self.grid = WordSearchGrid(size=size, seed=seed)
        self._generated = False

    def generate(self) -> bool:
        """Build the puzzle. Returns True if all words were placed."""
        ok = self.grid.build(self.words)
        self._generated = True
        if not ok:
            placed = {pw.word for pw in self.grid.placed}
            missing = [w for w in self.words if w not in placed]
            print(f"Warning: Could not place {len(missing)} word(s): {missing}")
        return ok

    def _build_svg(self, show_answers: bool = False) -> ET.Element:
        """Build SVG element — grid of letters + word list below."""
        if not self._generated:
            raise RuntimeError("Call generate() before rendering SVG.")

        cs = self.CELL_SIZE
        pad = self.MARGIN
        grid_w = self.size * cs
        grid_h = self.size * cs

        # Word list below grid
        word_line_h = 20
        words_top = pad + grid_h + 20
        # Arrange words in 2 columns
        col_count = 2
        words_per_col = (len(self.grid.placed) + col_count - 1) // col_count
        word_section_h = words_per_col * word_line_h + 10

        total_w = grid_w + 2 * pad
        total_h = int(words_top + word_section_h + pad)

        svg = ET.Element("svg", {
            "xmlns": "http://www.w3.org/2000/svg",
            "width": str(total_w),
            "height": str(total_h),
            "viewBox": f"0 0 {total_w} {total_h}",
        })
        ET.SubElement(svg, "rect", {"width": "100%", "height": "100%", "fill": "#FFFFFF"})

        grid_x0 = pad
        grid_y0 = pad

        # Draw grid lines
        for i in range(self.size + 1):
            # Horizontal
            ET.SubElement(svg, "line", {
                "x1": str(grid_x0),
                "y1": str(grid_y0 + i * cs),
                "x2": str(grid_x0 + grid_w),
                "y2": str(grid_y0 + i * cs),
                "stroke": "#CCCCCC",
                "stroke-width": "0.5",
            })
            # Vertical
            ET.SubElement(svg, "line", {
                "x1": str(grid_x0 + i * cs),
                "y1": str(grid_y0),
                "x2": str(grid_x0 + i * cs),
                "y2": str(grid_y0 + grid_h),
                "stroke": "#CCCCCC",
                "stroke-width": "0.5",
            })

        # Highlight answer words with a capsule/lozenge shape
        if show_answers:
            import math
            for pw in self.grid.placed:
                cells = self.grid.word_cells(pw)
                r0, c0 = cells[0]
                r1, c1 = cells[-1]
                # Center coords of first and last cell
                x1 = grid_x0 + c0 * cs + cs / 2
                y1 = grid_y0 + r0 * cs + cs / 2
                x2 = grid_x0 + c1 * cs + cs / 2
                y2 = grid_y0 + r1 * cs + cs / 2
                # Capsule dimensions
                dx, dy = x2 - x1, y2 - y1
                length = math.sqrt(dx * dx + dy * dy)
                angle = math.degrees(math.atan2(dy, dx))
                cap_w = length + cs * 0.75
                cap_h = cs * 0.7
                cx = (x1 + x2) / 2
                cy = (y1 + y2) / 2
                ET.SubElement(svg, "rect", {
                    "x": str(cx - cap_w / 2),
                    "y": str(cy - cap_h / 2),
                    "width": str(cap_w),
                    "height": str(cap_h),
                    "rx": str(cap_h / 2),
                    "ry": str(cap_h / 2),
                    "fill": "none",
                    "stroke": self.HIGHLIGHT_COLOR,
                    "stroke-width": "3",
                    "transform": f"rotate({angle:.1f} {cx:.1f} {cy:.1f})",
                })

        # Draw letters
        for r in range(self.size):
            for c in range(self.size):
                letter = self.grid.grid[r][c]
                el = ET.SubElement(svg, "text", {
                    "x": str(int(grid_x0 + c * cs + cs / 2)),
                    "y": str(int(grid_y0 + r * cs + cs / 2 + 6)),
                    "text-anchor": "middle",
                    "font-family": self.FONT_FAMILY,
                    "font-size": "18",
                    "font-weight": "bold",
                    "fill": self.LETTER_COLOR,
                })
                el.text = letter

        # Word list header
        header = ET.SubElement(svg, "text", {
            "x": str(pad),
            "y": str(int(words_top)),
            "font-family": self.FONT_FAMILY,
            "font-size": "16",
            "font-weight": "bold",
            "fill": self.HEADER_COLOR,
        })
        header.text = "Find these words:"

        # Word list in 2 columns
        col_width = grid_w // col_count
        sorted_words = sorted(self.grid.placed, key=lambda pw: pw.word)
        for i, pw in enumerate(sorted_words):
            col = i // words_per_col
            row_idx = i % words_per_col
            x = pad + 10 + col * col_width
            y = words_top + 22 + row_idx * word_line_h

            wt = ET.SubElement(svg, "text", {
                "x": str(int(x)),
                "y": str(int(y)),
                "font-family": self.FONT_FAMILY,
                "font-size": "13",
                "fill": self.WORD_LIST_COLOR,
            })
            wt.text = pw.word

        return svg

    def to_svg(self, filename: str, show_answers: bool = False):
        """Write puzzle to SVG file."""
        svg = self._build_svg(show_answers=show_answers)
        tree = ET.ElementTree(svg)
        ET.indent(tree, space="  ")
        with open(filename, "wb") as f:
            tree.write(f, encoding="utf-8", xml_declaration=True)
        print(f"Saved: {filename}")

    def to_svg_string(self, show_answers: bool = False) -> str:
        """Return SVG as string."""
        svg = self._build_svg(show_answers=show_answers)
        ET.indent(svg, space="  ")
        return ET.tostring(svg, encoding="unicode", xml_declaration=True)

    def print_grid(self):
        """Print ASCII grid to console."""
        if not self._generated:
            raise RuntimeError("Call generate() before printing.")
        for r in range(self.size):
            print(" ".join(self.grid.grid[r][c] for c in range(self.size)))
        print()
        print("Words:", ", ".join(pw.word for pw in self.grid.placed))


def generate_wordsearch(
    words: list[str],
    output_file: str = "wordsearch.svg",
    answer_key_file: Optional[str] = None,
    size: int = 10,
    seed: Optional[int] = None,
) -> WordSearchPuzzle:
    """Convenience function: generate a word search and save to SVG."""
    puzzle = WordSearchPuzzle(words, size=size, seed=seed)
    puzzle.generate()
    puzzle.to_svg(output_file, show_answers=False)
    if answer_key_file:
        puzzle.to_svg(answer_key_file, show_answers=True)
    return puzzle


if __name__ == "__main__":
    demo_words = ["CAT", "DOG", "FISH", "BIRD", "FROG", "BEAR", "DUCK", "LION"]
    puzzle = generate_wordsearch(
        demo_words,
        output_file="demo_wordsearch.svg",
        answer_key_file="demo_wordsearch_key.svg",
        seed=42,
    )
    puzzle.print_grid()
