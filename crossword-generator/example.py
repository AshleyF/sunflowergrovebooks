#!/usr/bin/env python3
"""
Example: Generate a kid-friendly crossword puzzle about animals.
"""

from crossword import generate_crossword

# Words and their clues — geared toward young readers
animal_words = [
    ("ELEPHANT", "The biggest animal that walks on land"),
    ("TIGER", "A big cat with orange and black stripes"),
    ("PENGUIN", "A bird that swims but cannot fly"),
    ("GIRAFFE", "The tallest animal with a very long neck"),
    ("DOLPHIN", "A friendly sea creature that jumps and plays"),
    ("RABBIT", "A fluffy animal with long ears that hops"),
    ("PARROT", "A colorful bird that can learn to talk"),
    ("TURTLE", "A slow animal that carries its house"),
    ("MONKEY", "A silly animal that swings from trees"),
    ("ZEBRA", "A horse-like animal with black and white stripes"),
]

if __name__ == "__main__":
    print("Generating 'Amazing Animals' crossword puzzle...")
    print()

    puzzle = generate_crossword(
        animal_words,
        title="Amazing Animals!",
        output_file="animals_crossword.svg",
        answer_key_file="animals_crossword_key.svg",
        seed=123,
    )

    puzzle.print_grid()

    print()
    print("Files created:")
    print("  animals_crossword.svg      — blank puzzle")
    print("  animals_crossword_key.svg  — answer key")
