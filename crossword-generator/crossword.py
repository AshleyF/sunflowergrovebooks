"""
Crossword Puzzle Generator
===========================
Generates kid-friendly crossword puzzles as SVG files.

Usage:
    from crossword import CrosswordPuzzle

    words_and_clues = [
        ("TIGER", "A big striped cat"),
        ("ELEPHANT", "The largest land animal"),
        ...
    ]
    puzzle = CrosswordPuzzle(words_and_clues)
    puzzle.generate()
    puzzle.to_svg("puzzle.svg")
"""

import random
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PlacedWord:
    word: str
    clue: str
    row: int
    col: int
    direction: str  # "across" or "down"
    number: Optional[int] = None


class CrosswordGrid:
    """Builds a crossword layout by placing words on a grid with intersections."""

    def __init__(self):
        self.placed: list[PlacedWord] = []
        self.cells: dict[tuple[int, int], str] = {}

    def _can_place(self, word: str, row: int, col: int, direction: str) -> bool:
        """Check if a word can be placed at the given position without conflicts."""
        dr, dc = (0, 1) if direction == "across" else (1, 0)
        length = len(word)

        # Check the cell before the word (must be empty)
        br, bc = row - dr, col - dc
        if (br, bc) in self.cells:
            return False

        # Check the cell after the word (must be empty)
        ar, ac = row + dr * length, col + dc * length
        if (ar, ac) in self.cells:
            return False

        for i, ch in enumerate(word):
            r, c = row + dr * i, col + dc * i
            existing = self.cells.get((r, c))

            if existing is not None:
                # Cell occupied — must match the letter
                if existing != ch:
                    return False
            else:
                # Cell empty — check parallel neighbors don't create unintended adjacency
                if direction == "across":
                    # Check above and below
                    if (r - 1, c) in self.cells or (r + 1, c) in self.cells:
                        return False
                else:
                    # Check left and right
                    if (r, c - 1) in self.cells or (r, c + 1) in self.cells:
                        return False

        return True

    def _place(self, word: str, clue: str, row: int, col: int, direction: str):
        """Place a word on the grid."""
        dr, dc = (0, 1) if direction == "across" else (1, 0)
        for i, ch in enumerate(word):
            self.cells[(row + dr * i, col + dc * i)] = ch
        self.placed.append(PlacedWord(word, clue, row, col, direction))

    def _find_intersections(self, word: str):
        """Find all valid placements for a word that intersect existing words."""
        candidates = []
        for pw in self.placed:
            for i, ch1 in enumerate(word):
                for j, ch2 in enumerate(pw.word):
                    if ch1 != ch2:
                        continue
                    # Try placing perpendicular to the existing word
                    if pw.direction == "across":
                        # Place new word going down, intersecting at pw's j-th letter
                        new_dir = "down"
                        new_row = pw.row - i
                        new_col = pw.col + j
                    else:
                        # Place new word going across, intersecting at pw's j-th letter
                        new_dir = "across"
                        new_row = pw.row + j
                        new_col = pw.col - i

                    if self._can_place(word, new_row, new_col, new_dir):
                        candidates.append((new_row, new_col, new_dir))
        return candidates

    def build(self, words_and_clues: list[tuple[str, str]], max_attempts: int = 50) -> bool:
        """
        Attempt to place all words on the grid.
        Returns True if all words were placed successfully.

        Tries multiple random orderings to find a layout that fits all words.
        """
        best_placed = []
        best_cells = {}

        for attempt in range(max_attempts):
            self.placed = []
            self.cells = {}

            # Shuffle but keep longest word first for the initial seed
            items = list(words_and_clues)
            first = max(items, key=lambda x: len(x[0]))
            items.remove(first)
            random.shuffle(items)
            items.insert(0, first)

            # Place first word horizontally at origin
            word0, clue0 = items[0]
            self._place(word0, clue0, 0, 0, "across")

            for word, clue in items[1:]:
                candidates = self._find_intersections(word)
                if candidates:
                    # Pick the placement closest to the center of mass
                    if self.cells:
                        avg_r = sum(r for r, c in self.cells) / len(self.cells)
                        avg_c = sum(c for r, c in self.cells) / len(self.cells)
                    else:
                        avg_r, avg_c = 0, 0

                    def score(candidate):
                        r, c, d = candidate
                        dr, dc = (0, 1) if d == "across" else (1, 0)
                        mid_r = r + dr * len(word) / 2
                        mid_c = c + dc * len(word) / 2
                        return (mid_r - avg_r) ** 2 + (mid_c - avg_c) ** 2

                    best = min(candidates, key=score)
                    self._place(word, clue, best[0], best[1], best[2])

            if len(self.placed) > len(best_placed):
                best_placed = list(self.placed)
                best_cells = dict(self.cells)

            if len(self.placed) == len(words_and_clues):
                break  # All words placed!

        self.placed = best_placed
        self.cells = best_cells
        return len(self.placed) == len(words_and_clues)

    def assign_numbers(self):
        """Assign clue numbers to placed words. Numbers are assigned left-to-right, top-to-bottom."""
        # Collect all starting positions
        starts: dict[tuple[int, int], int] = {}
        number = 1

        # Sort placed words by (row, col) to assign numbers in reading order
        sorted_words = sorted(self.placed, key=lambda pw: (pw.row, pw.col))

        for pw in sorted_words:
            key = (pw.row, pw.col)
            if key not in starts:
                starts[key] = number
                number += 1
            pw.number = starts[key]

    def normalize(self):
        """Shift grid so all coordinates are non-negative."""
        if not self.cells:
            return
        min_r = min(r for r, c in self.cells)
        min_c = min(c for r, c in self.cells)
        if min_r == 0 and min_c == 0:
            return

        self.cells = {(r - min_r, c - min_c): v for (r, c), v in self.cells.items()}
        for pw in self.placed:
            pw.row -= min_r
            pw.col -= min_c

    @property
    def bounds(self) -> tuple[int, int]:
        """Return (rows, cols) of the grid."""
        if not self.cells:
            return (0, 0)
        max_r = max(r for r, c in self.cells)
        max_c = max(c for r, c in self.cells)
        return (max_r + 1, max_c + 1)


class CrosswordPuzzle:
    """
    High-level crossword puzzle generator.

    Parameters
    ----------
    words_and_clues : list of (word, clue) tuples
        Each word is the answer and each clue is the question/hint.
    title : str, optional
        Title displayed above the puzzle.
    seed : int, optional
        Random seed for reproducible layouts.
    """

    CELL_COLOR = "#FFFFFF"
    CELL_STROKE = "#000000"
    NUMBER_COLOR = "#000000"
    CLUE_HEADER_COLOR = "#000000"
    CLUE_TEXT_COLOR = "#000000"

    CELL_SIZE = 36
    CELL_PAD = 2
    MARGIN = 30
    FONT_FAMILY = "Comic Sans MS, Comic Neue, cursive, sans-serif"

    def __init__(
        self,
        words_and_clues: list[tuple[str, str]],
        seed: Optional[int] = None,
    ):
        self.words_and_clues = [(w.upper(), c) for w, c in words_and_clues]
        self.grid = CrosswordGrid()
        self._generated = False

        if seed is not None:
            random.seed(seed)

    def generate(self) -> bool:
        """Build the crossword layout. Returns True if all words were placed."""
        all_placed = self.grid.build(self.words_and_clues)
        self.grid.normalize()
        self.grid.assign_numbers()
        self._generated = True

        if not all_placed:
            placed_words = {pw.word for pw in self.grid.placed}
            missing = [w for w, c in self.words_and_clues if w not in placed_words]
            print(f"Warning: Could not place {len(missing)} word(s): {missing}")

        return all_placed

    def _build_svg(self, show_answers: bool = False) -> ET.Element:
        """Construct the SVG element tree — just the grid and stacked clues, no chrome."""
        if not self._generated:
            raise RuntimeError("Call generate() before rendering SVG.")

        rows, cols = self.grid.bounds
        cs = self.CELL_SIZE
        pad = self.MARGIN

        # Gather clues
        across_clues = sorted(
            [pw for pw in self.grid.placed if pw.direction == "across"],
            key=lambda pw: pw.number,
        )
        down_clues = sorted(
            [pw for pw in self.grid.placed if pw.direction == "down"],
            key=lambda pw: pw.number,
        )

        # Layout dimensions
        grid_w = cols * cs
        grid_h = rows * cs
        grid_x0 = pad
        grid_y0 = pad

        # Clue section: stacked (Across then Down)
        clue_line_h = 20
        clue_top = grid_y0 + grid_h + 24
        clue_x = pad

        across_section_h = 22 + len(across_clues) * clue_line_h
        down_header_y = clue_top + across_section_h + 8
        down_section_h = 22 + len(down_clues) * clue_line_h

        total_w = grid_w + 2 * pad
        total_h = int(down_header_y + down_section_h + pad)

        # Root SVG
        svg = ET.Element("svg", {
            "xmlns": "http://www.w3.org/2000/svg",
            "width": str(int(total_w)),
            "height": str(int(total_h)),
            "viewBox": f"0 0 {int(total_w)} {int(total_h)}",
        })
        ET.SubElement(svg, "rect", {"width": "100%", "height": "100%", "fill": "#FFFFFF"})

        # Build set of numbered cellsfor quick lookup
        numbered: dict[tuple[int, int], int] = {}
        for pw in self.grid.placed:
            key = (pw.row, pw.col)
            if key not in numbered:
                numbered[key] = pw.number

        # Draw cells
        for r in range(rows):
            for c in range(cols):
                x = grid_x0 + c * cs
                y = grid_y0 + r * cs
                if (r, c) in self.grid.cells:
                    # White cell with border
                    ET.SubElement(svg, "rect", {
                        "x": str(int(x)),
                        "y": str(int(y)),
                        "width": str(int(cs)),
                        "height": str(int(cs)),
                        "fill": self.CELL_COLOR,
                        "stroke": self.CELL_STROKE,
                        "stroke-width": "1.5",
                    })

                    # Number label
                    if (r, c) in numbered:
                        num_el = ET.SubElement(svg, "text", {
                            "x": str(int(x + 3)),
                            "y": str(int(y + 11)),
                            "font-family": self.FONT_FAMILY,
                            "font-size": "9",
                            "font-weight": "bold",
                            "fill": self.NUMBER_COLOR,
                        })
                        num_el.text = str(numbered[(r, c)])

                    # Answer letter (for answer key)
                    if show_answers:
                        letter_el = ET.SubElement(svg, "text", {
                            "x": str(int(x + cs / 2)),
                            "y": str(int(y + cs / 2 + 5)),
                            "text-anchor": "middle",
                            "font-family": self.FONT_FAMILY,
                            "font-size": "16", "font-weight": "bold",
                            "fill": self.CLUE_TEXT_COLOR,
                        })
                        letter_el.text = self.grid.cells[(r, c)]

        # --- Clues: stacked vertically (Across, then Down) ---

        # Across header
        ah = ET.SubElement(svg, "text", {
            "x": str(int(clue_x)),
            "y": str(int(clue_top)),
            "font-family": self.FONT_FAMILY,
            "font-size": "16", "font-weight": "bold",
            "fill": self.CLUE_HEADER_COLOR,
        })
        ah.text = "Across"

        for i, pw in enumerate(across_clues):
            ct = ET.SubElement(svg, "text", {
                "x": str(int(clue_x + 10)),
                "y": str(int(clue_top + 20 + i * clue_line_h)),
                "font-family": self.FONT_FAMILY,
                "font-size": "13",
                "fill": self.CLUE_TEXT_COLOR,
            })
            ct.text = f"{pw.number}. {pw.clue}"

        # Down header
        dh = ET.SubElement(svg, "text", {
            "x": str(int(clue_x)),
            "y": str(int(down_header_y)),
            "font-family": self.FONT_FAMILY,
            "font-size": "16", "font-weight": "bold",
            "fill": self.CLUE_HEADER_COLOR,
        })
        dh.text = "Down"

        for i, pw in enumerate(down_clues):
            ct = ET.SubElement(svg, "text", {
                "x": str(int(clue_x + 10)),
                "y": str(int(down_header_y + 20 + i * clue_line_h)),
                "font-family": self.FONT_FAMILY,
                "font-size": "13",
                "fill": self.CLUE_TEXT_COLOR,
            })
            ct.text = f"{pw.number}. {pw.clue}"

        return svg

    def to_svg(self, filename: str, show_answers: bool = False):
        """Write the puzzle to an SVG file."""
        svg = self._build_svg(show_answers=show_answers)
        tree = ET.ElementTree(svg)
        ET.indent(tree, space="  ")
        with open(filename, "wb") as f:
            tree.write(f, encoding="utf-8", xml_declaration=True)
        print(f"Saved: {filename}")

    def to_svg_string(self, show_answers: bool = False) -> str:
        """Return the SVG as a string."""
        svg = self._build_svg(show_answers=show_answers)
        ET.indent(svg, space="  ")
        return ET.tostring(svg, encoding="unicode", xml_declaration=True)

    def print_grid(self):
        """Print an ASCII representation of the grid to the console."""
        if not self._generated:
            raise RuntimeError("Call generate() before printing.")

        rows, cols = self.grid.bounds
        for r in range(rows):
            line = ""
            for c in range(cols):
                ch = self.grid.cells.get((r, c))
                line += f" {ch} " if ch else " . "
            print(line)
        print()

        across = [pw for pw in self.grid.placed if pw.direction == "across"]
        down = [pw for pw in self.grid.placed if pw.direction == "down"]

        print("ACROSS")
        for pw in sorted(across, key=lambda p: p.number):
            print(f"  {pw.number}. {pw.clue} ({pw.word})")

        print("DOWN")
        for pw in sorted(down, key=lambda p: p.number):
            print(f"  {pw.number}. {pw.clue} ({pw.word})")


def generate_crossword(
    words_and_clues: list[tuple[str, str]],
    output_file: str = "crossword.svg",
    answer_key_file: Optional[str] = None,
    seed: Optional[int] = None,
) -> CrosswordPuzzle:
    """
    Convenience function: generate a crossword and save to SVG.

    Parameters
    ----------
    words_and_clues : list of (word, clue) pairs
    output_file : path for the blank puzzle SVG
    answer_key_file : optional path for the answer key SVG
    seed : random seed for reproducibility

    Returns
    -------
    CrosswordPuzzle instance
    """
    puzzle = CrosswordPuzzle(words_and_clues, seed=seed)
    puzzle.generate()
    puzzle.to_svg(output_file, show_answers=False)

    if answer_key_file:
        puzzle.to_svg(answer_key_file, show_answers=True)

    return puzzle


if __name__ == "__main__":
    # Quick demo
    demo_words = [
        ("SUN", "It shines bright in the sky"),
        ("MOON", "You can see it at night"),
        ("STAR", "A tiny light that twinkles"),
        ("CLOUD", "White and fluffy in the sky"),
        ("RAIN", "Water falling from clouds"),
        ("SNOW", "Frozen white flakes"),
        ("WIND", "You can feel it but not see it"),
    ]

    puzzle = generate_crossword(
        demo_words,
        output_file="demo_crossword.svg",
        answer_key_file="demo_crossword_key.svg",
        seed=42,
    )
    puzzle.print_grid()
