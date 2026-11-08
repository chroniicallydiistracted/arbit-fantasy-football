"""The stadium board in the full-field view (slice 5), drawn by the review renderer.

The board's facts come from `arbit_data.live.board` (one implementation); this draws them. It
stands above the far sideline facing the camera, in board pixels of 3 screen pixels, each a lit
or unlit LED, with our own glyphs from assets/sprites/board/glyphs.txt.

- **Teams.** Each team's logo sits at its outer edge, drawn in the same LED dots (OWN-039). Beside
  it are its code in its name tag color (OWN-038), its score and its timeouts left.
- **Signals.** Down and distance are in the yellow of the line to gain, and the ball's spot in the
  blue of the line of scrimmage. Scores and the clock are white.
- **The clock** shows the snap's time until the snap, then runs one second per second, as the real
  clock did, and stops on the end-of-play time once a source gives one (OWN-051). Without one it
  holds.
- **Results.** After the whistle each result scrolls in from the side of the team it is for. It
  is green for a score, red for a turnover or a miss, and yellow for a flag, which also names the
  foul, the team and the player's number. The board then turns to the game after the play.

Team logos are the teams' trademarks. They are read from the private data/logos/ (fetched by
fetch_logos.py) and never committed; without them the board is drawn without logos.
"""

import math
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

import numpy as np
from arbit_data.live.board import BoardResult, BoardSide, BoardState, PlayBoard
from arbit_data.live.choreography import SNAP
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
GLYPHS_PATH = ROOT / "assets/sprites/board/glyphs.txt"
LOGOS = ROOT / "data/logos/espn/dark"  # ESPN's logos made for dark backgrounds; private
DOT = 3  # screen pixels per board pixel
WIDTH, HEIGHT = 256, 43  # board pixels, the lit field inside the housing
HOUSING = 3  # board pixels of dark housing around the lit field
LOGO = 30  # board pixels square
CARD_SECONDS = 2.0
CARD_DELAY = 0.3  # after the whistle, before the first result
SCROLL_SECONDS = 0.6
SETTLE = 0.5  # with no result, the board turns to the game after the play this long after the whistle
HOLD_AFTER = 1.2  # the clip shows the game after the play at least this long

WHITE = (238, 238, 228)
DIM = (150, 152, 146)
YELLOW = (250, 215, 40)  # the line to gain (preview.FIRST_DOWN_COLOR)
BLUE = (96, 156, 255)  # the line of scrimmage, lifted to read on black
BALL = (176, 98, 36)
# The design system's signals in dark mode: gain, challenge and flag (OWN-039).
TONES = {"good": (95, 216, 146), "bad": (255, 138, 145), "flag": (255, 198, 0)}
UNLIT = (24, 26, 28)
UNLIT_PIP = (58, 60, 58)  # a timeout used
GAP = (9, 10, 11)
HOUSING_COLOR = (40, 44, 48)
HOUSING_EDGE = (62, 67, 72)
STRUT = (30, 33, 36)

RGB = tuple[int, int, int]


def load_glyphs(path: Path = GLYPHS_PATH) -> dict[str, list[str]]:
    glyphs: dict[str, list[str]] = {}
    for chunk in re.split(r"(?m)^== ", path.read_text()):
        if not chunk.strip() or chunk.startswith("#"):
            continue
        name, *rows = [line for line in chunk.split("\n") if line]
        glyphs[{"space": " ", "hash": "#"}.get(name, name)] = rows
    return glyphs


GLYPHS = load_glyphs()


def missing(text: str) -> set[str]:
    return {char for char in text if char not in GLYPHS}


def text_width(text: str, scale: int = 1) -> int:
    widths = [len(GLYPHS[char][0]) for char in text]
    return (sum(widths) + max(0, len(widths) - 1)) * scale


@cache
def logo(code: str) -> dict[tuple[int, int], RGB]:
    """A team's logo as LED dots: each dot the logo's color over its square, lit where the logo
    covers most of it, in a few flat colors as an LED board shows them. Empty without the file."""
    path = LOGOS / f"{code}.png"
    if not path.exists():
        return {}
    pixels = np.asarray(Image.open(path).convert("RGBA")).astype(float) / 255
    ys, xs = np.nonzero(pixels[..., 3] > 0.05)
    pixels = pixels[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
    height, width = pixels.shape[:2]
    side = max(height, width)
    square = np.zeros((side, side, 4))
    top, left = (side - height) // 2, (side - width) // 2
    square[top : top + height, left : left + width] = pixels
    step = side / LOGO
    dots: dict[tuple[int, int], RGB] = {}
    for y in range(LOGO):
        for x in range(LOGO):
            block = square[int(y * step) : int((y + 1) * step), int(x * step) : int((x + 1) * step)]
            alpha = block[..., 3]
            if alpha.mean() >= 0.45:
                rgb = (block[..., :3] * alpha[..., None]).sum((0, 1)) / alpha.sum()
                dots[(x, y)] = tuple(int(v * 255) for v in rgb)  # type: ignore[assignment]
    if dots:
        keys = list(dots)
        strip = Image.new("RGB", (len(keys), 1))
        strip.putdata([dots[key] for key in keys])
        flat = strip.quantize(6, method=Image.Quantize.MEDIANCUT).convert("RGB")
        for key, color in zip(keys, np.asarray(flat).reshape(-1, 3), strict=True):
            dots[key] = tuple(int(v) for v in color)  # type: ignore[assignment]
    return dots


@dataclass
class Canvas:
    """The lit field: a color for each lit board pixel."""

    lit: dict[tuple[int, int], RGB] = field(default_factory=dict)

    def text(self, text: str, x: int, y: int, color: RGB, scale: int = 1) -> None:
        for char in text:
            rows = GLYPHS[char]
            for row, line in enumerate(rows):
                for column, cell in enumerate(line):
                    if cell == "#":
                        for dy in range(scale):
                            for dx in range(scale):
                                self.lit[(x + column * scale + dx, y + row * scale + dy)] = color
            x += (len(rows[0]) + 1) * scale

    def centered(self, text: str, middle: int, y: int, color: RGB, scale: int = 1) -> None:
        self.text(text, middle - text_width(text, scale) // 2, y, color, scale)

    def dots(self, dots: dict[tuple[int, int], RGB], x: int, y: int) -> None:
        for (dx, dy), color in dots.items():
            self.lit[(x + dx, y + dy)] = color

    def image(self, shift: int = 0) -> Image.Image:
        """The board as screen pixels, housing included. `shift` moves everything lit that many
        board pixels sideways, as a card scrolls in."""
        edge = HOUSING * DOT
        out = np.zeros(((HEIGHT * DOT) + 2 * edge, (WIDTH * DOT) + 2 * edge, 4), np.uint8)
        out[..., :3], out[..., 3] = HOUSING_COLOR, 255
        out[:DOT, :, :3] = HOUSING_EDGE  # light catches the top edge
        field_ = out[edge : edge + HEIGHT * DOT, edge : edge + WIDTH * DOT]
        field_[..., :3] = GAP
        for y in range(HEIGHT):
            for x in range(WIDTH):
                field_[y * DOT : y * DOT + DOT - 1, x * DOT : x * DOT + DOT - 1, :3] = UNLIT
        for (x, y), color in self.lit.items():
            x += shift
            if 0 <= x < WIDTH and 0 <= y < HEIGHT:
                field_[y * DOT : y * DOT + DOT - 1, x * DOT : x * DOT + DOT - 1, :3] = color
        return Image.fromarray(out)


ORDINALS = {1: "1ST", 2: "2ND", 3: "3RD", 4: "4TH"}
CENTER = WIDTH // 2
AWAY_LOGO, HOME_LOGO = 3, WIDTH - 3 - LOGO  # each team's logo at its outer edge
LEFT, RIGHT = AWAY_LOGO + LOGO + 25, HOME_LOGO - 25  # each team's code, score and timeouts
COLUMN = 44  # board pixels for a team's code and score, between its logo and the clock
MIDDLE = 64  # board pixels for the quarter and the clock


def period_text(period: int | None) -> str:
    if period is None:
        return ""
    return f"{ORDINALS[period]} QTR" if period in ORDINALS else "OT" if period == 5 else f"{period - 4}OT"


def down_text(state: BoardState) -> str:
    if state.situation == "kickoff":
        return "KICKOFF"
    if state.situation == "extra_point":
        return "EXTRA POINT"
    if state.situation == "two_point":
        return "TWO-POINT TRY"
    if state.situation == "down" and state.down in ORDINALS:
        return f"{ORDINALS[state.down]} & {'GOAL' if state.goal_to_go else state.distance}"
    return ""


def spot_text(state: BoardState) -> str:
    if state.spot is None:
        return ""
    if state.spot.team_id is None:
        return f"BALL ON {state.spot.yard}"
    side = state.home if state.spot.team_id == state.home.team_id else state.away
    return f"BALL ON {side.code} {state.spot.yard}"


def texts(state: BoardState) -> dict[str, tuple[str, int]]:
    """Every string the board shows for a state, with the board pixels its space has."""
    shown = {
        "away code": (state.away.code, COLUMN - 10),  # with the ball beside it
        "home code": (state.home.code, COLUMN - 10),
        "period": (period_text(state.period), MIDDLE),
        "down": (down_text(state), WIDTH // 2 - 8),
        "spot": (spot_text(state), WIDTH // 2 - 8),
    }
    return {key: (text, room) for key, (text, room) in shown.items() if text}


def state_canvas(state: BoardState, colors: Callable[[str], RGB], clock: str | None = None) -> Canvas:
    canvas = Canvas()
    for side, middle, edge in ((state.away, LEFT, AWAY_LOGO), (state.home, RIGHT, HOME_LOGO)):
        canvas.dots(logo(side.code), edge, 2)
        _team(canvas, side, middle, state.possession == side.team_id, colors(side.team_id))
    canvas.centered(period_text(state.period), CENTER, 2, DIM)
    if clock or state.clock:
        canvas.centered(clock or state.clock or "", CENTER, 11, WHITE, 2)
    if down := down_text(state):
        canvas.text(down, 6, 35, YELLOW)
    if spot := spot_text(state):
        canvas.text(spot, WIDTH - 6 - text_width(spot), 35, BLUE)
    return canvas


def _team(canvas: Canvas, side: BoardSide, middle: int, has_ball: bool, color: RGB) -> None:
    canvas.centered(side.code, middle, 2, color)
    if has_ball:  # the ball beside the code, toward the middle of the board
        width = text_width(side.code)
        ball = len(GLYPHS["ball"][0])
        x = middle + width // 2 + 3 if middle < CENTER else middle - width // 2 - 3 - ball
        _icon(canvas, "ball", x, 4, BALL)
    if side.score is not None:
        canvas.centered(str(side.score), middle, 11, WHITE, 2)
    else:
        canvas.centered("-", middle, 11, DIM, 2)
    if side.timeouts is not None:
        pip = len(GLYPHS["pip"][0])
        start = middle - (3 * pip + 2 * 2) // 2
        for index in range(3):
            _icon(canvas, "pip", start + index * (pip + 2), 28, WHITE if index < side.timeouts else UNLIT_PIP)


def _icon(canvas: Canvas, name: str, x: int, y: int, color: RGB) -> None:
    for row, line in enumerate(GLYPHS[name]):
        for column, cell in enumerate(line):
            if cell == "#":
                canvas.lit[(x + column, y + row)] = color


def lines(text: str, scale: int = 2) -> list[str] | None:
    """`text` in one or two lines that fit the board at `scale`, broken between words."""
    room = WIDTH - 8
    if text_width(text, scale) <= room:
        return [text]
    words = text.split(" ")
    for cut in range(len(words) - 1, 0, -1):
        first, second = " ".join(words[:cut]), " ".join(words[cut:])
        if text_width(first, scale) <= room and text_width(second, scale) <= room:
            return [first, second]
    return None


def team_line(result: BoardResult, code: str | None) -> str:
    """The small line under a result: the team, and for a flag the player's number and status."""
    parts = [code or ""]
    if result.jersey:
        parts.append(f"#{result.jersey}")
    if result.detail:
        parts.append(result.detail)
    return " ".join(part for part in parts if part)


def card_canvas(result: BoardResult, code: str | None, team_color: RGB) -> Canvas:
    canvas = Canvas()
    color = TONES[result.tone]
    broken = lines(result.text) or lines(result.text, 1) or [result.text]
    scale = 2 if lines(result.text) else 1
    tall = 7 * scale
    if len(broken) == 1:
        canvas.centered(broken[0], CENTER, 9 if scale == 2 else 13, color, scale)
        under = 30
    else:
        for index, line in enumerate(broken):
            canvas.centered(line, CENTER, 2 + index * (tall + 2), color, scale)
        under = 2 + 2 * (tall + 2) + 2
    # The team in its color, a flag's player number in white and its status dimmer.
    pieces = [
        (text, color)
        for text, color in (
            (code or "", team_color),
            (f"#{result.jersey}" if result.jersey else "", WHITE),
            (result.detail or "", DIM),
        )
        if text
    ]
    x = CENTER - text_width(team_line(result, code)) // 2
    for text, color in pieces:
        canvas.text(text, x, under, color)
        x += text_width(text + " ") + 1
    return canvas


def clock_seconds(clock: str | None) -> int | None:
    match = re.fullmatch(r"(\d{1,2}):(\d{2})", clock or "")
    return int(match.group(1)) * 60 + int(match.group(2)) if match else None


class Board:
    """The board for one clip, drawn behind the field by `preview.render` (its `backdrop`)."""

    def __init__(self, board: PlayBoard, whistle: float, colors: Callable[[str], RGB]):
        self.board, self.whistle, self.colors = board, whistle, colors
        away = board.before.away.team_id
        self.cards = []
        for index, result in enumerate(board.results):
            code = self._code(result.team_id)
            color = colors(result.team_id) if result.team_id else WHITE
            # From the side of the team it's for: the away team's panel is on the left.
            sign = -1 if result.team_id == away else 1
            self.cards.append((card_canvas(result, code, color), sign, whistle + CARD_DELAY + index * CARD_SECONDS))
        self.after = state_canvas(board.after, colors).image()
        self.clocks: dict[str, Image.Image] = {}
        self.cache: dict[tuple[int, int], Image.Image] = {}
        self.start = clock_seconds(board.before.clock)
        self.end = clock_seconds(board.after.clock)
        self.before = self._before(board.before.clock)

    def _before(self, clock: str | None) -> Image.Image:
        key = clock or ""
        if key not in self.clocks:
            self.clocks[key] = state_canvas(self.board.before, self.colors, clock).image()
        return self.clocks[key]

    def _code(self, team: str | None) -> str | None:
        for side in (self.board.before.home, self.board.before.away):
            if side.team_id == team:
                return side.code
        return None

    @property
    def length(self) -> float:
        """How long a clip must run to show every result and then the game after the play."""
        cards = CARD_DELAY + CARD_SECONDS * len(self.cards) if self.cards else SETTLE
        return self.whistle + cards + HOLD_AFTER

    def clock_at(self, t: float) -> str | None:
        """The clock in real time from the snap, stopping on the end of the play when known."""
        if self.start is None or self.end is None or self.end >= self.start or t < SNAP:
            return self.board.before.clock
        left = max(self.end, math.ceil(self.start - (t - SNAP)))
        return f"{left // 60}:{left % 60:02d}"

    def at(self, t: float) -> Image.Image:
        if t < self.whistle:
            return self._before(self.clock_at(t))
        for index, (canvas, sign, start) in enumerate(self.cards):
            if start <= t < start + CARD_SECONDS:
                progress = min(1.0, (t - start) / SCROLL_SECONDS)
                shift = round(sign * WIDTH * (1 - progress) ** 2)  # eases to a stop
                if (index, shift) not in self.cache:
                    self.cache[(index, shift)] = canvas.image(shift)
                return self.cache[(index, shift)]
        if self.cards and t < self.cards[0][2]:
            return self._before(self.clock_at(t))
        if not self.cards and t < self.whistle + SETTLE:
            return self._before(self.clock_at(t))
        return self.after

    def place(self, camera) -> tuple[int, int]:
        """Top left on screen: centered over the field, a little above the far sideline."""
        far = min(y for _x, y in camera.field_corners())
        image = self.after
        return round(camera.shot.width / 2 - image.width / 2), round(far - 16 - image.height)

    def top(self, camera) -> int:
        return self.place(camera)[1]

    def draw(self, image: Image.Image, camera, t: float) -> None:
        board = self.at(t)
        left, top = self.place(camera)
        far = round(min(y for _x, y in camera.field_corners()))
        bottom = top + board.height
        pixels = image.load()
        for x in (left + board.width // 4, left + 3 * board.width // 4):  # two struts down to the stands
            for y in range(bottom, far):
                for dx in range(-DOT, DOT):
                    pixels[x + dx, y] = STRUT
        image.paste(board, (left, top))

    def colors_used(self) -> set[RGB]:
        found: set[RGB] = {STRUT}
        images = [self.before, self.after] + [canvas.image() for canvas, _sign, _start in self.cards]
        for picture in images:
            array = np.asarray(picture)[..., :3].reshape(-1, 3)
            found.update(tuple(int(v) for v in row) for row in np.unique(array, axis=0))
        return found
