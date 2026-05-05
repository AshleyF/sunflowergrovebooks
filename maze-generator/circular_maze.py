"""
Circular Maze Generator
=======================
Generates kid-friendly circular mazes as SVG files.

Uses recursive backtracker (depth-first) algorithm for nice winding paths.
Cells are arranged in concentric rings with sectors that double as rings
grow to keep cell proportions reasonable.

Usage:
    from circular_maze import generate_maze
    generate_maze(6, "maze.svg", seed=42)

    # Or batch:
    from circular_maze import generate_batch
    generate_batch(100, output_dir="mazes")
"""

import math
import random
import xml.etree.ElementTree as ET
from collections import deque
from pathlib import Path
from typing import Optional


class CircularMaze:
    """A circular maze using recursive backtracker algorithm."""

    def __init__(self, num_rings: int, seed: Optional[int] = None):
        self.num_rings = max(num_rings, 2)
        if seed is not None:
            random.seed(seed)

        self.sectors_per_ring = self._compute_sectors()
        self.connections: dict[tuple[int, int], set[tuple[int, int]]] = {}
        self._init_cells()
        self._generate()
        self._solution: Optional[list[tuple[int, int]]] = None

    def _compute_sectors(self):
        """Compute sectors per ring, doubling when cells get too wide."""
        sectors = [1]  # ring 0 = center disk (single cell)
        if self.num_rings <= 1:
            return sectors
        base = 8
        sectors.append(base)
        for r in range(2, self.num_rings):
            prev = sectors[-1]
            # Double when arc length per cell exceeds ~2x the ring width
            if 2 * math.pi * r / prev > 2.0:
                sectors.append(prev * 2)
            else:
                sectors.append(prev)
        return sectors

    def _init_cells(self):
        for r in range(self.num_rings):
            for s in range(self.sectors_per_ring[r]):
                self.connections[(r, s)] = set()

    def _get_neighbors(self, ring, sector):
        """Return list of neighboring cells (ring, sector)."""
        neighbors = []

        # Center connects to all ring-1 cells
        if ring == 0:
            if self.num_rings > 1:
                for s in range(self.sectors_per_ring[1]):
                    neighbors.append((1, s))
            return neighbors

        n = self.sectors_per_ring[ring]

        # Same ring: clockwise and counter-clockwise
        neighbors.append((ring, (sector + 1) % n))
        neighbors.append((ring, (sector - 1) % n))

        # Inward
        if ring == 1:
            neighbors.append((0, 0))
        else:
            inner_n = self.sectors_per_ring[ring - 1]
            ratio = n // inner_n
            assert ratio in (1, 2), f"Bad sector ratio {ratio} at ring {ring}"
            neighbors.append((ring - 1, sector // ratio))

        # Outward
        if ring < self.num_rings - 1:
            outer_n = self.sectors_per_ring[ring + 1]
            ratio = outer_n // n
            assert ratio in (1, 2), f"Bad sector ratio {ratio} at ring {ring}"
            for i in range(ratio):
                neighbors.append((ring + 1, sector * ratio + i))

        return neighbors

    def _generate(self):
        """Carve maze using iterative backtracker."""
        visited = set()
        stack = [(0, 0)]
        visited.add((0, 0))

        while stack:
            cell = stack[-1]
            r, s = cell
            unvisited = [nb for nb in self._get_neighbors(r, s) if nb not in visited]
            if unvisited:
                next_cell = random.choice(unvisited)
                self.connections[cell].add(next_cell)
                self.connections[next_cell].add(cell)
                visited.add(next_cell)
                stack.append(next_cell)
            else:
                stack.pop()

    def solve(self) -> list[tuple[int, int]]:
        """BFS from entrance (outer ring, sector 0) to center."""
        if self._solution is not None:
            return self._solution

        start = (self.num_rings - 1, 0)
        end = (0, 0)
        queue = deque([(start, [start])])
        visited = {start}

        while queue:
            cell, path = queue.popleft()
            if cell == end:
                self._solution = path
                return path
            for nb in self.connections[cell]:
                if nb not in visited:
                    visited.add(nb)
                    queue.append((nb, path + [nb]))

        self._solution = []
        return []

    def difficulty_score(self) -> float:
        """
        Score 0.0-1.0 based on solution path length vs total cells.
        Higher = harder (path winds through more of the maze).
        """
        path = self.solve()
        total = sum(self.sectors_per_ring)
        return len(path) / total if total > 0 else 0.0

    def _arc_path_d(self, cx, cy, radius, theta_start, theta_end):
        """SVG path data for a circular arc (clockwise in screen coords)."""
        x1 = cx + radius * math.cos(theta_start)
        y1 = cy + radius * math.sin(theta_start)
        x2 = cx + radius * math.cos(theta_end)
        y2 = cy + radius * math.sin(theta_end)
        span = theta_end - theta_start
        large_arc = 1 if span > math.pi else 0
        return f"M{x1:.2f},{y1:.2f}A{radius:.2f},{radius:.2f} 0 {large_arc} 1 {x2:.2f},{y2:.2f}"

    def to_svg(self, cell_size: int = 32, wall_width: float = 2.5) -> ET.Element:
        """Render as SVG. Entrance on outer ring (sector 0), goal at center."""
        ring_width = cell_size
        total_radius = self.num_rings * ring_width
        pad = 24
        size = int(2 * total_radius + 2 * pad)
        cx = size / 2.0
        cy = size / 2.0

        svg = ET.Element("svg", {
            "xmlns": "http://www.w3.org/2000/svg",
            "width": str(size),
            "height": str(size),
            "viewBox": f"0 0 {size} {size}",
        })
        ET.SubElement(svg, "rect", {
            "width": "100%", "height": "100%", "fill": "#FFFFFF",
        })

        parts = []

        # --- Outer boundary (skip sector 0 for entrance gap) ---
        outer_n = self.sectors_per_ring[self.num_rings - 1]
        for s in range(outer_n):
            if s == 0:
                continue
            t0 = s * 2 * math.pi / outer_n
            t1 = (s + 1) * 2 * math.pi / outer_n
            parts.append(self._arc_path_d(cx, cy, total_radius, t0, t1))

        # --- Ring boundary walls (arc at inner radius of each ring) ---
        # Each arc belongs to the outer cell; drawn when no inward connection.
        for r in range(1, self.num_rings):
            radius = r * ring_width
            n = self.sectors_per_ring[r]
            for s in range(n):
                # Determine inward neighbor
                if r == 1:
                    inward = (0, 0)
                else:
                    inner_n = self.sectors_per_ring[r - 1]
                    ratio = n // inner_n
                    inward = (r - 1, s // ratio)

                if inward not in self.connections[(r, s)]:
                    t0 = s * 2 * math.pi / n
                    t1 = (s + 1) * 2 * math.pi / n
                    parts.append(self._arc_path_d(cx, cy, radius, t0, t1))

        # --- Radial walls (line between CW-adjacent cells in each ring) ---
        # Each wall belongs to cell (r, s) at its CW boundary.
        for r in range(1, self.num_rings):
            n = self.sectors_per_ring[r]
            inner_r = r * ring_width
            outer_r = (r + 1) * ring_width
            for s in range(n):
                cw = (r, (s + 1) % n)
                if cw not in self.connections[(r, s)]:
                    theta = (s + 1) * 2 * math.pi / n
                    x1 = cx + inner_r * math.cos(theta)
                    y1 = cy + inner_r * math.sin(theta)
                    x2 = cx + outer_r * math.cos(theta)
                    y2 = cy + outer_r * math.sin(theta)
                    parts.append(f"M{x1:.2f},{y1:.2f}L{x2:.2f},{y2:.2f}")

        # Draw all walls as a single path
        ET.SubElement(svg, "path", {
            "d": " ".join(parts),
            "stroke": "#000000",
            "stroke-width": str(wall_width),
            "stroke-linecap": "round",
            "fill": "none",
        })

        # --- Entrance arrow (outside outer ring, pointing inward at sector 0) ---
        entrance_mid = math.pi / outer_n  # midpoint angle of sector 0
        tip_r = total_radius + 2
        base_r = total_radius + 10
        tip_x = cx + tip_r * math.cos(entrance_mid)
        tip_y = cy + tip_r * math.sin(entrance_mid)
        perp_x = -math.sin(entrance_mid)
        perp_y = math.cos(entrance_mid)
        base_x = cx + base_r * math.cos(entrance_mid)
        base_y = cy + base_r * math.sin(entrance_mid)
        ET.SubElement(svg, "polygon", {
            "points": (
                f"{base_x + 5*perp_x:.2f},{base_y + 5*perp_y:.2f} "
                f"{tip_x:.2f},{tip_y:.2f} "
                f"{base_x - 5*perp_x:.2f},{base_y - 5*perp_y:.2f}"
            ),
            "fill": "#000000",
        })

        # --- Goal dot at center ---
        ET.SubElement(svg, "circle", {
            "cx": f"{cx:.2f}",
            "cy": f"{cy:.2f}",
            "r": str(max(3, ring_width * 0.15)),
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
    num_rings: int,
    filename: str,
    seed: Optional[int] = None,
    cell_size: int = 32,
) -> CircularMaze:
    """Generate a single circular maze and save to SVG."""
    maze = CircularMaze(num_rings, seed=seed)
    maze.save_svg(filename, cell_size=cell_size)
    return maze


def generate_batch(
    count: int = 100,
    output_dir: str = "mazes",
    min_rings: int = 8,
    max_rings: int = 12,
    cell_size: int = 32,
    base_seed: int = 1000,
    min_difficulty: float = 0.4,
):
    """
    Generate a batch of quality circular mazes with varying ring counts.

    Rejects mazes whose solution path uses less than min_difficulty
    fraction of the total cells.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    rng = random.Random(base_seed)
    generated = 0
    attempt_seed = base_seed
    rejected = 0

    while generated < count:
        rings = rng.randint(min_rings, max_rings)
        maze = CircularMaze(rings, seed=attempt_seed)
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
