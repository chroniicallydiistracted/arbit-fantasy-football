"""Run pose batches one after another (the trial allows one job at a time) and download each result."""
import base64, json, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import mcp
from submit import LOOK
jobs_path = Path('gen/jobs.json')
def submit(name):
    b = json.load(open(f'batches/{name}.json'))
    ref = f"key/{b['ref']}-key2{'-56' if b['size'] == 56 else ''}.png"
    for attempt in range(60):
        res = mcp.call('animate_with_skeleton_v3', {
            'description': LOOK, 'action': b['action'], 'direction': 'east', 'view': 'side', 'no_background': True, 'seed': 7,
            'first_frame_base64': base64.b64encode(open(ref, 'rb').read()).decode(),
            'first_frame_keypoints': b['first'], 'keypoints': [k for _, k in b['frames']]})
        text = ''.join(c.get('text', '') for c in res.get('result', {}).get('content', []))
        if 'job_id: ' in text:
            jobs = json.loads(jobs_path.read_text()) if jobs_path.exists() else {}
            jobs[name] = {'job': text.split('job_id: ')[1].split()[0], 'frames': [n for n, _ in b['frames']], 'ref': b['ref'], 'size': b['size']}
            jobs_path.write_text(json.dumps(jobs, indent=1)); return jobs[name]
        print(name, 'waiting for a free slot', flush=True); time.sleep(20)
    raise SystemExit(f'{name}: no slot after 20 minutes')
for name in sys.argv[1:]:
    jobs = json.loads(jobs_path.read_text()) if jobs_path.exists() else {}
    job = jobs.get(name) or submit(name)
    print(name, 'job', job['job'], flush=True)
    subprocess.run([sys.executable, '-I', str(Path(__file__).parent / 'fetch.py'), job['job'], f'gen/{name}', str(len(job['frames']))], check=True)
print('ALL DONE', flush=True)
