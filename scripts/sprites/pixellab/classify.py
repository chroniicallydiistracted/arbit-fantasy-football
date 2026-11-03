"""Map a generated frame drawn in the key set back to colour classes, and report what did not fit."""
import json, sys
from pathlib import Path
import numpy as np
from PIL import Image
PAL = json.load(open('/home/andre/arbit-fantasy-football/assets/sprites/palette.json'))
KEYPAL = json.load(open(Path(__file__).resolve().parent / 'key-palette.json'))
CLASSES = list(KEYPAL)
COLS = np.array([KEYPAL[c] for c in CLASSES], float)
def classify(path, limit=40):
    a = np.array(Image.open(path).convert('RGBA')).astype(float)
    alpha = a[..., 3] > 127
    d = np.sqrt(((a[..., None, :3] - COLS[None, None]) ** 2).sum(-1))
    idx, dist = d.argmin(-1), d.min(-1)
    grid = np.full(alpha.shape, '.', dtype='<U1')
    ok = alpha & (dist <= limit)
    grid[ok] = np.array(CLASSES)[idx[ok]]
    exact = int((alpha & (dist == 0)).sum()); near = int((alpha & (dist > 0) & (dist <= limit)).sum()); off = int((alpha & (dist > limit)).sum())
    return grid, {'pixels': int(alpha.sum()), 'exact': exact, 'near': near, 'off': off, 'partial_alpha': int(((a[..., 3] > 0) & (a[..., 3] < 255)).sum())}
if __name__ == '__main__':
    for p in sys.argv[1:]:
        g, s = classify(p); print(Path(p).name, s)
