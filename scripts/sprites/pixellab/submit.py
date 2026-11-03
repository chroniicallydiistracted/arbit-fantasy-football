"""Submit pose batches to PixelLab's skeleton animator in the key palette. Records job ids in gen/jobs.json."""
import base64, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import mcp
LOOK = 'retro 16-bit american football player: white helmet with blue stripe, red jersey with dark trim and number, grey pants, red socks, black shoes, brown skin'
if __name__ == '__main__':
    jobs_path = Path('gen/jobs.json'); jobs = json.loads(jobs_path.read_text()) if jobs_path.exists() else {}
    for name in sys.argv[1:]:
        b = json.load(open(f'batches/{name}.json'))
        ref = f"key/{b['ref']}-key2{'-56' if b['size'] == 56 else ''}.png"
        res = mcp.call('animate_with_skeleton_v3', {
            'description': LOOK, 'action': b['action'], 'direction': 'east', 'view': 'side', 'no_background': True, 'seed': 7,
            'first_frame_base64': base64.b64encode(open(ref, 'rb').read()).decode(),
            'first_frame_keypoints': b['first'], 'keypoints': [k for _, k in b['frames']]})
        if 'error' in res or res['result'].get('isError'): print('FAILED', name); continue
        text = ''.join(c.get('text', '') for c in res['result']['content'])
        jobs[name] = {'job': text.split('job_id: ')[1].split()[0], 'frames': [n for n, _ in b['frames']], 'ref': b['ref'], 'size': b['size']}
        jobs_path.write_text(json.dumps(jobs, indent=1))
