#!/usr/bin/env python3
"""
Generate a word search puzzle from a JSON file.

Usage:
    python from_json.py puzzles/animals.json
    python from_json.py puzzles/animals.json --output my_puzzle.svg
"""

import argparse
import json
import os
from wordsearch import generate_wordsearch


def main():
    parser = argparse.ArgumentParser(description="Generate a word search from a JSON file")
    parser.add_argument("json_file", help="Path to JSON file with word list")
    parser.add_argument("--output", "-o", help="Output SVG filename")
    parser.add_argument("--size", type=int, default=None, help="Grid size (default: from JSON or 10)")
    args = parser.parse_args()

    with open(args.json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    words = data["words"]
    seed = data.get("seed", None)
    size = args.size or data.get("size", 10)

    out_dir = "wordsearches"
    os.makedirs(out_dir, exist_ok=True)

    base = os.path.splitext(os.path.basename(args.json_file))[0]
    output = args.output or os.path.join(out_dir, f"{base}_wordsearch.svg")
    answer_key = output.replace(".svg", "_key.svg")

    puzzle = generate_wordsearch(
        words,
        output_file=output,
        answer_key_file=answer_key,
        size=size,
        seed=seed,
    )
    puzzle.print_grid()

    print()
    print(f"Puzzle:     {output}")
    print(f"Answer key: {answer_key}")


if __name__ == "__main__":
    main()
