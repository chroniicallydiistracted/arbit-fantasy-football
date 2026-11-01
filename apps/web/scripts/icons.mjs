// Build-only conversion of the original vector mark. No generated binaries in Git.
import { Resvg } from '@resvg/resvg-js';
import { readFile, writeFile } from 'node:fs/promises';
const svg = await readFile(new URL('../public/mark.svg', import.meta.url), 'utf8');
for (const size of [192, 512]) {
  const png = new Resvg(svg, { fitTo: { mode: 'width', value: size }, font: { loadSystemFonts: false } }).render().asPng();
  await writeFile(new URL(`../public/icon-${size}.png`, import.meta.url), png);
}
