"""Generated key-palette frames -> class grids -> any team colours. Shared by every batch."""
import json, sys
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0, '/home/andre/arbit-fantasy-football/scripts/sprites')
import frames as F
HERE = Path(__file__).resolve().parent
KEY = json.load(open(HERE / 'key-palette.json'))
PAL = F.palette()
GREY_SMEAR_CLASSES = ('l', 'm')
def to_grid(path, allowed):
    """Nearest class among those the reference frame uses. Returns grid and the distance of each pixel."""
    allowed = sorted(allowed)
    cols = np.array([KEY[c] for c in allowed], float)
    a = np.array(Image.open(path).convert('RGBA')).astype(float)
    alpha = a[..., 3] > 127
    d = np.sqrt(((a[..., None, :3] - cols[None, None]) ** 2).sum(-1))
    k, dist = d.argmin(-1), d.min(-1)
    g = np.full(alpha.shape, '.', '<U1'); g[alpha] = np.array(allowed)[k[alpha]]
    return g, np.where(alpha, dist, 0)
def components(mask):
    H, W = mask.shape; seen = np.zeros_like(mask); out = []
    for y in range(H):
        for x in range(W):
            if mask[y, x] and not seen[y, x]:
                st, comp = [(y, x)], []; seen[y, x] = True
                while st:
                    cy, cx = st.pop(); comp.append((cy, cx))
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            ny, nx = cy + dy, cx + dx
                            if 0 <= ny < H and 0 <= nx < W and mask[ny, nx] and not seen[ny, nx]: seen[ny, nx] = True; st.append((ny, nx))
                out.append(comp)
    return out
def clean(g, dist, streaks=False):
    """Drop smears: grey-class patches of 7+ pixels in the lower 60% that the model drew far from any key colour,
    detached specks, and pixels touching nothing (the frame checker rejects those)."""
    g = g.copy(); H = g.shape[0]
    filled = np.nonzero((g != '.').any(1))[0]; top, bottom = filled.min(), filled.max()
    for comp in components(np.isin(g, GREY_SMEAR_CLASSES)):
        ys = [c[0] for c in comp]
        offish = np.mean([dist[c] > 25 for c in comp])
        if len(comp) >= 7 and (min(ys) - top) / max(1, bottom - top) > 0.4 and offish > 0.5:
            for c in comp: g[c] = '.'
    if streaks:
        # Motion streaks: light grey strokes with no outline around them. Real pants and helmets sit inside '#'.
        grey = np.isin(g, ('j', 'n', 'b', 'a', 'p', 'l', 'm'))
        for comp in components(grey):
            touching = 0
            for cy, cx in comp:
                near = [g[cy + dy, cx + dx] for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)) if 0 <= cy + dy < H and 0 <= cx + dx < g.shape[1]]
                touching += any(c != '.' and c not in ('j', 'n', 'b', 'a', 'p', 'l', 'm') for c in near)
            members = set(comp)
            thick = sum(sum((cy + dy, cx + dx) in members for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1))) >= 3 for cy, cx in comp)
            if len(comp) >= 3 and touching / len(comp) < 0.3 and thick / len(comp) < 0.1:
                for c in comp: g[c] = '.'
    body = components(g != '.')
    if body:
        biggest = max(len(c) for c in body)
        for comp in body:
            if len(comp) < 12 and len(comp) < biggest:
                for c in comp: g[c] = '.'
    changed = True
    while changed:
        changed = False
        for y, x in zip(*np.nonzero(g != '.')):
            if all(not (0 <= y + dy < H and 0 <= x + dx < g.shape[1]) or g[y + dy, x + dx] == '.' for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                g[y, x] = '.'; changed = True
    return g
def crop(g):
    ys, xs = np.nonzero(g != '.')
    return g[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
def rows(g):
    return [''.join(r).rstrip('.') or '.' for r in crop(g)]
def render(g, s):
    out = np.zeros((*g.shape, 4), np.uint8)
    for y, x in zip(*np.nonzero(g != '.')): out[y, x, :3] = PAL[g[y, x]][s]; out[y, x, 3] = 255
    return Image.fromarray(out)


def to_grid_with_ball(path, allowed, hands, size, radius=4.5):
    """Like to_grid, but ball colours count only within a few pixels of a hand; elsewhere they are skin."""
    plain, dist = to_grid(path, allowed)
    with_ball, dist_b = to_grid(path, set(allowed) | {'B', 'C'})
    g = plain.copy()
    for y, x in zip(*np.nonzero(np.isin(with_ball, ('B', 'C')))):
        if any((x - hx) ** 2 + (y - hy) ** 2 <= radius ** 2 for hx, hy in hands):
            g[y, x] = with_ball[y, x]; dist[y, x] = dist_b[y, x]
    # The model sometimes draws the ball in the jersey's darkest red: a block by a hand touching no other jersey colour.
    for comp in components(g == 'h'):
        cy = sum(c[0] for c in comp) / len(comp); cx = sum(c[1] for c in comp) / len(comp)
        touches_jersey = any(g[y + dy, x + dx] in 'ecf' for y, x in comp for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1))
                             if 0 <= y + dy < g.shape[0] and 0 <= x + dx < g.shape[1])
        if 6 <= len(comp) <= 20 and not touches_jersey and any((cx - hx) ** 2 + (cy - hy) ** 2 <= 6.5 ** 2 for hx, hy in hands):
            top = min(c[0] for c in comp)
            for y, x in comp: g[y, x] = 'B' if y == top else 'C'
    return g, dist


def strip_ball(g):
    """Poses ship without a ball; the renderer draws one ball sprite at the hand. Ball pixels inside the body
    take the commonest neighbouring class; ones sticking out of the body become empty."""
    g = g.copy(); H, W = g.shape
    hole = set(zip(*np.nonzero(np.isin(g, ('B', 'C')))))
    for y, x in hole: g[y, x] = '.'
    for _ in range(4):
        filled = {}
        for y, x in hole:
            around = [g[y + dy, x + dx] for dy in (-1, 0, 1) for dx in (-1, 0, 1) if (dy or dx) and 0 <= y + dy < H and 0 <= x + dx < W]
            body = [c for c in around if c != '.' and (c != '#' or around.count('#') > 4)]
            if len(body) >= 5:
                filled[(y, x)] = max(set(body), key=body.count)
        for (y, x), c in filled.items(): g[y, x] = c
        hole -= set(filled)
        if not filled: break
    return g
