# Crossword Puzzle Generator 🧩

A Python tool for generating kid-friendly crossword puzzles as SVG files.

## Quick Start

```python
from crossword import generate_crossword

words_and_clues = [
    ("SUN", "It shines bright in the sky"),
    ("MOON", "You can see it at night"),
    ("STAR", "A tiny light that twinkles"),
    ("CLOUD", "White and fluffy in the sky"),
    ("RAIN", "Water falling from clouds"),
]

puzzle = generate_crossword(
    words_and_clues,
    title="Sky & Weather",
    output_file="puzzle.svg",
    answer_key_file="puzzle_key.svg",
    seed=42,
)
```

## Features

- **SVG output** — scalable, print-ready puzzles
- **Answer key** — optional second SVG with letters filled in
- **Kid-friendly styling** — warm colors, rounded corners, playful font
- **Numbered clues** — standard crossword format (Across / Down)
- **Greedy placement** — automatically arranges words with intersections
- **Reproducible** — use `seed` parameter for consistent layouts

## API

### `generate_crossword(words_and_clues, title, output_file, answer_key_file, seed)`

Convenience function that generates and saves in one call.

### `CrosswordPuzzle(words_and_clues, title, seed)`

Full control:

```python
from crossword import CrosswordPuzzle

puzzle = CrosswordPuzzle(words_and_clues, title="My Puzzle", seed=42)
puzzle.generate()          # build the layout
puzzle.print_grid()        # ASCII preview in terminal
puzzle.to_svg("out.svg")   # blank puzzle
puzzle.to_svg("key.svg", show_answers=True)  # answer key
svg_str = puzzle.to_svg_string()  # get SVG as string
```

## Example

```bash
cd crossword-generator
python example.py
```

Generates `animals_crossword.svg` and `animals_crossword_key.svg`.

## Requirements

Python 3.10+ (standard library only — no dependencies).
