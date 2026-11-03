"""Renders the frame sheet and sample plays on a plain drawn field. Needs Pillow and NumPy:

uv run --no-project --with pillow --with numpy python scripts/sprites/preview.py

The field here is drawn from nothing, so these previews can be published. Never swap in a Gridiron
field: that art is licensed for the private app only (OWN-015).
"""

import math
import sys
from collections.abc import Callable
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import frames as sprite_frames

OUT = sprite_frames.ASSETS / "preview"
FRAMES = sprite_frames.all_frames()
PALETTE = sprite_frames.palette()
torso_x = sprite_frames.torso_x
WIDTH, HEIGHT, FPS, CROP = 960, 540, 20, 96
ART_PIXEL_YARDS = 3 / 32
# Sets are rows of the sheet, in its order. Add 32 for the other skin tone.
GREEN_SET, SILVER_SET = 11, 4
YARD = 8.08
GOAL_LEFT, NEAR_SIDELINE = 107.5, 458
CYCLES = {
    "RUN": (
        ["run1", "run_pass", "run_knee", "run_float", "run3", "run_far_pass", "run2", "run_far_float"],
        0.62,
    ),
    "DROP": (["drop_a", "drop_b", "drop_c", "drop_b"], 0.55),
}
LOS_COLOR = (40, 110, 230, 215)
FIRST_DOWN_COLOR = (250, 215, 40, 225)
BIG = ImageFont.load_default(size=19)
SMALL = ImageFont.load_default(size=14)


def rgba(rows: list[str], color_set: int) -> Image.Image:
    width = max(map(len, rows))
    pixels = np.zeros((len(rows), width, 4), np.uint8)
    for y, row in enumerate(rows):
        for x, cell in enumerate(row):
            if cell != ".":
                pixels[y, x, :3] = PALETTE[cell][color_set]
                pixels[y, x, 3] = 255
    return Image.fromarray(pixels)


def without_ball(rows: list[str]) -> list[str]:
    width = max(map(len, rows))
    grid = [list(row.ljust(width, ".")) for row in rows]
    result = [row[:] for row in grid]
    for y, row in enumerate(grid):
        for x, cell in enumerate(row):
            if cell in "BC":
                result[y][x] = "."
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        if 0 <= y + dy < len(grid) and 0 <= x + dx < width:
                            if grid[y + dy][x + dx] == "#":
                                result[y + dy][x + dx] = "."
    return ["".join(row) for row in result]


for carried in ("catch_reach", "catch_high", "snap_ready"):
    FRAMES[f"{carried}_e"] = without_ball(FRAMES[carried])


ANCHORS = sprite_frames.anchors()
# One ball sprite, drawn over a carrier's frame: frames themselves never include the ball.
BALL = [line for line in (sprite_frames.ASSETS / "ball.txt").read_text().splitlines() if line and not line.startswith("==")]


def ball_offset(name: str) -> tuple[float, float]:
    rows = FRAMES[name]
    points = [(x, y) for y, row in enumerate(rows) for x, cell in enumerate(row) if cell in "BC"]
    if points:
        center_x = sum(p[0] for p in points) / len(points)
        center_y = sum(p[1] for p in points) / len(points)
    else:  # Drawn without the ball: it sits in the near hand.
        center_x, center_y = ANCHORS[name.removesuffix("_e")]["near_hand"]
    return (center_x - torso_x(rows)) * ART_PIXEL_YARDS, (len(rows) - center_y) * ART_PIXEL_YARDS


def plain_field() -> Image.Image:
    """Same proportions as the app's field: 100 yards plus end zones, 53 1/3 yards wide."""
    scale = 3
    width, height = 1024 * scale, 486 * scale
    field = Image.new("RGB", (width, height), (58, 122, 56))
    draw = ImageDraw.Draw(field)

    def x_of(yard: float) -> float:
        return (GOAL_LEFT + yard * YARD) * scale

    top, bottom = 27 * scale, NEAR_SIDELINE * scale
    for start in range(0, 100, 10):
        draw.rectangle((x_of(start), top, x_of(start + 5), bottom), fill=(64, 130, 60))
    draw.rectangle((0, top, x_of(0), bottom), fill=(44, 92, 58))
    draw.rectangle((x_of(100), top, width, bottom), fill=(44, 92, 58))
    for yard in range(0, 101):
        x = x_of(yard)
        if yard % 5 == 0:
            draw.line((x, top, x, bottom), fill=(238, 240, 234), width=6 if yard % 10 == 0 else 4)
        else:
            for y in (top + 8, top + 0.36 * (bottom - top), top + 0.64 * (bottom - top), bottom - 8):
                draw.line((x, y - 9, x, y + 9), fill=(238, 240, 234), width=3)
    draw.rectangle((0, top - 8, width, top), fill=(245, 245, 240))
    draw.rectangle((0, bottom, width, bottom + 8), fill=(245, 245, 240))
    return field


FIELD = plain_field()
SCALE = 3


class Camera:
    def __init__(self, x: float, tilt: float = 0.0):
        self.position = np.array([x, 22.0, -40.0])
        forward = np.array([x, tilt, 40.0]) - self.position
        self.forward = forward / np.linalg.norm(forward)
        right = np.cross([0, 1, 0], self.forward)
        self.right = right / np.linalg.norm(right)
        self.up = np.cross(self.forward, self.right)

    def project(self, x: float, y: float, z: float) -> tuple[float, float, float]:
        offset = np.array([x, y, z]) - self.position
        depth = offset @ self.forward
        return (
            WIDTH / 2 + 3000 * (offset @ self.right) / depth,
            HEIGHT / 2 - 3000 * (offset @ self.up) / depth,
            3000 / depth,
        )

    def ground(self) -> Image.Image:
        source = [(0, 0), (FIELD.width, 0), (FIELD.width, FIELD.height), (0, FIELD.height)]
        target = []
        for px, py in source:
            x = (px / SCALE - GOAL_LEFT) / YARD
            z = (NEAR_SIDELINE - py / SCALE) / YARD
            target.append(self.project(x, 0, z)[:2])
        matrix, values = [], []
        for (x, y), (u, v) in zip(target, source, strict=True):
            matrix += [[x, y, 1, 0, 0, 0, -u * x, -u * y], [0, 0, 0, x, y, 1, -v * x, -v * y]]
            values += [u, v]
        coefficients = np.linalg.solve(np.array(matrix, float), np.array(values, float))
        return FIELD.transform(
            (WIDTH, HEIGHT),
            Image.PERSPECTIVE,
            coefficients,
            Image.BILINEAR,
            fillcolor=(14, 18, 16),
        )


class Actor:
    def __init__(self, color_set: int, x: float, z: float, facing_left: bool = False):
        self.color_set, self.facing_left = color_set, facing_left
        self.segments: list[tuple[float, float, float, float, float, float, str]] = []
        self.clock, self.x, self.z, self.travel = 0.0, x, z, 0.0
        self.previous: tuple[float, float] | None = None
        self.carries: list[tuple[float, float]] = []
        self.label: str | None = None

    def carry(self, start: float, end: float = 1e9) -> "Actor":
        self.carries.append((start, end))
        return self

    def carrying(self, t: float) -> bool:
        return any(start <= t < end for start, end in self.carries)

    def hold(self, pose: str, seconds: float) -> "Actor":
        return self.move(pose, seconds, self.x, self.z)

    def move(self, pose: str, seconds: float, x: float, z: float) -> "Actor":
        self.segments.append((self.clock, self.clock + seconds, self.x, self.z, x, z, pose))
        self.clock += seconds
        self.x, self.z = x, z
        return self

    def where(self, t: float) -> tuple[float, float, str]:
        for start, end, x0, z0, x1, z1, pose in self.segments:
            if t < end:
                progress = max(0.0, (t - start) / (end - start))
                return x0 + (x1 - x0) * progress, z0 + (z1 - z0) * progress, pose
        return self.x, self.z, self.segments[-1][6]

    def frame(self, t: float) -> tuple[float, float, str]:
        x, z, pose = self.where(t)
        if self.previous is not None:
            self.travel += math.hypot(x - self.previous[0], z - self.previous[1])
        self.previous = (x, z)
        if pose in CYCLES:
            sequence, step = CYCLES[pose]
            pose = sequence[int(self.travel / step) % len(sequence)]
        return x, z, pose


Point = tuple[float, float, float]


def flight(start_time: float, end_time: float, start: Point, end: Point, g: float = 10.7):
    duration = end_time - start_time
    rise = (end[1] - start[1] + 0.5 * g * duration * duration) / duration

    def at(t: float) -> Point:
        elapsed = t - start_time
        share = elapsed / duration
        return (
            start[0] + (end[0] - start[0]) * share,
            start[1] + rise * elapsed - 0.5 * g * elapsed * elapsed,
            start[2] + (end[2] - start[2]) * share,
        )

    return at


def render(
    name: str,
    seconds: float,
    actors: list[Actor],
    ball: Callable[[float], Point | None],
    follow: Callable[[float], float],
    lines: list[tuple[float, tuple[int, int, int, int]]],
    caption: str,
    tilted: bool = False,
    overlay: Callable[[ImageDraw.ImageDraw, "Camera"], None] | None = None,
) -> None:
    images: list[Image.Image] = []
    camera_x, tilt = follow(0), 0.0
    for index in range(int(seconds * FPS)):
        t = index / FPS
        camera_x += (follow(t) - camera_x) * 0.14
        ball_now = ball(t)
        if tilted:
            wanted = min(3.2, ball_now[1] * 0.22) if ball_now and ball_now[1] > 4 else 0.0
            tilt += (wanted - tilt) * 0.1
        camera = Camera(camera_x, tilt)
        image = camera.ground()
        draw = ImageDraw.Draw(image, "RGBA")
        for x, color in lines:
            corners = [(x - 0.28, 0), (x + 0.28, 0), (x + 0.28, 53.3), (x - 0.28, 53.3)]
            draw.polygon([camera.project(a, 0, b)[:2] for a, b in corners], fill=color)
        if overlay is not None:
            overlay(draw, camera)
        tags: list[tuple[float, float, str]] = []
        placed = [(actor, *actor.frame(t)) for actor in actors]
        for actor, x, z, pose in sorted(placed, key=lambda item: -item[2]):
            screen_x, screen_y, per_yard = camera.project(x, 0, z)
            art = per_yard * ART_PIXEL_YARDS
            sprite = rgba(FRAMES[pose], actor.color_set)
            if actor.facing_left:
                sprite = sprite.transpose(Image.FLIP_LEFT_RIGHT)
            width, height = max(1, round(sprite.width * art)), max(1, round(sprite.height * art))
            anchor = sprite.width - torso_x(FRAMES[pose]) if actor.facing_left else torso_x(FRAMES[pose])
            draw.ellipse(
                (
                    screen_x - width * 0.42,
                    screen_y - per_yard * 0.22,
                    screen_x + width * 0.42,
                    screen_y + per_yard * 0.2,
                ),
                fill=(0, 0, 0, 85),
            )
            scaled = sprite.resize((width, height), Image.NEAREST)
            image.paste(scaled, (round(screen_x - anchor * art), round(screen_y - height)), scaled)
            if actor.label:
                tags.append((screen_x, screen_y - height - 6, actor.label))
            spot_name = pose.removesuffix("_e")
            if actor.carrying(t) and spot_name in ANCHORS:
                held = ANCHORS[spot_name]["near_hand" if pose.startswith(("throw", "punt")) else "chest"]
                hand_x = sprite.width - held[0] if actor.facing_left else held[0]
                ball_sprite = rgba(BALL, 0)
                bw, bh = max(1, round(ball_sprite.width * art)), max(1, round(ball_sprite.height * art))
                ball_scaled = ball_sprite.resize((bw, bh), Image.NEAREST)
                left = round(screen_x - anchor * art + hand_x * art - bw / 2)
                image.paste(ball_scaled, (left, round(screen_y - height + held[1] * art - bh / 2)), ball_scaled)
        draw = ImageDraw.Draw(image, "RGBA")
        for tag_x, tag_y, text in tags:
            width_px = draw.textlength(text, font=SMALL)
            draw.rectangle((tag_x - width_px / 2 - 4, tag_y - 18, tag_x + width_px / 2 + 4, tag_y), fill=(10, 12, 14, 170))
            draw.text((tag_x - width_px / 2, tag_y - 17), text, font=SMALL, fill=(240, 240, 235, 255))
        if ball_now is not None:
            x, y, per_yard = camera.project(ball_now[0], 0, ball_now[2])
            draw.ellipse(
                (x - per_yard * 0.2, y - per_yard * 0.08, x + per_yard * 0.2, y + per_yard * 0.08),
                fill=(0, 0, 0, 80),
            )
            x, y, per_yard = camera.project(*ball_now)
            radius, turn = per_yard * 0.26, abs(math.cos(t * 20))
            outline = [
                (
                    x + math.cos(angle) * radius * (0.45 + 0.55 * turn),
                    y + math.sin(angle) * radius * 0.62,
                )
                for angle in np.linspace(0, 2 * math.pi, 14)
            ]
            draw.polygon(outline, fill=(112, 60, 22, 255), outline=(20, 10, 4, 255))
        image = image.crop((0, CROP, WIDTH, HEIGHT))
        draw = ImageDraw.Draw(image, "RGBA")
        bottom = HEIGHT - CROP
        draw.rectangle((0, bottom - 40, WIDTH, bottom), fill=(10, 12, 14, 228))
        draw.text((16, bottom - 32), caption, font=BIG, fill=(240, 240, 235, 255))
        note = "Re-creation from play-by-play"
        draw.text((WIDTH - 16 - draw.textlength(note, font=SMALL), bottom - 28), note, font=SMALL, fill=(200, 205, 200, 255))
        images.append(image)
    palettized = [
        image.convert("P", palette=Image.ADAPTIVE, colors=128, dither=Image.NONE) for image in images
    ]
    palettized[0].save(
        OUT / f"play-{name}.gif",
        save_all=True,
        append_images=palettized[1:],
        duration=int(1000 / FPS),
        loop=0,
        optimize=False,
        disposal=1,
    )
    size = (OUT / f"play-{name}.gif").stat().st_size
    print(f"play-{name}.gif {len(images)} frames {size / 1e6:.1f} MB")


def tackled(actor: Actor, spot: float, z: float) -> Actor:
    actor.move("hit", 0.1, spot - 0.4, z).move("stumble", 0.1, spot - 0.25, z).move("fall_30", 0.1, spot - 0.1, z)
    return actor.move("fall_60", 0.15, spot, z).hold("ground", 4)


def tackler(actor: Actor, wait: float, contact: float, spot: float, z: float, sign: float = 1) -> Actor:
    actor.hold("ready", wait).move("RUN", contact - 0.3 - wait, spot + 2.4 * sign, z - 0.3)
    actor.move("lunge", 0.25, spot + 1.1 * sign, z - 0.2).move("wrap", 0.2, spot + 0.5 * sign, z - 0.2)
    actor.move("fall_60", 0.2, spot + 0.2 * sign, z - 0.2).move("ground", 1.0, spot + 0.2 * sign, z - 0.2)
    return actor.hold("rise_1", 0.25).hold("rise_2", 0.3).hold("rise_3", 0.25).hold("ready", 3)


def pass_play() -> None:
    los, spot, catch_time, contact = 62, 86, 2.95, 4.4
    catch_x, catch_z = 73, 38.5
    passer = Actor(GREEN_SET, 57, 27).carry(0, 2.1).hold("ready", 0.8).move("DROP", 0.7, 54.5, 27)
    passer.hold("drop_b", 0.2).hold("throw_cock", 0.3).hold("throw_mid", 0.1)
    passer.hold("throw_rel", 0.15).hold("throw_follow", 0.35).hold("stand", 4)
    receiver = Actor(GREEN_SET, los, 44).carry(catch_time).hold("ready", 0.8)
    receiver.move("RUN", catch_time - 0.95, catch_x - 1.3, catch_z + 0.2)
    receiver.move("catch_reach_e", 0.15, catch_x, catch_z).move("catch_reach", 0.12, catch_x + 1, catch_z - 0.1)
    receiver.move("catch_secure", 0.2, catch_x + 2.8, catch_z - 0.3)
    receiver.move("RUN", contact - 0.13 - catch_time - 0.32, spot - 0.7, 36.2)
    tackled(receiver, spot, 36)
    defender = tackler(Actor(SILVER_SET, spot + 1.5, 24, True), 1.1, contact, spot, 36)
    dx, dy = ball_offset("throw_mid")
    cx, cy = ball_offset("catch_reach")
    path = flight(2.1, catch_time, (54.5 + dx, dy, 27), (catch_x + cx, cy, catch_z))

    def ball(t: float) -> Point | None:
        return path(t) if 2.1 <= t < catch_time else None

    def follow(t: float) -> float:
        if t < 1.8:
            return 60
        return path(max(t, 2.1))[0] + 2 if t < catch_time else receiver.where(t)[0] + 1

    lines = [(los, LOS_COLOR), (70, FIRST_DOWN_COLOR)]
    render("pass", 6.5, [passer, receiver, defender], ball, follow, lines, "Pass, 24 yards")


def run_play() -> None:
    los, spot, contact = 62, 71, 2.5
    runner = Actor(SILVER_SET, los - 3.5, 27).carry(0).hold("ready", 0.8)
    runner.move("RUN", contact - 0.93, spot - 0.7, 31)
    tackled(runner, spot, 31)
    defender = tackler(Actor(GREEN_SET, spot + 2, 38, True), 1.1, contact, spot, 31)
    render(
        "run",
        4.6,
        [runner, defender],
        lambda _t: None,
        lambda t: runner.where(t)[0] + 2,
        [(los, LOS_COLOR)],
        "Run, 9 yards",
    )


def sack_play() -> None:
    los, spot, contact = 85, 79, 2.5
    passer = Actor(SILVER_SET, 80.5, 27).carry(0).hold("ready", 0.8).move("DROP", 0.7, 78.5, 27)
    passer.hold("drop_b", contact - 1.63)
    passer.move("hit", 0.1, 78.7, 27).move("stumble", 0.08, 78.9, 27).move("fall_30", 0.1, spot, 27)
    passer.move("fall_60", 0.15, spot, 27).hold("ground", 4)
    rusher = tackler(Actor(GREEN_SET, los + 0.5, 34, True), 1.0, contact, spot, 27)
    render(
        "sack",
        4.6,
        [passer, rusher],
        lambda _t: None,
        lambda _t: 80,
        [(los, LOS_COLOR)],
        "Sack, 6 yard loss",
    )


def field_goal() -> None:
    los, hold_x, z, kick_z = 79, 72, 26.2, 27.7
    snapper = Actor(SILVER_SET, los, z).hold("snap_ready", 0.8).hold("snap_release", 0.5).hold("ready", 5)
    holder = Actor(SILVER_SET, hold_x, z).hold("hold_ready", 1.0).hold("hold_catch", 0.15).hold("hold_place", 0.4).hold("hold_ready", 4)
    kicker = Actor(SILVER_SET, hold_x - 3.6, kick_z).hold("ready", 0.75)
    kicker.move("RUN", 0.55, hold_x - 1.8, kick_z).move("kick_plant", 0.12, hold_x - 1.4, kick_z)
    kicker.move("kick_swing", 0.08, hold_x - 1.1, kick_z).move("kick_strike", 0.12, hold_x - 0.9, kick_z)
    kicker.move("kick_follow", 0.5, hold_x - 0.6, kick_z).hold("stand", 0.6)
    for pose in ("arms_up", "arms_jump", "arms_up", "arms_jump"):
        kicker.hold(pose, 0.25)
    kicker.hold("arms_up", 3)
    sx, sy = ball_offset("snap_ready")
    hx, hy = ball_offset("hold_place")
    snap = flight(0.8, 1.15, (los + sx, sy, z), (hold_x + hx, hy, z), g=2.0)
    kick = flight(1.5, 3.7, (hold_x + hx, hy, z), (110, 6.5, 26.67))

    def ball(t: float) -> Point | None:
        if 0.8 <= t < 1.15:
            return snap(t)
        if 1.5 <= t < 3.7:
            return kick(t)
        return (min(113, 110 + (t - 3.7) * 8), max(0.2, 6.5 - (t - 3.7) * 5), 26.67) if t >= 3.7 else None

    def follow(t: float) -> float:
        return 74 if t < 1.5 else 74 + (min(t, 3.7) - 1.5) * 13.5

    render("fg", 5.2, [snapper, holder, kicker], ball, follow, [(los, LOS_COLOR)], "Field goal", tilted=True)


def punt() -> None:
    los, start, landing, z, hang, kick_time = 60, 47, 89, 27, 3.7, 1.14
    punter = Actor(GREEN_SET, start, z).carry(0, kick_time).hold("ready", 0.7).hold("punt_hold", 0.35)
    punter.move("punt_drop", 0.15, start + 0.6, z).move("punt_strike", 0.12, start + 1.2, z)
    punter.move("punt_follow", 0.6, start + 1.6, z).hold("stand", 8)
    arrival = kick_time + hang
    returner = Actor(SILVER_SET, landing, 30, True).carry(arrival).hold("ready", arrival - 0.3)
    returner.hold("catch_high_e", 0.3).hold("catch_high", 0.12).move("catch_secure", 0.2, landing - 0.3, 30)
    returner.move("hit", 0.1, landing - 0.6, 30).move("stumble", 0.1, landing - 0.7, 30).move("fall_30", 0.1, landing - 0.8, 30)
    returner.move("fall_60", 0.15, landing - 1, 30).hold("ground", 4)
    coverage = Actor(GREEN_SET, 72, 24).hold("ready", 0.9)
    coverage.move("RUN", arrival + 0.42 - 0.3 - 0.9, landing - 3, 29.7).move("lunge", 0.25, landing - 1.8, 29.8)
    coverage.move("wrap", 0.2, landing - 1.3, 29.8).move("fall_60", 0.2, landing - 1.2, 29.8).hold("ground", 4)
    bx, by = ball_offset("catch_high")
    path = flight(kick_time, arrival, (start + 1.6, 1.1, z), (landing - bx, by, 30))

    def ball(t: float) -> Point | None:
        return path(t) if kick_time <= t < arrival else None

    def follow(t: float) -> float:
        return 52 if t < kick_time else min(87, path(min(t, arrival))[0] + 1)

    render("punt", arrival + 2.6, [punter, returner, coverage], ball, follow, [(los, LOS_COLOR)], "Punt, tackled on the return", tilted=True)


def frame_sheet() -> None:
    names = [name for name in FRAMES if not name.endswith("_e")]
    scale, cell_w, cell_h, columns = 5, 240, 215, 10
    rows = (len(names) + columns - 1) // columns
    sets = (GREEN_SET, SILVER_SET + 32)
    sheet = Image.new("RGB", (columns * cell_w, cell_h * rows * len(sets)), (92, 104, 92))
    draw = ImageDraw.Draw(sheet)
    groups = sprite_frames.load_groups()
    for j, color_set in enumerate(sets):
        for i, name in enumerate(names):
            left, top = (i % columns) * cell_w, (i // columns) * cell_h + j * rows * cell_h
            sprite = rgba(FRAMES[name], color_set)
            sprite = sprite.resize((sprite.width * scale, sprite.height * scale), Image.NEAREST)
            sheet.paste(sprite, (left + (cell_w - sprite.width) // 2, top + cell_h - 8 - sprite.height), sprite)
            original = name in groups["base"]
            draw.text((left + 6, top + 3), name, font=SMALL, fill=(255, 255, 255) if original else (255, 235, 120))
    sheet.save(OUT / "all-frames.png", optimize=True)


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    frame_sheet()
    pass_play()
    run_play()
    sack_play()
    field_goal()
    punt()
