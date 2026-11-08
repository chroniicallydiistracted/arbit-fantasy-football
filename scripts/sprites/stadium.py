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


def layer(camera, band: tuple[int, int], colors: Colors, seed: int) -> Image.Image:
    """The stadium as `camera` sees it, for frame rows `band` (an RGB image)."""
    top, bottom = band
    width = camera.shot.width
    out = np.zeros((bottom - top, width, 3), dtype=np.float64)
    step = 24
    for row in range(top, bottom, step):
        rows = min(step, bottom - row)
        sub = (np.arange(rows * SAMPLES) + 0.5) / SAMPLES + row
        cols = (np.arange(width * SAMPLES) + 0.5) / SAMPLES
        ys, xs = np.meshgrid(sub, cols, indexing="ij")
        color = _shade(_trace(camera, xs, ys), colors, seed)
        color = color.reshape(rows, SAMPLES, width, SAMPLES, 3).mean(axis=(1, 3))
        out[row - top : row - top + rows] = color
    return Image.fromarray(np.clip(np.rint(out), 0, 255).astype(np.uint8))


@dataclass
class Hits:
    kind: np.ndarray  # which surface: 0 sky, else GROUND .. RIM_FACE
    along: np.ndarray  # yards along the surface's own row direction (x for ground)
    out: np.ndarray  # yards out from the wall line (z for ground)
    up: np.ndarray  # yards up the face, for walls, club level and rim


def _trace(camera, xs: np.ndarray, ys: np.ndarray) -> Hits:
    shot = camera.shot
    a = (xs - shot.width / 2) / shot.focal
    b = -(ys - shot.height / 2) / shot.focal
    f, r, u = camera.forward, camera.right, camera.up
    d = np.stack([f[i] + a * r[i] + b * u[i] for i in range(3)], axis=-1)
    c = camera.position
    nearest = np.full(a.shape, np.inf)
    hits = Hits(np.zeros(a.shape, np.int8), np.zeros(a.shape), np.zeros(a.shape), np.zeros(a.shape))

    def keep(t: np.ndarray, valid: np.ndarray, kind: int, along: np.ndarray, out: np.ndarray, up: np.ndarray) -> None:
        closer = valid & (t > 0) & (t < nearest)
        nearest[closer] = t[closer]
        hits.kind[closer] = kind
        hits.along[closer] = along[closer]
        hits.out[closer] = out[closer]
        hits.up[closer] = up[closer]

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
        for axis, along, sign, wall in ((2, 0, +1, FAR_WALL), (0, 2, -1, LEFT_WALL), (0, 2, +1, RIGHT_WALL)):
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


def _crowd(along: np.ndarray, out: np.ndarray, colors: Colors, seed: int, depth: float) -> np.ndarray:
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
    seat_color = np.array(colors.venue[0], dtype=np.float64) * 0.5 + 20
    color = np.where((v < 0.18)[:, None], np.array(RISER, float), seat_color)
    person = ((h % np.uint64(100)) >= EMPTY) & (u > 0.12) & (u < 0.88) & (v >= 0.18)
    color = np.where((person & (v < 0.64))[:, None], shirt, color)
    head = person & (v >= 0.64) & (v < 0.9) & (u > 0.26) & (u < 0.74)
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


def surround(camera, field: Image.Image, band: tuple[int, int], colors: Colors, seed: int) -> Image.Image:
    """The field art laid on the field as `camera` sees it, inside the stadium, for rows `band`.
    `camera.ground()` must be the warp of `field`; the field's own pixels are kept as they are."""
    box = (0, band[0], camera.shot.width, band[1])
    image = layer(camera, band, colors, seed)
    image.paste(camera.ground().crop(box), (0, 0), field_mask(camera, field.size).crop(box))
    return image
