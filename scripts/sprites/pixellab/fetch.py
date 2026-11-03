"""Wait for a PixelLab job and download every frame. Usage: fetch.py JOB_ID OUTDIR COUNT"""
import json, sys, time, urllib.request, urllib.error
from pathlib import Path
cfg = json.load(open('/home/andre/.claude.json'))
AUTH = cfg['projects']['/home/andre/arbit-fantasy-football']['mcpServers']['pixellab']['headers']['Authorization']
job, out, count = sys.argv[1], Path(sys.argv[2]), int(sys.argv[3])
out.mkdir(parents=True, exist_ok=True)
deadline = time.time() + 600
for i in range(count):
    while True:
        try:
            req = urllib.request.Request(f'https://api.pixellab.ai/mcp/images/{job}/download?index={i}', headers={'Authorization': AUTH})
            with urllib.request.urlopen(req, timeout=60) as r: (out / f'{i + 1}.png').write_bytes(r.read()); break
        except urllib.error.HTTPError as e:
            if e.code != 423 or time.time() > deadline: print('HTTP', e.code, 'frame', i); raise SystemExit(1)
            time.sleep(int(e.headers.get('Retry-After') or 10))
print('downloaded', count, 'to', out)
