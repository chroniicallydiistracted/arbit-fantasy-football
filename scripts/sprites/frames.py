"""Sprite frames as text grids of color classes. Standard library only, so checks run anywhere."""

import json
import re
from pathlib import Path

ASSETS = Path(__file__).resolve().parents[2] / "assets" / "sprites"
EMPTY = "."
JERSEY = frozenset("cefh")


def palette() -> dict[str, list[list[int]]]:
    """Each class maps to its color in every set: 32 on the sheet's left, 32 on its right."""
    colors: dict[str, list[list[int]]] = json.loads((ASSETS / "palette.json").read_text())
    return colors


def load_groups() -> dict[str, dict[str, list[str]]]:
    groups: dict[str, dict[str, list[str]]] = {}
    for path in sorted((ASSETS / "frames").glob("*.txt")):
        frames: dict[str, list[str]] = {}
        for chunk in re.split(r"(?m)^== ", path.read_text()):
            if chunk.strip():
                name, *rows = chunk.strip("\n").split("\n")
                if name in frames:
                    raise ValueError(f"duplicate frame {name}")
                frames[name] = rows
        groups[path.stem] = frames
    return groups


def all_frames() -> dict[str, list[str]]:
    merged: dict[str, list[str]] = {}
    for frames in load_groups().values():
        for name, rows in frames.items():
            if name in merged:
                raise ValueError(f"duplicate frame {name}")
            merged[name] = rows
    return merged


def torso_x(rows: list[str]) -> float:
    """Where a frame sits horizontally. Aligning on the jersey keeps a body steady across frames."""
    columns = [x for row in rows for x, cell in enumerate(row) if cell in JERSEY]
    return sum(columns) / len(columns) if columns else max(map(len, rows)) / 2


def problems(frames: dict[str, list[str]], colors: dict[str, list[list[int]]]) -> list[str]:
    """Colors outside the palette and pixels touching nothing, which read as dirt."""
    found: list[str] = []
    for name, rows in frames.items():
        unknown = {cell for row in rows for cell in row} - set(colors) - {EMPTY}
        if unknown:
            found.append(f"{name}: unknown {sorted(unknown)}")
        width = max(map(len, rows))
        grid = [row.ljust(width, EMPTY) for row in rows]
        for y, row in enumerate(grid):
            for x, cell in enumerate(row):
                if cell == EMPTY:
                    continue
                around = [
                    grid[y + dy][x + dx]
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1))
                    if 0 <= y + dy < len(grid) and 0 <= x + dx < width
                ]
                if all(neighbor == EMPTY for neighbor in around):
                    found.append(f"{name}: floating pixel at {x},{y}")
    return found
