"""Real uniforms are measured from their sheets and shaded the way the owner's art is (OWN-028)."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/sprites"))
SPEC = importlib.util.spec_from_file_location("uniforms", ROOT / "scripts/sprites/uniforms.py")
assert SPEC is not None and SPEC.loader is not None
uniforms = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(uniforms)

PALETTE = json.loads((ROOT / "assets/sprites/palette.json").read_text())
WHITE, OUTLINE = (255, 255, 255), (149, 149, 149)


@pytest.mark.parametrize("family", sorted(uniforms.SHADES))
def test_shading_reproduces_every_set_on_the_owners_sheet(family):
    base_class = uniforms.BASE_CLASS[family]
    for color_set in range(64):
        shades = uniforms.ramp(PALETTE[base_class][color_set], family)
        for cls, color in shades.items():
            expected = PALETTE[cls][color_set]
            assert all(abs(a - b) <= 1 for a, b in zip(color, expected, strict=True)), (
                family,
                color_set,
                cls,
            )


def test_a_pure_white_is_shaded_like_the_sheets_own_white():
    jersey = uniforms.ramp(WHITE, "jersey_socks")
    assert jersey["e"] == WHITE and jersey["c"] == (217, 217, 217)


def sheet(parts):
    """A drawing on the sheet template: filled boxes, each inside a two-pixel outline."""

    def pixel(x, y):
        found = WHITE
        for (left, top, right, bottom), color in parts:
            if left - 2 <= x < right + 2 and top - 2 <= y < bottom + 2:
                found = color if left <= x < right and top <= y < bottom else OUTLINE
        return found

    return pixel


NAVY, ORANGE, GREY = (10, 30, 60), (230, 80, 20), (225, 220, 215)
ROAD_SHEET = [
    ((50, 20, 140, 105), NAVY),  # helmet
    ((142, 80, 147, 108), (5, 15, 35)),  # a facemask bar
    ((12, 120, 172, 248), WHITE),  # jersey, white and fully enclosed
    ((76, 175, 110, 228), NAVY),  # numbers
    ((40, 255, 145, 376), (30, 40, 65)),  # pants
    ((188, 254, 212, 370), (30, 40, 65)),  # pants stripe view
    ((196, 254, 204, 370), ORANGE),
    ((40, 380, 66, 451), WHITE),  # socks
    ((40, 414, 66, 424), NAVY),  # a sock stripe
    ((30, 456, 66, 488), WHITE),  # cleats
]


def test_measures_each_part_from_its_place_on_the_template():
    measured = uniforms.measure_pixels(sheet(ROAD_SHEET), 400, 500)
    assert measured["helmet"] == NAVY
    assert measured["helmet_stripe"] is None  # this sheet draws no helmet stripe view
    assert measured["facemask"] == (5, 15, 35)
    assert measured["jersey"] == WHITE  # white inside an outline is gear, not background
    assert measured["numbers"] == NAVY
    assert measured["pants"] == (30, 40, 65)
    assert measured["pants_stripe"] == ORANGE
    assert measured["cleats"] == WHITE
    socks = measured["socks"]
    assert socks[5] == WHITE and socks[418 - 380] == NAVY and socks[-5] == WHITE
    assert socks[0] is None  # the row against the pants' outline is all edge


def test_a_helmet_stripe_view_gives_the_stripe_color():
    parts = [*ROAD_SHEET, ((188, 21, 213, 61), NAVY), ((198, 21, 203, 61), ORANGE)]
    assert uniforms.measure_pixels(sheet(parts), 400, 500)["helmet_stripe"] == ORANGE


def test_plain_pants_have_no_stripe():
    parts = [p for p in ROAD_SHEET if p[1] != ORANGE]
    assert uniforms.measure_pixels(sheet(parts), 400, 500)["pants_stripe"] is None


def test_refuses_a_sheet_that_is_not_the_template():
    with pytest.raises(ValueError):
        uniforms.measure_pixels(lambda x, y: WHITE, 300, 500)


def test_a_sock_stripe_survives_shrinking_to_sprite_size():
    socks = [WHITE] * 30 + [NAVY] * 6 + [WHITE] * 35
    assert uniforms.sock_color(socks, 33 / 70) == NAVY
    assert uniforms.sock_color(socks, 0.0) == WHITE and uniforms.sock_color(socks, 1.0) == WHITE


def test_paint_takes_each_part_from_the_uniform_and_skin_from_the_set():
    uniform = {
        "helmet": NAVY,
        "helmet_stripe": None,
        "facemask": (5, 15, 35),
        "jersey": WHITE,
        "numbers": NAVY,
        "pants": GREY,
        "pants_stripe": ORANGE,
        "socks": [WHITE] * 71,
        "cleats": WHITE,
    }
    skin = {cls: PALETTE[cls][0] for cls in PALETTE}
    rows, regions = ["jcl", "kd#", "e##"], ["HJM", "P..", "0K."]
    painted = uniforms.paint(rows, regions, uniform, skin)
    assert painted[0] == [uniforms.ramp(NAVY, "helmet_pants")["j"], (217, 217, 217), (5, 15, 35)]
    assert painted[1] == [uniforms.ramp(ORANGE, "trim")["k"], tuple(PALETTE["d"][0]), (0, 0, 0)]
    assert painted[2] == [WHITE, uniforms.ramp(WHITE, "helmet_pants")["b"], (0, 0, 0)]
