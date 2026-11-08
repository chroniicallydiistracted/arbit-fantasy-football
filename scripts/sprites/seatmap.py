"""A venue's seating map (the owner's private SVG references) as section polygons in field yards.

x runs along the field with the goal lines at 0 and 100, z across it from one sideline (0) to the
other (53.33), as the live field's scripts and stadium use them. The map's football field fixes
the scale and the origin.
"""

import re
from pathlib import Path

import numpy as np

NUMBER = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
TOKEN = re.compile(r"[MmLlHhVvCcZz]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


def path_points(d: str, curve_steps: int = 8) -> list[list[tuple[float, float]]]:
    """The subpaths of an SVG path's `d` (M, L, H, V, C, Z, absolute and relative) as point lists."""
    tokens = TOKEN.findall(d)
    out: list[list[tuple[float, float]]] = []
    points: list[tuple[float, float]] = []
    x = y = sx = sy = 0.0
    command = ""
    i = 0

    def num() -> float:
        nonlocal i
        value = float(tokens[i])
        i += 1
        return value

    while i < len(tokens):
        if tokens[i].isalpha():
            command = tokens[i]
            i += 1
            if command in "Zz":
                if points:
                    out.append(points)
                points, x, y = [], sx, sy
                continue
        relative = command.islower()
        c = command.upper()
        if c == "M":
            nx, ny = num(), num()
            x, y = (x + nx, y + ny) if relative else (nx, ny)
            if points:
                out.append(points)
            points, sx, sy = [(x, y)], x, y
            command = "l" if relative else "L"  # later pairs are lines
        elif c == "L":
            nx, ny = num(), num()
            x, y = (x + nx, y + ny) if relative else (nx, ny)
            points.append((x, y))
        elif c == "H":
            nx = num()
            x = x + nx if relative else nx
            points.append((x, y))
        elif c == "V":
            ny = num()
            y = y + ny if relative else ny
            points.append((x, y))
        elif c == "C":
            p = [num() for _ in range(6)]
            if relative:
                p = [p[0] + x, p[1] + y, p[2] + x, p[3] + y, p[4] + x, p[5] + y]
            x0, y0 = x, y
            for k in range(1, curve_steps + 1):
                t = k / curve_steps
                a, b, c2, e = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t**2, t**3
                points.append((a * x0 + b * p[0] + c2 * p[2] + e * p[4], a * y0 + b * p[1] + c2 * p[3] + e * p[5]))
            x, y = p[4], p[5]
        else:
            raise ValueError(f"unsupported path command {command}")
    if points:
        out.append(points)
    return out


def sections(svg: Path) -> dict[str, list[np.ndarray]]:
    """Each selectable section's polygons in field yards (x along, z across), by its id."""
    text = svg.read_text()
    field = re.search(r'<path[^>]*?d="M ([\d.]+),([\d.]+) H ([\d.]+) V ([\d.]+) H [\d.]+ Z"[^>]*?id="football-base-color', text, re.S)
    if field is None:
        raise ValueError("no football field in the map")
    left, top, right, bottom = (float(v) for v in field.groups())
    per_yard = (right - left) / 120.0
    selectable = text[text.index('id="svg-selectable-group"') :]
    found: dict[str, list[np.ndarray]] = {}
    for tag in re.findall(r"<path\b[^>]*?>", selectable, re.S):
        ident = re.search(r'\bid="([^"]+)"', tag)
        d = re.search(r'\bd="([^"]+)"', tag, re.S)
        if not ident or not d:
            continue
        polys = []
        for sub in path_points(d.group(1)):
            arr = np.array(sub)
            # Map x: the left end line is x = -10; map y: the bottom sideline is z = 0.
            polys.append(np.column_stack(((arr[:, 0] - left) / per_yard - 10.0, (bottom - arr[:, 1]) / per_yard)))
        found[ident.group(1)] = polys
    return found
