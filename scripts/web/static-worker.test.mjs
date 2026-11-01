import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, writeFile, readFile, mkdir, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { runInNewContext } from 'node:vm';
import { writeStaticWorker } from './static-worker.mjs';

test('PWA never intercepts private APIs, auth, events, exports or arbitrary runtime content', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'arbit-worker-'));
  try {
    await mkdir(join(dir, 'assets'));
    await writeFile(join(dir, 'assets/app-abc.js'), 'app');
    await writeFile(join(dir, 'offline.html'), 'safe shell');
    await writeFile(join(dir, 'index.html'), 'online app');
    const { version } = await writeStaticWorker(dir);
    const events = {};
    let requests = 0;
    runInNewContext(await readFile(join(dir, 'sw.js'), 'utf8'), {
      self: { location: { origin: 'https://arbit.example' }, addEventListener: (name, callback) => { events[name] = callback; } },
      URL, Set, fetch: () => { requests++; },
    });
    for (const path of ['/api/v1/me', '/api/v1/players/private', '/auth/callback?code=secret', '/internal/league/current', '/exports/roster', '/events/live', '/arbitrary.json', '/assets/app-abc.js?token=secret']) {
      let intercepted = false;
      events.fetch({ request: { method: 'GET', url: `https://arbit.example${path}`, mode: 'cors' }, respondWith: () => { intercepted = true; } });
      assert.equal(intercepted, false, path);
    }
    assert.equal(requests, 0);
    await writeFile(join(dir, 'assets/app-abc.js'), 'new app');
    assert.notEqual((await writeStaticWorker(dir)).version, version, 'static changes must create a distinct update');
  } finally { await rm(dir, { recursive: true }); }
});
