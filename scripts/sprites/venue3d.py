"""A stadium as a real 3D model behind the live field (OWN-050, OWN-059): its own shape and parts,
not a recolored generic bowl.

A venue's model is built from its private references:
- **Plan.** The seating map's sections (`seatmap.py`), scaled about the field's center so the lower
  bowl's front matches the field-level wall measured in the reference frame. The map's own field
  is drawn small, as seat maps do; the bowl is to scale.
- **Heights.** Each tier (lower bowl, club, upper deck) has a front height and a rake, measured by
  intersecting the reference camera's rays with the tier edges' real positions.
- **Structures** in yards: the field wall, the fascias, suite rows, the press box, light banks and
  video boards.

Rendering is a small software rasterizer. Every triangle is drawn in depth order into a buffer of
material, section and row coordinates, and each material is then shaded procedurally:
- **Seats:** the seat color with risers, stairs at each section's sides, cross-aisles, tunnel
  portals and a crowd.
- **Glass:** suites with their frames.
- **Lamps:** lit.

The camera is any pinhole camera: the live field's, or the reference's own, so the model can be laid
over its reference and checked.
"""

from dataclasses import dataclass, field

import numpy as np
from PIL import Image

# Materials.
SKY, SEATS, CONCRETE, FASCIA, GLASS, BOARD, LAMPS, STEEL, ROOF, GROUND, TUNNEL = range(11)


@dataclass
class View:
    """A pinhole camera: where it is, where it looks, and its frame."""

    position: np.ndarray
    forward: np.ndarray
    right: np.ndarray
    up: np.ndarray
    focal: float
    width: int
    height: int

    @classmethod
    def of(cls, camera, width: int | None = None, height: int | None = None) -> "View":
        """The live field's camera (`preview.Camera`) or the reference's (`refcam.Cam`)."""
        if hasattr(camera, "shot"):
            return cls(camera.position, camera.forward, camera.right, camera.up, camera.shot.focal, camera.shot.width, camera.shot.height)
        return cls(camera.pos, camera.fwd, camera.right, camera.up, camera.focal, width or 0, height or 0)

    def project(self, points: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        offset = points - self.position
        depth = offset @ self.forward
        with np.errstate(divide="ignore", invalid="ignore"):
            u = self.width / 2 + self.focal * (offset @ self.right) / depth
            v = self.height / 2 - self.focal * (offset @ self.up) / depth
        return u, v, depth


@dataclass
class Mesh:
    """Triangles, each with a material and a part number, and per-corner attributes:
    s (yards across the part), r (yards up or back from its front edge) and the part's width."""

    vertices: list[np.ndarray] = field(default_factory=list)  # each (3, 3)
    attributes: list[np.ndarray] = field(default_factory=list)  # each (3, 2): s, r
    materials: list[int] = field(default_factory=list)
    parts: list[int] = field(default_factory=list)
    widths: list[float] = field(default_factory=list)
    tiers: list[int] = field(default_factory=list)

    def add(self, tri: np.ndarray, attrs: np.ndarray, material: int, part: int, width: float = 0.0, tier: int = 0) -> None:
        self.vertices.append(np.asarray(tri, float))
        self.attributes.append(np.asarray(attrs, float))
        self.materials.append(material)
        self.parts.append(part)
        self.widths.append(width)
        self.tiers.append(tier)

    def quad(self, a, b, c, d, material: int, part: int, width: float = 0.0, tier: int = 0, uv=None) -> None:
        """Corners in order a-b-c-d; `uv` gives each corner's (s, r)."""
        uv = uv if uv is not None else [(0, 0), (width, 0), (width, 1), (0, 1)]
        self.add([a, b, c], [uv[0], uv[1], uv[2]], material, part, width, tier)
        self.add([a, c, d], [uv[0], uv[2], uv[3]], material, part, width, tier)


def seating_section(mesh: Mesh, front, back, part: int, tier: int) -> None:
    """A seating section between measured front/back rails, each left-to-right in world yards.

    Heights come from those rails, never from a radial distance normalized separately for each
    polygon. Neighboring sections therefore share a straight, level edge when their rails do.
    Row coordinates measure plan depth, and normalized width keeps stairs on tapered edges.
    """
    front, back = np.asarray(front, float), np.asarray(back, float)
    if front.shape != (2, 3) or back.shape != (2, 3) or not np.isfinite([front, back]).all():
        raise ValueError("seating rails must be two finite 3D points each")
    across = (front[1] - front[0])[[0, 2]]
    width = float(np.linalg.norm(across))
    if width <= 1e-6:
        raise ValueError("seating section needs a nonzero width")
    outward = (back.mean(axis=0) - front.mean(axis=0))[[0, 2]]
    depth = float(abs(across[0] * outward[1] - across[1] * outward[0]) / width)
    if depth <= 1e-6 or np.linalg.norm((back[1] - back[0])[[0, 2]]) <= 1e-6:
        raise ValueError("seating section needs a nonzero depth and back width")
    polygon = np.array([front[0], front[1], back[1], back[0]])[:, [0, 2]]
    edges = np.roll(polygon, -1, axis=0) - polygon
    following = np.roll(edges, -1, axis=0)
    turns = edges[:, 0] * following[:, 1] - edges[:, 1] * following[:, 0]
    if not ((turns > 1e-8).all() or (turns < -1e-8).all()):
        raise ValueError("seating rails must form a convex, non-crossing section")
    mesh.quad(front[0], front[1], back[1], back[0], SEATS, part, width, tier,
              [(0, 0), (width, 0), (width, depth), (0, depth)])


@dataclass
class GBuffer:
    depth: np.ndarray
    material: np.ndarray
    part: np.ndarray
    s: np.ndarray
    r: np.ndarray
    width: np.ndarray
    tier: np.ndarray
    normal_y: np.ndarray  # how much the surface faces up: 1 a seating deck, 0 a wall


def rasterize(mesh: Mesh, view: View, band: tuple[int, int]) -> GBuffer:
    top, bottom = band
    rows, cols = bottom - top, view.width
    g = GBuffer(
        np.full((rows, cols), np.inf),
        np.full((rows, cols), SKY, np.int16),
        np.full((rows, cols), -1, np.int32),
        np.zeros((rows, cols)),
        np.zeros((rows, cols)),
        np.zeros((rows, cols)),
        np.zeros((rows, cols), np.int8),
        np.zeros((rows, cols)),
    )
    if not mesh.vertices:
        return g
    tris = np.stack(mesh.vertices)
    u, v, d = view.project(tris.reshape(-1, 3))
    u, v, d = u.reshape(-1, 3), v.reshape(-1, 3), d.reshape(-1, 3)
    edges1, edges2 = tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0]
    normals = np.cross(edges1, edges2)
    lengths = np.linalg.norm(normals, axis=1)
    normal_y = np.abs(normals[:, 1]) / np.where(lengths > 0, lengths, 1)
    for i in range(len(tris)):
        if (d[i] < 0.5).any():
            continue  # behind or at the camera: the stands never are
        x0, x1 = int(max(0, np.floor(u[i].min()))), int(min(cols - 1, np.ceil(u[i].max())))
        y0, y1 = int(max(top, np.floor(v[i].min()))), int(min(bottom - 1, np.ceil(v[i].max())))
        if x0 > x1 or y0 > y1:
            continue
        px, py = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        (ax, bx, cx), (ay, by, cy) = u[i], v[i]
        area = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
        if abs(area) < 1e-9:
            continue
        w0 = ((bx - px) * (cy - py) - (by - py) * (cx - px)) / area
        w1 = ((cx - px) * (ay - py) - (cy - py) * (ax - px)) / area
        w2 = 1 - w0 - w1
        inside = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
        if not inside.any():
            continue
        inverse = w0 / d[i, 0] + w1 / d[i, 1] + w2 / d[i, 2]
        depth = 1 / inverse
        sub = (slice(y0 - top, y1 - top + 1), slice(x0, x1 + 1))
        closer = inside & (depth < g.depth[sub])
        if not closer.any():
            continue
        attrs = mesh.attributes[i]
        s = (w0 * attrs[0, 0] / d[i, 0] + w1 * attrs[1, 0] / d[i, 1] + w2 * attrs[2, 0] / d[i, 2]) * depth
        r = (w0 * attrs[0, 1] / d[i, 0] + w1 * attrs[1, 1] / d[i, 1] + w2 * attrs[2, 1] / d[i, 2]) * depth
        g.depth[sub][closer] = depth[closer]
        g.material[sub][closer] = mesh.materials[i]
        g.part[sub][closer] = mesh.parts[i]
        g.s[sub][closer] = s[closer]
        g.r[sub][closer] = r[closer]
        g.width[sub][closer] = mesh.widths[i]
        g.tier[sub][closer] = mesh.tiers[i]
        g.normal_y[sub][closer] = normal_y[i]
    return g


def _hash(*parts: np.ndarray, seed: int = 0) -> np.ndarray:
    mask = np.uint64(0xFFFFFFFF)
    h = np.full(np.shape(parts[0]), np.uint64((seed * 2654435761) & 0xFFFFFFFF), dtype=np.uint64)
    for prime, part in zip((73856093, 19349663, 83492791), parts, strict=False):
        h ^= (np.asarray(part).astype(np.int64).astype(np.uint64) * np.uint64(prime)) & mask
        h = (h * np.uint64(2246822519)) & mask
        h ^= h >> np.uint64(13)
    return h


def shade(g: GBuffer, look: dict, crowd: dict | None = None, seed: int = 0, night: bool = False) -> Image.Image:
    """Colors for every pixel from its material and coordinates. `look` holds the venue's colors
    and seating details; `crowd` (fan colors) fills the seats for a game."""
    rows, cols = g.material.shape
    out = np.zeros((rows, cols, 3))
    sky = np.array(look.get("night_sky" if night else "sky", (120, 160, 196)), float)
    yy = (np.arange(rows) / max(1, rows))[:, None, None]
    out[:] = sky * (0.85 + 0.25 * yy)  # a little lighter toward the horizon
    concrete = np.array(look["concrete"], float)
    seat = np.array(look["seat"], float)

    m = g.material
    flat = (0.92 + 0.12 * g.normal_y)[..., None]  # decks catch more light than walls

    # Seats: rows, stairs at each section's sides, a cross-aisle, tunnel portals and a crowd.
    mask = m == SEATS
    if mask.any():
        s, r, width, tier = g.s[mask], g.r[mask], g.width[mask], g.tier[mask]
        tread = look.get("tread", 0.95)
        color = np.tile(seat, (len(s), 1))
        riser = (r % tread) < tread * 0.32
        color[riser] *= 0.72
        # Individual chair backs keep empty decks legible as seating instead of striped slabs.
        seat_phase = (s / 0.55) % 1.0
        gap = (seat_phase < 0.10) | (seat_phase > 0.90)
        color[gap] *= 0.72
        lip = ~gap & ((r % tread) >= tread * 0.32) & ((r % tread) < tread * 0.44)
        color[lip] *= 1.12
        if crowd is not None:
            seat_index, row_index = np.floor(s / 0.55), np.floor(r / tread)
            h = _hash(seat_index, row_index, g.part[mask], seed=seed)
            u, vv = (s / 0.55) % 1.0, (r / tread) % 1.0
            filled = (h % np.uint64(100)) >= crowd.get("empty", 12)
            palette = np.array(crowd["colors"], float)
            shirt = palette[((h >> np.uint64(8)) % np.uint64(len(palette))).astype(np.int64)]
            skin = np.array([(236, 196, 164), (204, 152, 112), (156, 104, 66), (102, 66, 42)], float)[((h >> np.uint64(16)) % np.uint64(4)).astype(np.int64)]
            body = filled & (u > 0.2) & (u < 0.8) & (vv > 0.3) & (vv < 0.75)
            head = filled & (u > 0.32) & (u < 0.68) & (vv >= 0.75) & (vv < 0.95)
            color[body] = shirt[body]
            color[head] = skin[head]
        stairs = (s < 0.6) | (s > width - 0.6)
        steps = (r % (tread / 2)) < tread * 0.12
        color[stairs] = concrete * np.where(steps[stairs], 0.78, 1.0)[:, None]
        for walk in look.get("walkways", []):
            band = (tier == walk["tier"]) & (r >= walk["r"]) & (r < walk["r"] + walk["depth"])
            color[band] = concrete * 0.96
        for shadow in look.get("shadows", []):
            # Rows under the tier above, out of the light.
            under = (tier == shadow["tier"]) & (r >= shadow["r"]) & (r < shadow["r"] + shadow["depth"])
            color[under] *= shadow["shade"]
        for portal in look.get("portals", []):
            # A tunnel at a section's side: a concrete frame and a dark opening.
            near_side = np.minimum(s, width - s) < portal["half"]
            rows_ok = (tier == portal["tier"]) & (r >= portal["r"]) & (r < portal["r"] + portal["depth"])
            frame = near_side & rows_ok
            opening = frame & (np.minimum(s, width - s) < portal["half"] - 0.35) & (r < portal["r"] + portal["depth"] - 0.35) & (r > portal["r"] + 0.2)
            color[frame] = concrete * 1.02
            color[opening] = (24, 24, 28)
        out[mask] = color * flat[mask]

    for material, key, default in ((CONCRETE, "concrete", (200, 198, 188)), (FASCIA, "fascia", (226, 224, 216)), (STEEL, "steel", (150, 152, 156)), (ROOF, "roof", (70, 74, 80)), (GROUND, "apron", (90, 120, 60)), (TUNNEL, "tunnel", (22, 24, 28))):
        mask = m == material
        if mask.any():
            out[mask] = np.array(look.get(key, default), float) * flat[mask]

    # Suites: each one's front has a frame around it and evenly spaced mullions across its own
    # width, and is lit or dark as one room.
    mask = m == GLASS
    if mask.any():
        s, r, width, part = g.s[mask], g.r[mask], g.width[mask], g.part[mask]
        color = np.tile(np.array(look.get("glass", (26, 28, 32)), float), (len(s), 1))
        height = look.get("suite_height", 4.3)
        panes = np.maximum(1, np.round(width / look.get("pane", 1.5)))
        pane = width / panes
        frame = (r < 0.55) | (r > height - 0.35) | (s < 0.25) | (s > width - 0.25) | ((s % pane) < 0.12)
        color[frame] = np.array(look.get("fascia", (226, 224, 216)), float)
        if night:
            room = (_hash(part, seed=seed + 1) % np.uint64(100)).astype(float)
            lit = ~frame & (room < 45)
            color[lit] = np.array((236, 200, 140), float) * (0.6 + 0.3 * room[lit, None] / 100)
        out[mask] = color

    # Video boards: dark screens in a light frame.
    mask = m == BOARD
    if mask.any():
        s, r, width = g.s[mask], g.r[mask], g.width[mask]
        edge = (s < 0.5) | (s > width - 0.5) | (r < 0.5) | (r > look.get("board_height", 8.0) - 0.5)
        split = np.abs(s - width * look.get("board_split", 0.62)) < 0.4
        color = np.tile(np.array(look.get("screen", (34, 36, 40)), float), (len(s), 1))
        color[edge | split] = np.array(look.get("fascia", (226, 224, 216)), float) * 0.9
        out[mask] = color

    # Light banks: rows of lamps in a frame.
    mask = m == LAMPS
    if mask.any():
        s, r = g.s[mask], g.r[mask]
        lamp = ((s * 1.6) % 1.0 < 0.62) & ((r * 1.6) % 1.0 < 0.62)
        color = np.tile(np.array(look.get("steel", (150, 152, 156)), float), (len(s), 1))
        color[lamp] = (250, 250, 240) if not night else (255, 252, 230)
        out[mask] = color
    if night:
        # Under the stadium lights: everything but the lights a little darker than day.
        dim = ~np.isin(m, (LAMPS, SKY)) & ~((m == GLASS) & (out.sum(axis=-1) > 560))
        out[dim] *= look.get("night_light", 0.84)
    return Image.fromarray(np.clip(np.rint(out), 0, 255).astype(np.uint8))
