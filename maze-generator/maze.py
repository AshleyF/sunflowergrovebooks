"""
Maze Generator
==============
Generates kid-friendly mazes as SVG files.

Uses recursive backtracker (depth-first) algorithm for nice winding paths.
Grid sizes are kept small (8x8 to 12x12) for ages 5-8.
Includes difficulty scoring to reject trivially easy layouts.

Usage:
    from maze import generate_maze
    generate_maze(10, 10, "maze.svg", seed=42)

    # Or batch:
    from maze import generate_batch
    generate_batch(100, output_dir="mazes")
"""

import random
import xml.etree.ElementTree as ET
from collections import deque
from pathlib import Path
from typing import Optional


class Maze:
    """A 2D maze using recursive backtracker algorithm."""

    def __init__(self, width: int, height: int, seed: Optional[int] = None):
        self.width = width
        self.height = height
        if seed is not None:
            random.seed(seed)

        # Each cell tracks which walls are open: set of ("N","S","E","W")
        self.grid: list[list[set[str]]] = [
            [set() for _ in range(width)] for _ in range(height)
        ]
        self._generate()
        self._solution: Optional[list[tuple[int, int]]] = None

    def _generate(self):
        """Carve the maze using iterative backtracker (no recursion limit issues)."""
        opposites = {"N": "S", "S": "N", "E": "W", "W": "E"}
        deltas = {"N": (-1, 0), "S": (1, 0), "E": (0, 1), "W": (0, -1)}

        visited = [[False] * self.width for _ in range(self.height)]
        stack = [(0, 0)]
        visited[0][0] = True

        while stack:
            r, c = stack[-1]
            neighbors = []
            for direction, (dr, dc) in deltas.items():
                nr, nc = r + dr, c + dc
                if 0 <= nr < self.height and 0 <= nc < self.width and not visited[nr][nc]:
                    neighbors.append((direction, nr, nc))

            if neighbors:
                direction, nr, nc = random.choice(neighbors)
                self.grid[r][c].add(direction)
                self.grid[nr][nc].add(opposites[direction])
                visited[nr][nc] = True
                stack.append((nr, nc))
            else:
                stack.pop()

    def solve(self) -> list[tuple[int, int]]:
        """BFS from top-left to bottom-right. Returns the solution path."""
        if self._solution is not None:
            return self._solution

        deltas = {"N": (-1, 0), "S": (1, 0), "E": (0, 1), "W": (0, -1)}
        start = (0, 0)
        end = (self.height - 1, self.width - 1)

        queue = deque([(start, [start])])
        visited = {start}

        while queue:
            (r, c), path = queue.popleft()
            if (r, c) == end:
                self._solution = path
                return path
            for direction in self.grid[r][c]:
                dr, dc = deltas[direction]
                nr, nc = r + dr, c + dc
                if (nr, nc) not in visited:
                    visited.add((nr, nc))
                    queue.append(((nr, nc), path + [(nr, nc)]))

        self._solution = []
        return []

    def difficulty_score(self) -> float:
        """
        Score 0.0-1.0 representing maze difficulty.

        Based on solution path length relative to total cells.
        Higher = harder (solution winds through more of the maze).
        A score of 0.3 means the solution only visits 30% of cells — too easy.
        We want scores >= 0.5 for a decent maze.
        """
        path = self.solve()
        total = self.width * self.height
        return len(path) / total if total > 0 else 0.0

    def to_svg(self, cell_size: int = 32, wall_width: float = 2.5) -> ET.Element:
        """Render the maze as SVG. Entrance on left of (0,0), exit on right of (H-1,W-1)."""
        pad = 24
        maze_w = self.width * cell_size
        maze_h = self.height * cell_size
        total_w = maze_w + 2 * pad
        total_h = maze_h + 2 * pad

        svg = ET.Element("svg", {
            "xmlns": "http://www.w3.org/2000/svg",
            "width": str(total_w),
            "height": str(total_h),
            "viewBox": f"0 0 {total_w} {total_h}",
        })
        ET.SubElement(svg, "rect", {"width": "100%", "height": "100%", "fill": "#FFFFFF"})

        x0, y0 = pad, pad
        segments = []

        # --- Top border ---
        for c in range(self.width):
            segments.append((
                x0 + c * cell_size, y0,
                x0 + (c + 1) * cell_size, y0,
            ))

        # --- Left border (skip row 0 for entrance gap) ---
        for r in range(self.height):
            if r == 0:
                continue  # entrance gap
            segments.append((
                x0, y0 + r * cell_size,
                x0, y0 + (r + 1) * cell_size,
            ))

        # --- Bottom border ---
        for c in range(self.width):
            segments.append((
                x0 + c * cell_size, y0 + self.height * cell_size,
                x0 + (c + 1) * cell_size, y0 + self.height * cell_size,
            ))

        # --- Right border (skip last row for exit gap) ---
        for r in range(self.height):
            if r == self.height - 1:
                continue  # exit gap
            segments.append((
                x0 + self.width * cell_size, y0 + r * cell_size,
                x0 + self.width * cell_size, y0 + (r + 1) * cell_size,
            ))

        # --- Interior horizontal walls (between row r and r+1) ---
        for r in range(self.height - 1):
            for c in range(self.width):
                if "S" not in self.grid[r][c]:
                    segments.append((
                        x0 + c * cell_size, y0 + (r + 1) * cell_size,
                        x0 + (c + 1) * cell_size, y0 + (r + 1) * cell_size,
                    ))

        # --- Interior vertical walls (between col c and c+1) ---
        for r in range(self.height):
            for c in range(self.width - 1):
                if "E" not in self.grid[r][c]:
                    segments.append((
                        x0 + (c + 1) * cell_size, y0 + r * cell_size,
                        x0 + (c + 1) * cell_size, y0 + (r + 1) * cell_size,
                    ))

        # Draw all walls as a single path
        path_d = " ".join(f"M{x1},{y1}L{x2},{y2}" for x1, y1, x2, y2 in segments)
        ET.SubElement(svg, "path", {
            "d": path_d,
            "stroke": "#000000",
            "stroke-width": str(wall_width),
            "stroke-linecap": "round",
            "fill": "none",
        })

        # Entry arrow — centered on the left gap (row 0), pointing right into the maze
        entry_cy = y0 + cell_size / 2
        ax = x0 - 4
        ET.SubElement(svg, "polygon", {
            "points": (
                f"{ax - 8},{entry_cy - 5} "
                f"{ax},{entry_cy} "
                f"{ax - 8},{entry_cy + 5}"
            ),
            "fill": "#000000",
        })

        # Exit arrow — centered on the right gap (last row), pointing right out
        exit_cy = y0 + (self.height - 1) * cell_size + cell_size / 2
        ax = x0 + maze_w + 4
        ET.SubElement(svg, "polygon", {
            "points": (
                f"{ax},{exit_cy - 5} "
                f"{ax + 8},{exit_cy} "
                f"{ax},{exit_cy + 5}"
            ),
            "fill": "#000000",
        })

        return svg

    def save_svg(self, filename: str, cell_size: int = 32):
        """Write maze to an SVG file."""
        svg = self.to_svg(cell_size=cell_size)
        tree = ET.ElementTree(svg)
        ET.indent(tree, space="  ")
        with open(filename, "wb") as f:
            tree.write(f, encoding="utf-8", xml_declaration=True)


def generate_maze(
    width: int,
    height: int,
    filename: str,
    seed: Optional[int] = None,
    cell_size: int = 32,
) -> Maze:
    """Generate a single maze and save to SVG."""
    maze = Maze(width, height, seed=seed)
    maze.save_svg(filename, cell_size=cell_size)
    return maze


def generate_batch(
    count: int = 100,
    output_dir: str = "mazes",
    min_size: int = 8,
    max_size: int = 12,
    cell_size: int = 32,
    base_seed: int = 1000,
    min_difficulty: float = 0.5,
):
    """
    Generate a batch of quality mazes with varying sizes.

    Rejects mazes whose solution path uses less than min_difficulty
    fraction of the total cells (avoids trivially easy mazes with
    large unreachable dead-end sections).
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    rng = random.Random(base_seed)
    generated = 0
    attempt_seed = base_seed
    rejected = 0

    while generated < count:
        w = rng.randint(min_size, max_size)
        h = rng.randint(min_size, max_size)
        maze = Maze(w, h, seed=attempt_seed)
        score = maze.difficulty_score()
        attempt_seed += 1

        if score < min_difficulty:
            rejected += 1
            continue

        generated += 1
        filename = out / f"maze_{generated:03d}.svg"
        maze.save_svg(str(filename), cell_size=cell_size)

    print(f"Generated {count} mazes in {output_dir}/ (rejected {rejected} too-easy ones)")


if __name__ == "__main__":
    generate_batch(100, output_dir="mazes")
