// The stadium board (slice 5, ENG-039, ENG-040), drawn as scripts/sprites/board.py draws it for the
// review clips: LED dots three screen pixels apart, our own glyphs, team logos in the same dots,
// results scrolling in from their team's side in the game's signal colors, and the clock running
// from the snap to the whistle when the play's end clock is known. Colors here are the board's own
// LED art, not interface styling.
import glyphText from "../../../../assets/sprites/board/glyphs.txt?raw";
import type { components } from "../generated/api";

type Board = components["schemas"]["PlayBoard"];
type State = components["schemas"]["BoardState"];
type Side = components["schemas"]["BoardSide"];
type Result = components["schemas"]["BoardResult"];
type RGB = [number, number, number];

export const DOT = 3;
export const WIDTH = 256;
export const HEIGHT = 43;
const HOUSING = 3;
const LOGO = 30;
const CARD_SECONDS = 2.0;
const CARD_DELAY = 0.3;
const SCROLL_SECONDS = 0.6;
const SETTLE = 0.5;
const HOLD_AFTER = 1.2;
const SNAP = 0.6;

const WHITE: RGB = [238, 238, 228];
const DIM: RGB = [150, 152, 146];
const YELLOW: RGB = [250, 215, 40];
const BLUE: RGB = [96, 156, 255];
const BALL: RGB = [176, 98, 36];
const TONES: Record<string, RGB> = {
  good: [95, 216, 146],
  bad: [255, 138, 145],
  flag: [255, 198, 0],
};
const UNLIT: RGB = [24, 26, 28];
const UNLIT_PIP: RGB = [58, 60, 58];
const GAP: RGB = [9, 10, 11];
const HOUSING_COLOR: RGB = [40, 44, 48];
const HOUSING_EDGE: RGB = [62, 67, 72];
export const STRUT = "rgb(30,33,36)";
const ORDINALS: Record<number, string> = { 1: "1ST", 2: "2ND", 3: "3RD", 4: "4TH" };

function loadGlyphs(text: string): Record<string, string[]> {
  const glyphs: Record<string, string[]> = {};
  for (const chunk of text.split(/^== /m)) {
    if (!chunk.trim() || chunk.startsWith("#")) continue;
    const [name, ...rows] = chunk.split("\n").filter((line) => line.length > 0);
    glyphs[name === "space" ? " " : name === "hash" ? "#" : name] = rows;
  }
  return glyphs;
}
const GLYPHS = loadGlyphs(glyphText);

function textWidth(text: string, scale = 1) {
  const widths = [...text].map((c) => GLYPHS[c]?.[0].length ?? 3);
  return (widths.reduce((a, b) => a + b, 0) + Math.max(0, widths.length - 1)) * scale;
}

class Canvas {
  lit = new Map<string, RGB>();
  text(text: string, x: number, y: number, color: RGB, scale = 1) {
    for (const char of text) {
      const rows = GLYPHS[char] ?? GLYPHS[" "];
      rows.forEach((line, row) => {
        [...line].forEach((cell, column) => {
          if (cell !== "#") return;
          for (let dy = 0; dy < scale; dy += 1)
            for (let dx = 0; dx < scale; dx += 1)
              this.lit.set(`${x + column * scale + dx},${y + row * scale + dy}`, color);
        });
      });
      x += (rows[0].length + 1) * scale;
    }
  }
  centered(text: string, middle: number, y: number, color: RGB, scale = 1) {
    this.text(text, middle - Math.floor(textWidth(text, scale) / 2), y, color, scale);
  }
  icon(name: string, x: number, y: number, color: RGB) {
    GLYPHS[name]?.forEach((line, row) => {
      [...line].forEach((cell, column) => {
        if (cell === "#") this.lit.set(`${x + column},${y + row}`, color);
      });
    });
  }
  dots(dots: number[][], x: number, y: number) {
    for (const [dx, dy, r, g, b] of dots) this.lit.set(`${x + dx},${y + dy}`, [r, g, b]);
  }
  render(shift = 0): HTMLCanvasElement {
    const edge = HOUSING * DOT;
    const canvas = document.createElement("canvas");
    canvas.width = WIDTH * DOT + 2 * edge;
    canvas.height = HEIGHT * DOT + 2 * edge;
    const ctx = canvas.getContext("2d");
    if (!ctx) return canvas;
    ctx.fillStyle = rgb(HOUSING_COLOR);
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = rgb(HOUSING_EDGE);
    ctx.fillRect(0, 0, canvas.width, DOT);
    ctx.fillStyle = rgb(GAP);
    ctx.fillRect(edge, edge, WIDTH * DOT, HEIGHT * DOT);
    ctx.fillStyle = rgb(UNLIT);
    for (let y = 0; y < HEIGHT; y += 1)
      for (let x = 0; x < WIDTH; x += 1)
        ctx.fillRect(edge + x * DOT, edge + y * DOT, DOT - 1, DOT - 1);
    for (const [key, color] of this.lit) {
      const [x0, y] = key.split(",").map(Number);
      const x = x0 + shift;
      if (x < 0 || x >= WIDTH || y < 0 || y >= HEIGHT) continue;
      ctx.fillStyle = rgb(color);
      ctx.fillRect(edge + x * DOT, edge + y * DOT, DOT - 1, DOT - 1);
    }
    return canvas;
  }
}

const rgb = (c: number[]) => `rgb(${c[0]},${c[1]},${c[2]})`;
const CENTER = Math.floor(WIDTH / 2);
const AWAY_LOGO = 3;
const HOME_LOGO = WIDTH - 3 - LOGO;
const LEFT = AWAY_LOGO + LOGO + 25;
const RIGHT = HOME_LOGO - 25;

function periodText(period: number | null | undefined) {
  if (period == null) return "";
  return ORDINALS[period] ? `${ORDINALS[period]} QTR` : period === 5 ? "OT" : `${period - 4}OT`;
}
function downText(s: State) {
  if (s.situation === "kickoff") return "KICKOFF";
  if (s.situation === "extra_point") return "EXTRA POINT";
  if (s.situation === "two_point") return "TWO-POINT TRY";
  if (s.situation === "down" && s.down && ORDINALS[s.down])
    return `${ORDINALS[s.down]} & ${s.goal_to_go ? "GOAL" : s.distance}`;
  return "";
}
function spotText(s: State) {
  if (!s.spot) return "";
  if (s.spot.team_id == null) return `BALL ON ${s.spot.yard}`;
  const side = s.spot.team_id === s.home.team_id ? s.home : s.away;
  return `BALL ON ${side.code} ${s.spot.yard}`;
}

export type Team = { color: RGB; logo: number[][] };

function stateCanvas(state: State, teams: Record<string, Team>, clock?: string | null) {
  const canvas = new Canvas();
  const team = (side: Side, middle: number, edge: number) => {
    const known = teams[side.team_id];
    if (known) canvas.dots(known.logo, edge, 2);
    canvas.centered(side.code, middle, 2, known?.color ?? WHITE);
    if (state.possession === side.team_id) {
      const width = textWidth(side.code);
      const ball = GLYPHS.ball[0].length;
      canvas.icon(
        "ball",
        middle < CENTER
          ? middle + Math.floor(width / 2) + 3
          : middle - Math.floor(width / 2) - 3 - ball,
        4,
        BALL,
      );
    }
    if (side.score != null) canvas.centered(String(side.score), middle, 11, WHITE, 2);
    else canvas.centered("-", middle, 11, DIM, 2);
    if (side.timeouts != null) {
      const pip = GLYPHS.pip[0].length;
      const start = middle - Math.floor((3 * pip + 4) / 2);
      for (let i = 0; i < 3; i += 1)
        canvas.icon("pip", start + i * (pip + 2), 28, i < side.timeouts ? WHITE : UNLIT_PIP);
    }
  };
  team(state.away, LEFT, AWAY_LOGO);
  team(state.home, RIGHT, HOME_LOGO);
  canvas.centered(periodText(state.period), CENTER, 2, DIM);
  const shown = clock ?? state.clock;
  if (shown) canvas.centered(shown, CENTER, 11, WHITE, 2);
  const down = downText(state);
  if (down) canvas.text(down, 6, 35, YELLOW);
  const spot = spotText(state);
  if (spot) canvas.text(spot, WIDTH - 6 - textWidth(spot), 35, BLUE);
  return canvas;
}

function lines(text: string, scale = 2): string[] | null {
  const room = WIDTH - 8;
  if (textWidth(text, scale) <= room) return [text];
  const words = text.split(" ");
  for (let cut = words.length - 1; cut > 0; cut -= 1) {
    const first = words.slice(0, cut).join(" ");
    const second = words.slice(cut).join(" ");
    if (textWidth(first, scale) <= room && textWidth(second, scale) <= room) return [first, second];
  }
  return null;
}

function cardCanvas(result: Result, code: string | null, teamColor: RGB) {
  const canvas = new Canvas();
  const color = TONES[result.tone] ?? WHITE;
  const large = lines(result.text);
  const broken = large ?? lines(result.text, 1) ?? [result.text];
  const scale = large ? 2 : 1;
  const tall = 7 * scale;
  let under = 30;
  if (broken.length === 1) canvas.centered(broken[0], CENTER, scale === 2 ? 9 : 13, color, scale);
  else {
    broken.forEach((line, i) => {
      canvas.centered(line, CENTER, 2 + i * (tall + 2), color, scale);
    });
    under = 2 + 2 * (tall + 2) + 2;
  }
  const pieces: [string, RGB][] = (
    [
      [code ?? "", teamColor],
      [result.jersey ? `#${result.jersey}` : "", WHITE],
      [result.detail ?? "", DIM],
    ] as [string, RGB][]
  ).filter(([text]) => text);
  const whole = pieces.map(([text]) => text).join(" ");
  let x = CENTER - Math.floor(textWidth(whole) / 2);
  for (const [text, c] of pieces) {
    canvas.text(text, x, under, c);
    x += textWidth(`${text} `) + 1;
  }
  return canvas;
}

function seconds(clock: string | null | undefined) {
  const m = /^(\d{1,2}):(\d{2})$/.exec(clock ?? "");
  return m ? Number(m[1]) * 60 + Number(m[2]) : null;
}

export class LedBoard {
  private cache = new Map<string, HTMLCanvasElement>();
  private cards: { canvas: Canvas; sign: number; start: number }[];
  private start: number | null;
  private end: number | null;
  constructor(
    private board: Board,
    private whistle: number,
    private teams: Record<string, Team>,
  ) {
    const away = board.before.away.team_id;
    this.cards = board.results.map((result, index) => {
      const code =
        [board.before.home, board.before.away].find((s) => s.team_id === result.team_id)?.code ??
        null;
      const color = (result.team_id && teams[result.team_id]?.color) || WHITE;
      return {
        canvas: cardCanvas(result, code, color),
        sign: result.team_id === away ? -1 : 1,
        start: whistle + CARD_DELAY + index * CARD_SECONDS,
      };
    });
    this.start = seconds(board.before.clock);
    this.end = seconds(board.after.clock);
  }

  get length() {
    return (
      this.whistle +
      (this.cards.length ? CARD_DELAY + CARD_SECONDS * this.cards.length : SETTLE) +
      HOLD_AFTER
    );
  }

  private clockAt(t: number) {
    if (this.start == null || this.end == null || this.end >= this.start || t < SNAP)
      return this.board.before.clock ?? null;
    const share = Math.min(1, (t - SNAP) / Math.max(0.1, this.whistle - SNAP));
    const left = Math.ceil(this.start - (this.start - this.end) * share);
    return `${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")}`;
  }

  private memo(key: string, make: () => HTMLCanvasElement) {
    let found = this.cache.get(key);
    if (!found) {
      found = make();
      this.cache.set(key, found);
    }
    return found;
  }

  at(t: number): HTMLCanvasElement {
    const before = (clock: string | null) =>
      this.memo(`b:${clock}`, () => stateCanvas(this.board.before, this.teams, clock).render());
    if (t < this.whistle) return before(this.clockAt(t));
    for (const [index, card] of this.cards.entries()) {
      if (card.start <= t && t < card.start + CARD_SECONDS) {
        const progress = Math.min(1, (t - card.start) / SCROLL_SECONDS);
        const shift = Math.round(card.sign * WIDTH * (1 - progress) ** 2);
        return this.memo(`c:${index}:${shift}`, () => card.canvas.render(shift));
      }
    }
    if (
      (this.cards.length && t < this.cards[0].start) ||
      (!this.cards.length && t < this.whistle + SETTLE)
    )
      return before(this.clockAt(t));
    return this.memo("a", () => stateCanvas(this.board.after, this.teams).render());
  }
}

// The board stands centered above the far sideline; two struts carry it down to the stands.
export function drawBoard(
  ctx: CanvasRenderingContext2D,
  image: HTMLCanvasElement,
  width: number,
  top: number,
  fieldTop: number,
) {
  const left = Math.round(width / 2 - image.width / 2);
  ctx.fillStyle = STRUT;
  for (const x of [left + image.width / 4, left + (3 * image.width) / 4])
    ctx.fillRect(x - DOT, top + image.height, DOT * 2, Math.max(0, fieldTop - top - image.height));
  ctx.drawImage(image, left, top);
}
