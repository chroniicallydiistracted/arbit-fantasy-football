"""Review sheet for one batch: raw output, then classified frames in Arizona and Green Bay colours."""
import json, sys
from pathlib import Path
from PIL import Image, ImageDraw
sys.path.insert(0, str(Path(__file__).parent))
import convert as V
from assemble import REF_CLASSES, manual
name = sys.argv[1]
jobs = json.load(open('gen/jobs.json'))[name]; spec = json.load(open(f'batches/{name}.json')); size = spec['size']
ref = Image.open(f"key/{jobs['ref']}-key2{'-56' if size == 56 else ''}.png").convert('RGBA')
BG = (92, 104, 92, 255); n = len(spec['frames']) + 1
sheet = Image.new('RGBA', (size * n, size * 3), BG)
sheet.alpha_composite(ref, (0, 0))
for i, (label, _) in enumerate(spec['frames']):
    raw = Image.open(f'gen/{name}/{i + 1}.png').convert('RGBA'); sheet.alpha_composite(raw, (size * (i + 1), 0))
    kps = spec['frames'][i][1]; hands = [(k['x'] * size, k['y'] * size) for k in kps if k['label'] in ('RIGHT ARM', 'LEFT ARM')]
    g, d = V.to_grid_with_ball(f'gen/{name}/{i + 1}.png', set(REF_CLASSES[jobs['ref']]), hands, size); g = V.clean(V.strip_ball(manual(label, V.clean(g, d))), d)
    print(label, 'ball pixels', int(((g == 'B') | (g == 'C')).sum()))
    sheet.alpha_composite(V.render(g, 0), (size * (i + 1), size)); sheet.alpha_composite(V.render(g, 11 + 32), (size * (i + 1), size * 2))
big = sheet.resize((sheet.width * 4, sheet.height * 4), Image.NEAREST); d = ImageDraw.Draw(big)
for i, (label, _) in enumerate(spec['frames']): d.text((size * 4 * (i + 1) + 4, 4), label, fill=(255, 255, 255))
big.save(f'gen/{name}-review.png')
