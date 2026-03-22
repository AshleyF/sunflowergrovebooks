#!/usr/bin/env python3
"""
Generate a crossword puzzle from a JSON file.

Usage:
    python from_json.py puzzles/sunflower_grove.json
    python from_json.py puzzles/sunflower_grove.json --output my_puzzle.svg
"""

import argparse
import json
import os
from crossword import generate_crossword


def main():
    parser = argparse.ArgumentParser(description="Generate a crossword from a JSON file")
    parser.add_argument("json_file", help="Path to JSON file with words and clues")
    parser.add_argument("--output", "-o", help="Output SVG filename (default: based on input name)")
    args = parser.parse_args()

    with open(args.json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    seed = data.get("seed", None)
    words_and_clues = [tuple(pair) for pair in data["words_and_clues"]]

    out_dir = "crosswords"
    os.makedirs(out_dir, exist_ok=True)

    base = os.path.splitext(os.path.basename(args.json_file))[0]
    output = args.output or os.path.join(out_dir, f"{base}_crossword.svg")
    answer_key = output.replace(".svg", "_key.svg")

    puzzle = generate_crossword(
        words_and_clues,
        output_file=output,
        answer_key_file=answer_key,
        seed=seed,
    )
    puzzle.print_grid()

    print()
    print(f"Puzzle:     {output}")
    print(f"Answer key: {answer_key}")


if __name__ == "__main__":
    main()
