"""Stick-figure sheet for a batch: the reference sprite with its skeleton, then every pose."""
import json, sys
from pathlib import Path
from PIL import Image, ImageDraw
BONES = [('NECK','RIGHT SHOULDER'),('RIGHT SHOULDER','RIGHT ELBOW'),('RIGHT ELBOW','RIGHT ARM'),('NECK','LEFT SHOULDER'),('LEFT SHOULDER','LEFT ELBOW'),('LEFT ELBOW','LEFT ARM'),
         ('NECK','RIGHT HIP'),('RIGHT HIP','RIGHT KNEE'),('RIGHT KNEE','RIGHT LEG'),('NECK','LEFT HIP'),('LEFT HIP','LEFT KNEE'),('LEFT KNEE','LEFT LEG'),('NECK','NOSE')]
def tile(size, sprite, kps, label, scale=6):
    im = Image.new('RGBA', (size, size), (92, 104, 92, 255))
    if sprite: im.alpha_composite(sprite)
    im = im.resize((size * scale, size * scale), Image.NEAREST); d = ImageDraw.Draw(im)
    p = {k['label']: (k['x'] * size * scale, k['y'] * size * scale) for k in kps}
    for a, b in BONES: d.line([p[a], p[b]], fill=(255, 220, 0) if 'RIGHT' in a + b else (0, 200, 255), width=3)
    x, y = p['NOSE']; d.ellipse([x - 4, y - 4, x + 4, y + 4], fill=(255, 255, 255))
    d.line([(0, (size - 4) * scale), (size * scale, (size - 4) * scale)], fill=(30, 30, 30), width=2)
    d.text((6, 6), label, fill=(255, 255, 255))
    return im
if __name__ == '__main__':
    b = json.load(open(sys.argv[1])); size = b['size']
    sprite = Image.open(sys.argv[2]).convert('RGBA')
    tiles = [tile(size, sprite, b['first'], b['ref'])] + [tile(size, None, k, n) for n, k in b['frames']]
    sheet = Image.new('RGBA', (sum(t.width for t in tiles), tiles[0].height))
    x = 0
    for t in tiles: sheet.paste(t, (x, 0)); x += t.width
    sheet.save(sys.argv[3])
