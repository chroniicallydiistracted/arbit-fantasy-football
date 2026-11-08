// Generates the semantic CSS and the offline page's stylesheet from packages/design-tokens/tokens.json.
import { readFile, writeFile } from 'node:fs/promises';

const root = new URL('../../', import.meta.url);
const tokens = JSON.parse(await readFile(new URL('packages/design-tokens/tokens.json', root), 'utf8'));
const kebab = (name) => name.replace(/[A-Z]/g, (c) => `-${c.toLowerCase()}`);
const block = (values, prefix = '') => Object.entries(values).map(([name, value]) => `  --${prefix}${kebab(name)}: ${value};`).join('\n');
const rem = (px) => `${px / 16}rem`;
const space = Object.fromEntries(tokens.spacingPx.map((px, index) => [index + 1, rem(px)]));
const { typography: type, stripe, motionMs: motion, layout } = tokens;
const stripePattern = `repeating-linear-gradient(90deg, ${stripe.dark} 0 ${stripe.widthRem}rem, ${stripe.light} ${stripe.widthRem}rem ${stripe.widthRem * 2}rem)`;

const css = `/* Generated from packages/design-tokens/tokens.json. Run node scripts/web/tokens.mjs. */
:root {
${block(tokens.color.light)}
${block(tokens.board)}
  --font-display: ${type.display};
  --font-text: ${type.text};
${block(type.scale, 'type-')}
${block(type.tracking, 'tracking-')}
  --line-body: ${type.bodyLineHeight};
  --line-table: ${type.tableLineHeight};
${block(space, 'space-')}
  --gutter: clamp(${rem(tokens.spacingPx[3])}, 3vw, ${rem(tokens.spacingPx[5])});
  --radius: ${tokens.radiusPx}px;
  --content-max: ${layout.maxContentPx}px;
  --rail: ${rem(layout.railPx)};
  --game-tile-width: ${rem(layout.gameTileWidthPx)};
  --tabbar: ${rem(layout.tabBarPx)};
  --motion-fast: ${motion.fast}ms;
  --motion-normal: ${motion.normal}ms;
  --stripes: ${stripePattern};
  --scrim: ${tokens.scrim};
  color-scheme: light;
}
:root[data-theme="dark"] {
${block(tokens.color.dark)}
  color-scheme: dark;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
${block(tokens.color.dark).replace(/^/gm, '  ')}
    color-scheme: dark;
  }
}
`;

const offline = `/* Generated from packages/design-tokens/tokens.json. */
body{margin:0;background:${tokens.board.board};color:${tokens.board.boardInk};font:1rem/1.45 "Liberation Sans",Arial,sans-serif}
.edge{height:.25rem;background:${stripePattern}}
main{padding:clamp(1.5rem,8vw,4rem);max-width:36rem}
h1{font:800 3.5rem/1 "Arial Narrow","Liberation Sans Narrow",sans-serif;text-transform:uppercase;margin:0 0 1rem}
p{color:${tokens.board.boardMuted};margin:0 0 1.5rem}
a{display:inline-block;background:${tokens.board.boardFlag};color:${tokens.color.light.onFlag};font-weight:600;padding:.75rem 1.25rem;text-decoration:none}
`;

const targets = [
  [new URL('apps/web/src/tokens.css', root), css],
  [new URL('apps/web/public/offline.css', root), offline],
];
for (const [destination, content] of targets) {
  if (process.argv.includes('--check')) {
    if ((await readFile(destination, 'utf8')) !== content) throw new Error(`${destination.pathname} is stale. Run node scripts/web/tokens.mjs.`);
  } else await writeFile(destination, content);
}
