// Mechanical design rules from docs/design/design-system.md. Originality still needs human review;
// this only stops the system silently eroding back to one-off values and generated copy.
import { readdir, readFile } from 'node:fs/promises';
import { join } from 'node:path';

const root = new URL('../../', import.meta.url).pathname;
const web = join(root, 'apps/web');

// Generic defaults of generated interfaces. Arbit's faces are declared in tokens.json.
const BANNED_FONTS = /\b(Inter|Space Grotesk|Instrument (Sans|Serif)|Newsreader|Fraunces|Playfair|DM (Sans|Serif)|Poppins|Geist|Manrope|Sora|Outfit|Plus Jakarta|Bricolage|Lora|Merriweather)\b/;
// Slogans and taglines removed in the reset. Interface text states facts; it does not sell.
const BANNED_COPY = [
  /seat in the/i, /your seat/i, /considered view/i, /insight follows/i, /facts first/i, /in perspective/i,
  /built for the/i, /to come\b/i, /fuller picture/i, /private by design/i, /welcome back/i, /you.re invited/i,
  /let.s get you/i, /feels right/i, /shortlist/i, /keep an eye/i, /team sheet/i, /around the ffa/i, /clearer view/i,
  /members only/i, /your league\./i, /your front office/i, /warm paper/i, /evening green/i, /supercharge/i,
  /unlock\b/i, /effortless/i, /seamless/i, /elevate/i, /at a glance/i, /powered by/i,
];
const SPACE_PROPS = /^(margin|padding|gap|row-gap|column-gap)(-(top|right|bottom|left|inline|block)(-(start|end))?)?$/;
const SPACE_ALLOWED = /^(0|auto|inherit|unset|-?var\(--space-[1-8]\)|var\(--gutter\)|var\(--[a-z-]+\))$/;

const errors = [];
const fail = (file, line, message) => errors.push(`${file}:${line}: ${message}`);

// Top-level space-separated parts; a math function counts as one part and may hold tokens inside.
function parts(value) {
  const result = [];
  let depth = 0;
  let current = '';
  for (const char of value) {
    if (char === '(') depth += 1;
    if (char === ')') depth -= 1;
    if (char === ' ' && depth === 0) {
      if (current) result.push(current);
      current = '';
    } else current += char;
  }
  if (current) result.push(current);
  return result;
}

async function lintStyles(file) {
  const text = await readFile(join(web, file), 'utf8');
  text.split('\n').forEach((raw, index) => {
    const line = raw.replace(/\/\*.*?\*\//g, '');
    const at = index + 1;
    if (/#[0-9a-fA-F]{3,8}\b/.test(line)) fail(file, at, 'raw hex color; use a token');
    if (/\b(rgb|rgba|hsl|hsla|oklch)\(/.test(line)) fail(file, at, 'raw color function; use a token');
    if (/font-style:\s*italic/.test(line)) fail(file, at, 'italics are not part of the type system');
    if (BANNED_FONTS.test(line)) fail(file, at, 'banned generic font');
    const declaration = /^\s*([a-z-]+):\s*(.+?);?\s*$/.exec(line);
    if (!declaration) return;
    const [, property, value] = declaration;
    if (property === 'font-size' && !/^(var\(--type-[a-z0-9-]+\)|inherit)$/.test(value)) fail(file, at, `font-size must use a --type token, found ${value}`);
    if (property === 'font-family' && !/^(var\(--font-[a-z]+\)|inherit)$/.test(value)) fail(file, at, 'font-family must use a --font token');
    if (property === 'letter-spacing' && !/^(0|normal|var\(--tracking-[a-z]+\))$/.test(value)) fail(file, at, 'letter-spacing must use a --tracking token');
    if (property === 'border-radius' && !/^(0|var\(--radius\))$/.test(value)) fail(file, at, 'corners are square or --radius');
    if (property === 'box-shadow' && value !== 'none') fail(file, at, 'no drop shadows; separation comes from rules and boards');
    if (SPACE_PROPS.test(property)) {
      for (const part of parts(value)) {
        if (/^(calc|max|min|clamp|env)\(/.test(part)) {
          if (/\d(px|rem|em)\b/.test(part.replace(/var\([^()]*\)/g, ''))) fail(file, at, `${property} math must use tokens, found ${part}`);
        } else if (!SPACE_ALLOWED.test(part)) fail(file, at, `${property} must use --space tokens, found ${part}`);
      }
    }
  });
}

async function lintCopy(file) {
  const text = await readFile(join(web, file), 'utf8');
  if (BANNED_FONTS.test(text)) fail(file, 1, 'banned generic font');
  text.split('\n').forEach((line, index) => {
    for (const pattern of BANNED_COPY) if (pattern.test(line)) fail(file, index + 1, `banned copy ${pattern}`);
    if (/<em\b/.test(line)) fail(file, index + 1, 'emphasis styling is not a heading device');
  });
}

await lintStyles('src/styles.css');
const sources = (await readdir(join(web, 'src'))).filter((name) => name.endsWith('.tsx') && !name.endsWith('.test.tsx'));
for (const name of sources) await lintCopy(join('src', name));
for (const name of ['public/offline.html', 'public/manifest.webmanifest', 'index.html']) await lintCopy(name);

if (errors.length) {
  console.error(`${errors.length} design rule violation(s):\n${errors.slice(0, 60).join('\n')}`);
  if (errors.length > 60) console.error(`...and ${errors.length - 60} more`);
  process.exit(1);
}
console.log('Design rules pass.');
