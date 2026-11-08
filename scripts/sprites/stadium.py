"""The stadium around the field in the full-field view: sideline turf, walls, stands and crowd.

The full-field camera is fixed (OWN-030), so the stadium is computed once per game and drawn
behind the field, as the field itself is. Every screen pixel's ray from the camera is traced
against a stadium bowl built around the field in yards, and the first surface it meets decides
the color from that surface's own coordinates. Rows, seats and aisles therefore line up in true
perspective with the field and the players. One ray per pixel keeps the seats crisp pixels like
the players' sprites; averaging 3x3 rays looked no softer at display size and made the image
nearly twice as large to download.

The bowl, from the field out, on the far sideline and behind both end zones (the camera sits in
the near stands, so they are never in view):
- **Sideline turf** continuing the field art's own border color, with the benches in the far
  team area.
- **A padded wall** in the home team's first color, capped in its second.
- **The lower bowl:** rows rising at about 30 degrees, with aisles and tunnel portals. Most fans
  wear the home team's colors, some the visitors' or neutral colors, and a few seats are empty.
  At a neutral site, such as an international game, the two teams' fans are even and the walls,
  seats and club level are neutral gray.
- **The club level:** a band of lit windows in a home-colored fascia.
- **The upper deck:** steeper rows of crowd, then the roof rim with its light banks.

The stands are kept darker and less saturated than the field so the play stays the brightest
thing in the frame, as under stadium lights. It is a generic bowl in the home team's colors:
no logos, wordmarks or copy of a real venue. Every choice is seeded by the game, so a game's
stadium never changes between builds.
"""

from dataclasses import dataclass

import numpy as np
from PIL import Image

RGB = tuple[int, int, int]

# In yards: x along the field (goal lines at 0 and 100), z across it (near sideline 0, far
# 53.3), y up. The field art covers x -13.3 to 113.4 and z -3.5 to 56.7.
FAR_WALL, LEFT_WALL, RIGHT_WALL = 66.0, -22.0, 122.0
WALL = 2.5
LOWER_SLOPE, LOWER_DEPTH = 0.58, 18.0  # about 30 degrees, 18 yards of rows
CLUB = 4.0
UPPER_SLOPE, UPPER_DEPTH = 0.72, 24.0
RIM = 3.0
ROW, SEAT = 0.95, 0.55  # yards a row runs back, and one seat's width
AISLE_EVERY = 22  # seats between aisles; a tunnel opens beside every other aisle
EMPTY = 7  # percent of seats left empty
SAMPLES = 1  # rays per pixel on each axis
STANDS_LIGHT, STANDS_SATURATION = 0.74, 0.8
TEAM_AREA = (32.0, 68.0)  # between the 32-yard lines

SKY: RGB = (12, 15, 24)
NEUTRAL: tuple[RGB, ...] = ((236, 236, 230), (36, 36, 40), (128, 130, 134), (56, 70, 102), (172, 44, 44), (196, 196, 188))
SKIN: tuple[RGB, ...] = ((236, 196, 164), (204, 152, 112), (156, 104, 66), (102, 66, 42))
RISER: RGB = (46, 48, 52)
AISLE: tuple[RGB, RGB] = (150, 150, 146), (122, 122, 118)
WINDOW_LIT, WINDOW_DARK = (226, 200, 146), (40, 46, 58)
PANE = 2.2  # yards per club window pane
BENCH: RGB = (34, 36, 40)
NEUTRAL_VENUE: tuple[RGB, ...] = ((62, 66, 74), (150, 154, 160))

GROUND, WALL_FACE, LOWER, CLUB_FACE, UPPER, RIM_FACE = 1, 2, 3, 4, 5, 6


@dataclass(frozen=True)
class Colors:
    home: tuple[RGB, ...]  # the home team's colors, first to last
    away: tuple[RGB, ...]
    turf: RGB  # the field art's own border, which the sideline turf continues
    neutral: bool = False  # a neutral site: nobody's colors on the building, an even crowd

    @property
    def venue(self) -> tuple[RGB, ...]:
        """The building's own colors: the home team's, or neutral gray at a neutral site."""
        return NEUTRAL_VENUE if self.neutral else self.home


def rgb(hex_color: str) -> RGB:
    value = hex_color.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def turf_color(field: Image.Image) -> RGB:
    """The field art's outer border, so the turf beyond it continues without a seam."""
    pixels = np.asarray(field.convert("RGB"), dtype=np.float64)
    edges = [pixels[:12], pixels[-12:], pixels[:, :12], pixels[:, -12:]]
    median = np.median(np.concatenate([e.reshape(-1, 3) for e in edges]), axis=0)
    return int(median[0]), int(median[1]), int(median[2])


def layer(camera, band: tuple[int, int], colors: Colors, seed: int, venue: dict | None = None) -> Image.Image:
    """The stadium as `camera` sees it, for frame rows `band` (an RGB image). With a `venue`
    measured by `venues.py`, the stands take that building's design; without one they are the
    generic bowl in the home team's colors."""
    top, bottom = band
    width = camera.shot.width
    out = np.zeros((bottom - top, width, 3), dtype=np.float64)
    step = 24
    for row in range(top, bottom, step):
        rows = min(step, bottom - row)
        sub = (np.arange(rows * SAMPLES) + 0.5) / SAMPLES + row
        cols = (np.arange(width * SAMPLES) + 0.5) / SAMPLES
        ys, xs = np.meshgrid(sub, cols, indexing="ij")
        hits = _trace(camera, xs, ys)
        color = _shade(hits, colors, seed) if venue is None else _shade_venue(camera, hits, colors, seed, venue)
        color = color.reshape(rows, SAMPLES, width, SAMPLES, 3).mean(axis=(1, 3))
        out[row - top : row - top + rows] = color
    return Image.fromarray(np.clip(np.rint(out), 0, 255).astype(np.uint8))


@dataclass
class Hits:
    kind: np.ndarray  # which surface: 0 sky, else GROUND .. RIM_FACE
    along: np.ndarray  # yards along the surface's own row direction (x for ground)
    out: np.ndarray  # yards out from the wall line (z for ground)
    up: np.ndarray  # yards up the face, for walls, club level and rim
    side: np.ndarray  # -1 the ground, 0 the far stands, 1 behind the left end zone, 2 the right
    point: np.ndarray  # where the ray met it, in yards (x, y, z)


def _trace(camera, xs: np.ndarray, ys: np.ndarray) -> Hits:
    shot = camera.shot
    a = (xs - shot.width / 2) / shot.focal
    b = -(ys - shot.height / 2) / shot.focal
    f, r, u = camera.forward, camera.right, camera.up
    d = np.stack([f[i] + a * r[i] + b * u[i] for i in range(3)], axis=-1)
    c = camera.position
    nearest = np.full(a.shape, np.inf)
    hits = Hits(
        np.zeros(a.shape, np.int8),
        np.zeros(a.shape),
        np.zeros(a.shape),
        np.zeros(a.shape),
        np.full(a.shape, -1, np.int8),
        np.zeros(a.shape + (3,)),
    )
    side = -1
    p = np.zeros(a.shape + (3,))

    def keep(t: np.ndarray, valid: np.ndarray, kind: int, along: np.ndarray, out: np.ndarray, up: np.ndarray) -> None:
        closer = valid & (t > 0) & (t < nearest)
        nearest[closer] = t[closer]
        hits.kind[closer] = kind
        hits.along[closer] = along[closer]
        hits.out[closer] = out[closer]
        hits.up[closer] = up[closer]
        hits.side[closer] = side
        hits.point[closer] = p[closer]

    def plane(axis: int, at: float) -> tuple[np.ndarray, np.ndarray]:
        t = (at - c[axis]) / d[..., axis]
        return t, c + t[..., None] * d

    def slope(axis: int, sign: int, start: float, base: float, k: float) -> tuple[np.ndarray, np.ndarray]:
        """Where the ray meets y = base + k * (yards out past `start` along `axis`)."""
        t = (base + k * sign * (c[axis] - start) - c[1]) / (d[..., 1] - k * sign * d[..., axis])
        return t, c + t[..., None] * d

    zero = np.zeros(a.shape)
    with np.errstate(divide="ignore", invalid="ignore"):
        t, p = plane(1, 0.0)
        inside = (p[..., 0] > LEFT_WALL) & (p[..., 0] < RIGHT_WALL) & (p[..., 2] < FAR_WALL)
        keep(t, inside, GROUND, p[..., 0], p[..., 2], zero)
        # The far stands run along x; the end-zone stands along z.
        for side, (axis, along, sign, wall) in enumerate(((2, 0, +1, FAR_WALL), (0, 2, -1, LEFT_WALL), (0, 2, +1, RIGHT_WALL))):
            t, p = plane(axis, wall)
            keep(t, (p[..., 1] >= 0) & (p[..., 1] <= WALL), WALL_FACE, p[..., along], zero, p[..., 1])
            t, p = slope(axis, sign, wall, WALL, LOWER_SLOPE)
            out = sign * (p[..., axis] - wall)
            keep(t, (out >= 0) & (out <= LOWER_DEPTH), LOWER, p[..., along], out, p[..., 1])
            back = wall + sign * LOWER_DEPTH
            low = WALL + LOWER_SLOPE * LOWER_DEPTH
            t, p = plane(axis, back)
            keep(t, (p[..., 1] >= low) & (p[..., 1] <= low + CLUB), CLUB_FACE, p[..., along], zero, p[..., 1] - low)
            t, p = slope(axis, sign, back, low + CLUB, UPPER_SLOPE)
            out = sign * (p[..., axis] - back)
            keep(t, (out >= 0) & (out <= UPPER_DEPTH), UPPER, p[..., along], out, p[..., 1])
            crest = low + CLUB + UPPER_SLOPE * UPPER_DEPTH
            t, p = plane(axis, back + sign * UPPER_DEPTH)
            keep(t, (p[..., 1] >= crest) & (p[..., 1] <= crest + RIM), RIM_FACE, p[..., along], zero, p[..., 1] - crest)
    return hits


def _shade(hits: Hits, colors: Colors, seed: int) -> np.ndarray:
    image = np.empty(hits.kind.shape + (3,))
    image[:] = SKY
    for kind, paint in ((GROUND, _turf), (WALL_FACE, _wall), (CLUB_FACE, _club), (RIM_FACE, _rim)):
        mask = hits.kind == kind
        if mask.any():
            image[mask] = paint(hits.along[mask], hits.out[mask], hits.up[mask], colors, seed)
    for kind, salt, depth in ((LOWER, 0, LOWER_DEPTH), (UPPER, 7, UPPER_DEPTH)):
        mask = hits.kind == kind
        if mask.any():
            image[mask] = _crowd(hits.along[mask], hits.out[mask], colors, seed + salt, depth)
    stands = hits.kind >= WALL_FACE
    image[stands] = _dim(image[stands])
    return image


# The field art's edges in yards: where each side's apparent heights are measured from, as the
# references measure them from the playing surface's corners.
FIELD_FAR, FIELD_LEFT, FIELD_RIGHT = 56.7, -13.3, 113.4
KINDS = ("seats", "concrete", "suites", "ribbon", "open", "apron")
# The fixed camera sees the far stands up to about this apparent height, while a building's design
# rises two or three times higher. Above the wall, the reference's stack is compressed into what
# the camera sees, so the whole design shows: lower bowl, suites, ribbons, upper deck.
SEEN, WALL_TOP = 22.0, 5.0
VENUE_LIGHT, VENUE_SATURATION = 0.86, 0.9


def _reach(venue: dict) -> float:
    """How high the far stands' design rises in the reference before the sky or roof."""
    open_at = next((b["from"] for b in venue["far"] if b["kind"] == "open"), None)
    top = open_at if open_at is not None else max((b["to"] for b in venue["far"]), default=SEEN)
    return min(48.0, max(SEEN, top))


def _apparent(camera, hits: Hits) -> np.ndarray:
    """Each hit's height as it appears above the field's edge on its side, in yards at the edge:
    the measure `venues.py` takes from the references."""
    foot = hits.point.copy()
    foot[..., 1] = 0.0
    foot[hits.side == 0, 2] = FIELD_FAR
    foot[hits.side == 1, 0] = FIELD_LEFT
    foot[hits.side == 2, 0] = FIELD_RIGHT

    def project(q: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        offset = q - camera.position
        depth = offset @ camera.forward
        with np.errstate(divide="ignore", invalid="ignore"):
            return camera.shot.height / 2 - camera.shot.focal * (offset @ camera.up) / depth, camera.shot.focal / depth

    hit_y, _ = project(hits.point)
    foot_y, per_yard = project(foot)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.nan_to_num((foot_y - hit_y) / per_yard)


def _lookup(app: np.ndarray, bands: list[dict]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """For each apparent height: its band's kind, color and how far up the band it is (0..1)."""
    bands = [b for b in bands if b["kind"] != "apron"] or [{"from": 0, "to": 99, "kind": "seats", "color": [90, 90, 96]}]
    tops = np.array([b["to"] for b in bands])
    index = np.clip(np.searchsorted(tops, app, side="right"), 0, len(bands) - 1)
    kinds = np.array([KINDS.index(b["kind"]) for b in bands])[index]
    colors = np.array([b["color"] for b in bands], dtype=np.float64)[index]
    lows = np.array([b["from"] for b in bands])[index]
    spans = np.maximum(0.3, tops[index] - lows)
    return kinds, colors, np.clip((app - lows) / spans, 0, 1)


def _shade_venue(camera, hits: Hits, colors: Colors, seed: int, venue: dict) -> np.ndarray:
    """The stands as the venue's own design: each spot takes the reference band at its apparent
    height on its side, seats filled with the crowd, under night lights."""
    image = np.empty(hits.kind.shape + (3,))
    image[:] = SKY
    ground = hits.kind == GROUND
    if ground.any():
        image[ground] = _turf(hits.along[ground], hits.out[ground], hits.up[ground], colors, seed)
    stands = hits.kind >= WALL_FACE
    if not stands.any():
        return image
    app = _apparent(camera, hits)
    squeeze = (_reach(venue) - WALL_TOP) / (SEEN - WALL_TOP)
    app = np.where(app > WALL_TOP, WALL_TOP + (app - WALL_TOP) * squeeze, app)
    kind = np.full(hits.kind.shape, KINDS.index("open"))
    band_color = np.zeros(hits.kind.shape + (3,))
    share = np.zeros(hits.kind.shape)
    for side, name in enumerate(("far", "left", "right")):
        mask = stands & (hits.side == side)
        if mask.any():
            kind[mask], band_color[mask], share[mask] = _lookup(app[mask], venue[name])
    lit = np.zeros(hits.kind.shape, bool)  # lights keep their glow under the dimming
    sloped = (hits.kind == LOWER) | (hits.kind == UPPER)
    # Seats: the crowd on the seat color, on the bowl's rows; on a face, rows of seat backs.
    seats = stands & (kind == KINDS.index("seats"))
    crowd = seats & sloped
    if crowd.any():
        depth = np.where(hits.kind[crowd] == LOWER, LOWER_DEPTH, UPPER_DEPTH)
        image[crowd] = _crowd(hits.along[crowd], hits.out[crowd], colors, seed, depth, seat=band_color[crowd], sparse=True)
    backs = seats & ~sloped
    if backs.any():
        stripe = ((app[backs] * 2.2) % 1.0 < 0.35)[:, None]
        image[backs] = np.where(stripe, band_color[backs] * 0.7, band_color[backs])
    concrete = stands & (kind == KINDS.index("concrete"))
    if concrete.any():
        noise = (_hash(np.floor(hits.along[concrete] * 2), np.floor(app[concrete] * 3), seed=seed) % np.uint64(9)).astype(float) - 4
        image[concrete] = band_color[concrete] + noise[:, None]
    suites = stands & (kind == KINDS.index("suites"))
    if suites.any():
        # Dark glass with a scattering of lit suites: small panes, some lit, dimmer than a sign.
        along, up = hits.along[suites], share[suites]
        pane = ((along / 1.2) % 1.0 > 0.18) & (up > 0.35) & (up < 0.7)
        on = (_hash(np.floor(along / 1.2), seed=seed + 5) % np.uint64(100)) < 45
        glass = np.maximum(band_color[suites], 18) * 1.2
        image[suites] = np.where((pane & on)[:, None], np.array(WINDOW_LIT, float) * 0.8, glass)
        windows = np.zeros_like(lit)
        windows[suites] = pane & on
        lit |= windows
    ribbon = stands & (kind == KINDS.index("ribbon"))
    if ribbon.any():
        dots = (((hits.along[ribbon] * 6) % 1.0 < 0.5) ^ ((app[ribbon] * 6) % 1.0 < 0.5))[:, None]
        image[ribbon] = np.where(dots, band_color[ribbon], band_color[ribbon] * 0.82)
        lit |= ribbon
    open_ = stands & (kind == KINDS.index("open"))
    if open_.any() and venue.get("indoor"):
        # Under a roof: its dark structure, with the light rigs in rows.
        roof = np.empty((int(open_.sum()), 3))
        roof[:] = (34, 36, 42)
        rigs = ((hits.along[open_] / 3.0) % 1.0 < 0.35) & ((app[open_] * 0.8) % 1.0 < 0.18)
        roof[rigs] = (232, 232, 220)
        image[open_] = roof
        glow = np.zeros_like(lit)
        glow[open_] = rigs
        lit |= glow
        open_ = np.zeros_like(open_)
    if open_.any():
        # Open to the night: the sky, with a city's or a concourse's lights low in it.
        image[open_] = SKY
        lights = (_hash(np.floor(hits.along[open_] * 1.5), np.floor(app[open_] * 2.5), seed=seed + 9) % np.uint64(100)) < np.where(app[open_] < 30, 6, 0)
        glow = np.zeros_like(lit)
        glow[open_] = lights
        image[glow] = WINDOW_LIT
        lit |= open_
    dim = stands & ~lit
    gray = image[dim].mean(axis=-1, keepdims=True)
    image[dim] = (gray + (image[dim] - gray) * VENUE_SATURATION) * VENUE_LIGHT
    return image


def _dim(pixels: np.ndarray) -> np.ndarray:
    gray = pixels.mean(axis=-1, keepdims=True)
    return (gray + (pixels - gray) * STANDS_SATURATION) * STANDS_LIGHT


def _hash(*parts: np.ndarray, seed: int) -> np.ndarray:
    """A stable pseudo-random 32-bit value per integer cell."""
    mask = np.uint64(0xFFFFFFFF)
    h = np.full(parts[0].shape, np.uint64((seed * 2654435761) & 0xFFFFFFFF), dtype=np.uint64)
    for prime, part in zip((73856093, 19349663, 83492791), parts, strict=False):
        h ^= (part.astype(np.int64).astype(np.uint64) * np.uint64(prime)) & mask
        h = (h * np.uint64(2246822519)) & mask
        h ^= h >> np.uint64(13)
    return h


def _pick(h: np.ndarray, shift: int, palette: np.ndarray) -> np.ndarray:
    return palette[((h >> np.uint64(shift)) % np.uint64(len(palette))).astype(np.int64)]


def _second(colors: tuple[RGB, ...]) -> RGB:
    return colors[1] if len(colors) > 1 else colors[0]


def _turf(x: np.ndarray, z: np.ndarray, _up: np.ndarray, colors: Colors, seed: int) -> np.ndarray:
    noise = (_hash(np.floor(x * 2), np.floor(z * 2), seed=seed) % np.uint64(7)).astype(np.float64) - 3
    out = np.array(colors.turf, dtype=np.float64) + noise[:, None]
    bench = (z > 61.5) & (z < 62.6) & (x > TEAM_AREA[0] + 4) & (x < TEAM_AREA[1] - 4) & ((x % 8.0) < 6.5)
    out[bench] = BENCH
    shade = np.clip((z - (FAR_WALL - 1.6)) / 1.6, 0, 1) * 0.3  # the wall's shadow at its foot
    shade = np.maximum(shade, np.clip((LEFT_WALL + 1.6 - x) / 1.6, 0, 1) * 0.3)
    shade = np.maximum(shade, np.clip((x - (RIGHT_WALL - 1.6)) / 1.6, 0, 1) * 0.3)
    return out * (1 - shade)[:, None]


def _wall(along: np.ndarray, _out: np.ndarray, up: np.ndarray, colors: Colors, _seed: int) -> np.ndarray:
    out = np.empty(along.shape + (3,))
    out[:] = np.array(colors.venue[0], dtype=np.float64) * 0.7 + 14
    out[up > WALL - 0.3] = np.array(_second(colors.venue), dtype=np.float64) * 0.9 + 18
    out[(along % 6.0) < 0.1] *= 0.7  # seams between pads
    return out


def _crowd(
    along: np.ndarray,
    out: np.ndarray,
    colors: Colors,
    seed: int,
    depth: float | np.ndarray,
    seat: np.ndarray | None = None,
    sparse: bool = False,
) -> np.ndarray:
    rows, seats = np.floor(out / ROW), np.floor(along / SEAT)
    v, u = (out / ROW) % 1.0, (along / SEAT) % 1.0  # within one seat: v from the riser back
    h = _hash(rows, seats, seed=seed)
    home, away = colors.home, colors.away
    if colors.neutral:
        fans = [home[0]] * 26 + [_second(home)] * 6 + [away[0]] * 26 + [_second(away)] * 6
    else:
        fans = [home[0]] * 52 + [_second(home)] * 16 + [away[0]] * 9
    palette = np.array(fans + list(NEUTRAL) * 4, dtype=np.float64)
    shirt = _pick(h, 8, palette)
    skin = _pick(h, 16, np.array(SKIN, dtype=np.float64))
    seat_color = np.array(colors.venue[0], dtype=np.float64) * 0.5 + 20 if seat is None else seat
    color = np.where((v < 0.18)[:, None], np.array(RISER, float), seat_color)
    # In a venue's own design the seats carry it, so fans are narrower and a few more seats empty.
    empty, side, crown = (22, 0.24, 0.8) if sparse else (EMPTY, 0.12, 0.9)
    person = ((h % np.uint64(100)) >= empty) & (u > side) & (u < 1 - side) & (v >= 0.18)
    color = np.where((person & (v < 0.62))[:, None], shirt, color)
    head = person & (v >= 0.62) & (v < crown) & (u > 0.3) & (u < 0.7)
    color = np.where(head[:, None], skin, color)
    aisle = (seats % AISLE_EVERY) == 0
    color = np.where(aisle[:, None], np.where((v < 0.5)[:, None], np.array(AISLE[0], float), np.array(AISLE[1], float)), color)
    cycle = seats % (2 * AISLE_EVERY)
    portal = (cycle >= 1) & (cycle <= 4) & (rows >= 5) & (rows <= 7)
    color[portal] = (14, 14, 16)
    return color * (1.0 - 0.16 * np.clip(out / depth, 0, 1))[:, None]  # back rows sit under the level above


def _club(along: np.ndarray, _out: np.ndarray, up: np.ndarray, colors: Colors, seed: int) -> np.ndarray:
    out = np.empty(along.shape + (3,))
    out[:] = np.array(colors.venue[0], dtype=np.float64) * 0.4 + 12
    trim = (up <= 0.45) | (up >= CLUB - 0.45)
    out[trim] = np.array(_second(colors.venue), dtype=np.float64) * 0.85 + 16
    # One glazed band of tall panes between thin mullions; a few suites are dark.
    pane = np.floor(along / PANE)
    glass = ((along / PANE) % 1.0 > 0.08) & (up > 0.7) & (up < CLUB - 0.7)
    h = _hash(pane, seed=seed + 3)
    dark = (h % np.uint64(100)) < 12
    glow = 0.82 + 0.18 * ((h >> np.uint64(8)) % np.uint64(100)).astype(np.float64) / 100
    out[glass & ~dark] = np.array(WINDOW_LIT, dtype=np.float64) * glow[glass & ~dark, None]
    out[glass & dark] = WINDOW_DARK
    return out


def _rim(along: np.ndarray, _out: np.ndarray, up: np.ndarray, _colors: Colors, _seed: int) -> np.ndarray:
    out = np.empty(along.shape + (3,))
    out[:] = (30, 32, 38)
    out[((along / 4.0) % 1.0 < 0.5) & (up > RIM * 0.45) & (up < RIM * 0.85)] = (250, 250, 236)
    return out


def field_mask(camera, field_size: tuple[int, int]) -> Image.Image:
    """Where the warped field art covers the frame (L, 255 inside), with the same warp as the field."""
    return camera.warp(Image.new("L", field_size, 255), 0)


def surround(
    camera, field: Image.Image, band: tuple[int, int], colors: Colors, seed: int, venue: dict | None = None
) -> Image.Image:
    """The field art laid on the field as `camera` sees it, inside the stadium, for rows `band`:
    the venue's own design when one is given, otherwise the generic bowl. `camera.ground()` must
    be the warp of `field`; the field's own pixels are kept as they are."""
    box = (0, band[0], camera.shot.width, band[1])
    image = layer(camera, band, colors, seed, venue)
    image.paste(camera.ground().crop(box), (0, 0), field_mask(camera, field.size).crop(box))
    return image
