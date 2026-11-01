import { spawnSync } from 'node:child_process';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
const root = new URL('../../', import.meta.url).pathname;
const temporary = await mkdtemp(join(tmpdir(), 'arbit-contract-'));
function execute(program, args) {
  const result = spawnSync(program, args, { cwd: root, encoding: 'utf8' });
  if (result.status !== 0) throw new Error(`${program} failed: ${result.stderr || result.stdout}`);
  return result.stdout;
}
try {
  const actual = execute('uv', ['run', 'python', '-c', 'from scripts.export_openapi import export; print(export(), end="")']);
  if (actual !== await readFile(join(root, 'packages/contracts/openapi.json'), 'utf8')) throw new Error('OpenAPI is stale. Run uv run python scripts/export_openapi.py, then pnpm generate:client.');
  execute('pnpm', ['exec', 'openapi-typescript', 'packages/contracts/openapi.json', '-o', join(temporary, 'api.ts')]);
  if (await readFile(join(temporary, 'api.ts'), 'utf8') !== await readFile(join(root, 'apps/web/src/generated/api.ts'), 'utf8')) throw new Error('TypeScript contract is stale. Run pnpm generate:client.');
  execute('node', ['scripts/web/tokens.mjs', '--check']);
  console.log('OpenAPI and generated TypeScript are current.');
} finally { await rm(temporary, { recursive: true }); }
