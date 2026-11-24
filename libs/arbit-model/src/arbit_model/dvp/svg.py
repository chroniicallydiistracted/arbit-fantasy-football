"""Deterministic SVG plots for the DvP reports (no plotting dependency; same input, same bytes).

Colors are the Okabe-Ito colorblind-safe set, one per position group. Plots have an explicit
white background so they read the same in light and dark viewers.
"""

import math
from collections.abc import Sequence
from html import escape

COLORS = {
    "QB": "#0072B2",
    "RB": "#009E73",
    "WR": "#D55E00",
    "TE": "#CC79A7",
    "K": "#E69F00",
    "DST": "#000000",
}
INK, MUTED, GRID = "#1a1a1a", "#666666", "#e3e3e3"
FONT = "font-family='Helvetica, Arial, sans-serif'"


def _f(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _ticks(low: float, high: float, count: int = 5) -> list[float]:
    span = high - low
    if span <= 0:
        return [low]
    raw = span / count
    magnitude = 10 ** math.floor(math.log10(raw))
    step = min((s * magnitude for s in (1, 2, 2.5, 5, 10) if s * magnitude >= raw), default=raw)
    first = math.ceil(low / step) * step
    ticks, value = [], first
    while value <= high + 1e-9:
        ticks.append(round(value, 10))
        value += step
    return ticks


def _label(value: float) -> str:
    return f"{value:g}" if abs(value) < 1e5 else f"{value:.1e}"


class Canvas:
    def __init__(self, width: int, height: int, title: str) -> None:
        self.width, self.height = width, height
        self.parts = [
            f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' "
            f"viewBox='0 0 {width} {height}' {FONT} font-size='12'>",
            f"<title>{escape(title)}</title>",
            f"<rect width='{width}' height='{height}' fill='#ffffff'/>",
            f"<text x='16' y='24' font-size='15' font-weight='bold' fill='{INK}'>"
            f"{escape(title)}</text>",
        ]

    def add(self, element: str) -> None:
        self.parts.append(element)

    def text(self, x: float, y: float, content: str, **attrs: str) -> None:
        extra = " ".join(f"{k.replace('_', '-')}='{v}'" for k, v in attrs.items())
        self.add(f"<text x='{_f(x)}' y='{_f(y)}' {extra}>{escape(content)}</text>")

    def render(self) -> str:
        return "\n".join([*self.parts, "</svg>"]) + "\n"


class Panel:
    """A plotting area inside a canvas with linear (or log10) axes."""

    def __init__(
        self,
        canvas: Canvas,
        box: tuple[float, float, float, float],
        xlim: tuple[float, float],
        ylim: tuple[float, float],
        *,
        xlog: bool = False,
    ) -> None:
        self.c, self.box, self.xlim, self.ylim, self.xlog = canvas, box, xlim, ylim, xlog

    def x(self, value: float) -> float:
        left, _, width, _ = self.box
        low, high = self.xlim
        if self.xlog:
            value, low, high = math.log10(value), math.log10(low), math.log10(high)
        return left + (value - low) / (high - low) * width

    def y(self, value: float) -> float:
        _, top, _, height = self.box
        low, high = self.ylim
        return top + height - (value - low) / (high - low) * height

    def axes(self, xlabel: str, ylabel: str, xticks: Sequence[float] | None = None) -> None:
        left, top, width, height = self.box
        ticks_x = list(xticks) if xticks is not None else _ticks(*self.xlim)
        for t in ticks_x:
            px = self.x(t)
            self.c.add(
                f"<line x1='{_f(px)}' y1='{_f(top)}' x2='{_f(px)}' y2='{_f(top + height)}' "
                f"stroke='{GRID}'/>"
            )
            self.c.text(px, top + height + 15, _label(t), text_anchor="middle", fill=MUTED)
        for t in _ticks(*self.ylim):
            py = self.y(t)
            self.c.add(
                f"<line x1='{_f(left)}' y1='{_f(py)}' x2='{_f(left + width)}' y2='{_f(py)}' "
                f"stroke='{GRID}'/>"
            )
            self.c.text(left - 6, py + 4, _label(t), text_anchor="end", fill=MUTED)
        self.c.add(
            f"<rect x='{_f(left)}' y='{_f(top)}' width='{_f(width)}' height='{_f(height)}' "
            f"fill='none' stroke='{MUTED}'/>"
        )
        self.c.text(left + width / 2, top + height + 32, xlabel, text_anchor="middle", fill=INK)
        cx, cy = left - 40, top + height / 2
        self.c.add(
            f"<text x='{_f(cx)}' y='{_f(cy)}' transform='rotate(-90 {_f(cx)} {_f(cy)})' "
            f"text-anchor='middle' fill='{INK}'>{escape(ylabel)}</text>"
        )

    def line(
        self, xs: Sequence[float], ys: Sequence[float], color: str, width: float = 2, dash: str = ""
    ) -> None:
        points = " ".join(f"{_f(self.x(a))},{_f(self.y(b))}" for a, b in zip(xs, ys, strict=True))
        style = f" stroke-dasharray='{dash}'" if dash else ""
        self.c.add(
            f"<polyline points='{points}' fill='none' stroke='{color}' stroke-width='{width}'{style}/>"
        )

    def band(
        self, xs: Sequence[float], lows: Sequence[float], highs: Sequence[float], color: str
    ) -> None:
        top = [f"{_f(self.x(a))},{_f(self.y(b))}" for a, b in zip(xs, highs, strict=True)]
        bottom = [f"{_f(self.x(a))},{_f(self.y(b))}" for a, b in zip(xs, lows, strict=True)][::-1]
        self.c.add(
            f"<polygon points='{' '.join(top + bottom)}' fill='{color}' fill-opacity='0.15' stroke='none'/>"
        )

    def dots(
        self, xs: Sequence[float], ys: Sequence[float], color: str, radius: float = 2.5
    ) -> None:
        for a, b in zip(xs, ys, strict=True):
            self.c.add(
                f"<circle cx='{_f(self.x(a))}' cy='{_f(self.y(b))}' r='{radius}' fill='{color}' "
                f"fill-opacity='0.55'/>"
            )


def _limits(values: Sequence[float], pad: float = 0.05) -> tuple[float, float]:
    low, high = min(values), max(values)
    span = (high - low) or 1.0
    return low - pad * span, high + pad * span


def scatter(
    title: str,
    xs: Sequence[float],
    ys: Sequence[float],
    *,
    color: str,
    xlabel: str,
    ylabel: str,
    note: str,
) -> str:
    """Two halves' means per unit, with the identity line and the least-squares line."""
    canvas = Canvas(520, 520, title)
    both = list(xs) + list(ys)
    lim = _limits(both)
    panel = Panel(canvas, (70, 50, 420, 400), lim, lim)
    panel.axes(xlabel, ylabel)
    panel.line([lim[0], lim[1]], [lim[0], lim[1]], MUTED, 1, "4 4")
    panel.dots(xs, ys, color)
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx:
        slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / sxx
        panel.line(
            [lim[0], lim[1]], [my + slope * (lim[0] - mx), my + slope * (lim[1] - mx)], color
        )
    canvas.text(70, 500, note, fill=MUTED)
    return canvas.render()


def forest(
    title: str,
    rows: Sequence[tuple[str, str, float | None, float | None, float | None]],
    *,
    xlabel: str,
    xlim: tuple[float, float],
    note: str,
    log: bool = True,
) -> str:
    """Point estimates with intervals on a log (or linear) axis. Rows: (label, group, estimate,
    low, high); an open-ended interval runs to the axis edge with an arrow."""
    height = 80 + 22 * len(rows) + 50
    canvas = Canvas(720, height, title)
    panel = Panel(canvas, (230, 50, 460, 22 * len(rows)), xlim, (0, len(rows)), xlog=log)
    ticks = (
        [t for t in (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000) if xlim[0] <= t <= xlim[1]]
        if log
        else _ticks(*xlim)
    )
    left, top, width, rows_height = panel.box
    for t in ticks:
        px = panel.x(t)
        canvas.add(
            f"<line x1='{_f(px)}' y1='{_f(top)}' x2='{_f(px)}' y2='{_f(top + rows_height)}' stroke='{GRID}'/>"
        )
        canvas.text(px, top + rows_height + 15, _label(t), text_anchor="middle", fill=MUTED)
    canvas.text(left + width / 2, top + rows_height + 32, xlabel, text_anchor="middle", fill=INK)
    for i, (label, group, estimate, low, high) in enumerate(rows):
        cy = top + 22 * i + 11
        color = COLORS.get(group, INK)
        canvas.text(left - 8, cy + 4, label, text_anchor="end", fill=INK)
        lo = max(low if low is not None else xlim[0], xlim[0])
        hi = min(high if high is not None else xlim[1], xlim[1])
        canvas.add(
            f"<line x1='{_f(panel.x(lo))}' y1='{_f(cy)}' x2='{_f(panel.x(hi))}' y2='{_f(cy)}' "
            f"stroke='{color}' stroke-width='2'/>"
        )
        if high is None or high > xlim[1]:
            ax = panel.x(xlim[1])
            canvas.add(
                f"<polygon points='{_f(ax)},{_f(cy)} {_f(ax - 7)},{_f(cy - 4)} {_f(ax - 7)},{_f(cy + 4)}' "
                f"fill='{color}'/>"
            )
        if estimate is not None and xlim[0] <= estimate <= xlim[1]:
            canvas.add(f"<circle cx='{_f(panel.x(estimate))}' cy='{_f(cy)}' r='4' fill='{color}'/>")
    canvas.text(16, height - 12, note, fill=MUTED)
    return canvas.render()


def lines(
    title: str,
    series: Sequence[
        tuple[
            str,
            str,
            Sequence[float],
            Sequence[float],
            Sequence[float] | None,
            Sequence[float] | None,
        ]
    ],
    *,
    xlabel: str,
    ylabel: str,
    ylim: tuple[float, float],
    note: str,
    xticks: Sequence[float] | None = None,
) -> str:
    """Line series with optional bands. Series: (label, group, xs, ys, lows, highs)."""
    canvas = Canvas(720, 470, title)
    xs_all = [x for s in series for x in s[2]]
    panel = Panel(canvas, (70, 50, 470, 340), (min(xs_all), max(xs_all)), ylim)
    panel.axes(xlabel, ylabel, xticks)
    for _label, group, xs, ys, lows, highs in series:
        color = COLORS.get(group, INK)
        if lows is not None and highs is not None:
            panel.band(xs, lows, highs, color)
        panel.line(xs, ys, color)
    for i, (label, group, *_rest) in enumerate(series):
        cy = 64 + 20 * i
        canvas.add(
            f"<rect x='560' y='{cy - 9}' width='14' height='4' fill='{COLORS.get(group, INK)}'/>"
        )
        canvas.text(580, cy, label, fill=INK)
    canvas.text(16, 455, note, fill=MUTED)
    return canvas.render()


def histograms(
    title: str,
    panels: Sequence[tuple[str, str, Sequence[float], float | None]],
    *,
    xlabel: str,
    note: str,
    bins: int = 30,
) -> str:
    """Small multiples of null distributions, each with its observed value marked."""
    cols = 3
    rows_n = math.ceil(len(panels) / cols)
    canvas = Canvas(780, 70 + rows_n * 210 + 30, title)
    for i, (label, group, values, observed) in enumerate(panels):
        col, row = i % cols, i // cols
        left, top = 50 + col * 250, 55 + row * 210
        low = min(min(values), observed if observed is not None else min(values))
        high = max(max(values), observed if observed is not None else max(values))
        low, high = _limits([low, high], 0.04)
        width = (high - low) / bins
        counts = [0] * bins
        for v in values:
            counts[min(bins - 1, int((v - low) / width))] += 1
        panel = Panel(canvas, (left, top + 18, 210, 140), (low, high), (0, max(counts) * 1.1))
        color = COLORS.get(group, INK)
        for b, count in enumerate(counts):
            x0, x1 = panel.x(low + b * width), panel.x(low + (b + 1) * width)
            y0 = panel.y(count)
            canvas.add(
                f"<rect x='{_f(x0)}' y='{_f(y0)}' width='{_f(max(x1 - x0 - 0.5, 0.5))}' "
                f"height='{_f(panel.y(0) - y0)}' fill='{MUTED}' fill-opacity='0.6'/>"
            )
        if observed is not None:
            ox = panel.x(observed)
            canvas.add(
                f"<line x1='{_f(ox)}' y1='{_f(top + 18)}' x2='{_f(ox)}' y2='{_f(top + 158)}' "
                f"stroke='{color}' stroke-width='3'/>"
            )
        canvas.add(
            f"<rect x='{left}' y='{top + 18}' width='210' height='140' fill='none' stroke='{MUTED}'/>"
        )
        canvas.text(left, top + 12, label, fill=INK, font_weight="bold")
        for t in _ticks(low, high, 4):
            canvas.text(panel.x(t), top + 172, _label(t), text_anchor="middle", fill=MUTED)
        canvas.text(left + 105, top + 190, xlabel, text_anchor="middle", fill=MUTED)
    canvas.text(16, canvas.height - 12, note, fill=MUTED)
    return canvas.render()
