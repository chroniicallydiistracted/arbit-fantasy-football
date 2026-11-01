import { readFile, writeFile } from 'node:fs/promises';
const root = new URL('../../', import.meta.url);
const tokens = JSON.parse(await readFile(new URL('packages/design-tokens/tokens.json', root), 'utf8'));
const roles = value => Object.entries(value).map(([name, color]) => `  --${name.replace(/[A-Z]/g, c => `-${c.toLowerCase()}`)}: ${color};`).join('\n');
const css = `/* Generated from packages/design-tokens/tokens.json. */\n:root {\n${roles(tokens.color.light)}\n  --font-body: ${tokens.typography.sans};\n  --font-display: ${tokens.typography.display};\n}\n:root[data-theme="dark"] {\n${roles(tokens.color.dark)}\n  color-scheme: dark;\n}\n@media (prefers-color-scheme: dark) {\n  :root:not([data-theme="light"]) {\n${roles(tokens.color.dark)}\n    color-scheme: dark;\n  }\n}\n`;
const destination = new URL('apps/web/src/tokens.css', root);
if (process.argv.includes('--check')) {
  if (await readFile(destination, 'utf8') !== css) throw new Error('Semantic CSS is stale. Run node scripts/web/tokens.mjs.');
} else await writeFile(destination, css);
