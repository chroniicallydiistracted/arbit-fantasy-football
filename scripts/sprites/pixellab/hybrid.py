"""Approved Arizona-coloured frames + class labels from a key-palette redraw of the same poses and seed.
Unambiguous Arizona colours give their class directly; black and white take the redraw's class nearby."""
import sys
from collections import Counter
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0, str(Path(__file__).parent))
import convert as V
def hybrid(approved_path, key_grid, allowed):
    a = np.array(Image.open(approved_path).convert('RGBA'))
    inv = {}
    for c in allowed: inv.setdefault(tuple(V.PAL[c][0]), []).append(c)
    g = np.full(a.shape[:2], '.', '<U1'); stats = Counter()
    H, W = g.shape
    for y, x in zip(*np.nonzero(a[..., 3] > 127)):
        cands = inv.get(tuple(int(v) for v in a[y, x, :3]))
        if not cands:
            col = a[y, x, :3].astype(float)
            cands = [min(allowed, key=lambda c: np.linalg.norm(col - np.array(V.PAL[c][0])))]
            stats['off'] += 1
        if len(cands) == 1:
            g[y, x] = cands[0]; stats['direct'] += 1; continue
        votes = Counter()
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                ny, nx = y + dy, x + dx
                if 0 <= ny < H and 0 <= nx < W and key_grid[ny, nx] in cands:
                    votes[key_grid[ny, nx]] += 3 if (dy, dx) == (0, 0) else 1
        if votes:
            g[y, x] = votes.most_common(1)[0][0]; stats['from redraw'] += 1
        else:
            g[y, x] = '#' if '#' in cands else cands[0]; stats['default'] += 1
    return g, stats
