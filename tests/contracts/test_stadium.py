"""The stadium fills the full-field view around the owner's field art, without changing the field."""

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("live_art", ROOT / "scripts/sprites/live_art.py")
assert SPEC is not None and SPEC.loader is not None
live_art = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(live_art)  # puts scripts/sprites on the path for the modules below
P = sys.modules["preview"]
S = sys.modules["stadium"]

RED, GOLD, BLUE, WHITE = (200, 30, 30), (240, 200, 40), (20, 60, 160), (230, 230, 230)
VOID, SKY = (14, 18, 16), S.SKY


def colors(neutral: bool = False) -> "S.Colors":
    return S.Colors(
        home=(RED, GOLD), away=(BLUE, WHITE), turf=S.turf_color(P.FIELD), neutral=neutral
    )


@pytest.fixture(scope="module")
def view():
    camera = P.Camera(P.WIDE.fixed_x, 0.0, P.WIDE)
    top, bottom, _board = live_art.frame_band(camera)
    box = (0, top, camera.shot.width, bottom)
    image = np.asarray(S.surround(camera, P.FIELD, (top, bottom), colors(), seed=401873037))
    inside = np.asarray(S.field_mask(camera, P.FIELD.size).crop(box)) == 255
    return camera, (top, bottom), image, inside


def test_nothing_the_browser_draws_is_left_empty(view):
    _camera, _band, image, inside = view
    around = image[~inside]
    assert around.size, "the band shows space around the field"
    for empty in (VOID, SKY):
        assert not (around == empty).all(axis=-1).any(), empty


def test_the_owners_field_art_is_kept_exactly(view):
    camera, (top, bottom), image, inside = view
    field = np.asarray(camera.ground().crop((0, top, camera.shot.width, bottom)))
    assert inside.mean() > 0.4
    assert (image[inside] == field[inside]).all()


def test_the_sideline_turf_continues_the_field_without_a_seam(view):
    camera, (top, _bottom), image, _inside = view
    far = round(min(y for _x, y in camera.field_corners())) - top
    centre = camera.shot.width // 2
    beyond, within = image[far - 4, centre].astype(int), image[far + 4, centre].astype(int)
    assert np.abs(beyond - within).max() <= 8


def test_a_game_always_gets_the_same_stadium_and_games_differ(view):
    camera, (top, _bottom), image, _inside = view
    band = (top, top + 80)  # stands
    again = np.asarray(S.layer(camera, band, colors(), seed=401873037))
    other = np.asarray(S.layer(camera, band, colors(), seed=401873038))
    assert (again == image[:80]).all()
    assert (other != again).any(axis=-1).mean() > 0.2


def shares(image: np.ndarray) -> tuple[float, float]:
    """Of all pixels, the share that reads as the red home color and as the blue visitors' color."""
    rgb = image.reshape(-1, 3).astype(int)
    red = (rgb[:, 0] > rgb[:, 1] + 30) & (rgb[:, 0] > rgb[:, 2] + 30)
    blue = (rgb[:, 2] > rgb[:, 0] + 30) & (rgb[:, 2] > rgb[:, 1] + 10)
    return red.mean(), blue.mean()


def test_home_fans_fill_the_stands_and_a_neutral_site_splits_them(view):
    camera, (top, _bottom), _image, _inside = view
    band = (top, top + 160)
    home_red, home_blue = shares(np.asarray(S.layer(camera, band, colors(), seed=7)))
    neutral_red, neutral_blue = shares(
        np.asarray(S.layer(camera, band, colors(neutral=True), seed=7))
    )
    assert home_red > 4 * home_blue
    assert 0.6 < neutral_red / neutral_blue < 1.6


def test_a_neutral_site_wall_carries_no_teams_colors(view):
    camera, _band, _image, _inside = view
    far = min(y for _x, y in camera.field_corners())
    wall = camera.project(50, S.WALL / 2, S.FAR_WALL)[1]
    assert wall < far
    row = (round(wall), round(wall) + 1)
    home, neutral = (
        np.asarray(S.layer(camera, row, colors(site), seed=7))[0, 900:1020].astype(int)
        for site in (False, True)
    )
    assert (home[:, 0] > home[:, 2] + 30).mean() > 0.8
    assert (np.ptp(neutral, axis=-1) < 16).mean() > 0.8


# A home stadium's own design (OWN-050), from a small made-up spec: the real ones are measured
# from the owner's private references and never committed.
V = sys.modules["venues"]
GREEN = [20, 210, 40]


def design(indoor: bool = False) -> dict:
    stack = [
        {"from": 0.0, "to": 5.0, "kind": "concrete", "color": [200, 200, 196]},
        {"from": 5.0, "to": 14.0, "kind": "seats", "color": GREEN},
        {"from": 14.0, "to": 16.0, "kind": "suites", "color": [20, 20, 24]},
        {"from": 16.0, "to": 30.0, "kind": "seats", "color": GREEN},
        {"from": 30.0, "to": 80.0, "kind": "open", "color": [140, 175, 190]},
    ]
    return {"far": stack, "left": stack, "right": stack, "indoor": indoor}


SPEC = {
    "venues": {"home": design(), "shared:a": design(), "shared:b": design(indoor=True)},
    "by_stadium": {"HOM00": "home", "SHR00": {"AAA": "shared:a", "BBB": "shared:b"}},
}


def test_a_home_game_takes_its_stadium_and_a_shared_one_the_home_teams_configuration():
    assert V.venue_for("HOM00", "XYZ", SPEC) is SPEC["venues"]["home"]
    assert V.venue_for("SHR00", "BBB", SPEC) is SPEC["venues"]["shared:b"]
    assert V.venue_for("SHR00", "CCC", SPEC) is None
    assert V.venue_for("ELSE00", "AAA", SPEC) is None
    assert V.venue_for(None, "AAA", SPEC) is None


def test_the_venue_design_shows_in_the_stands_and_the_field_is_kept(view):
    camera, (top, bottom), _image, inside = view
    image = np.asarray(S.surround(camera, P.FIELD, (top, bottom), colors(), 7, design()))
    field = np.asarray(camera.ground().crop((0, top, camera.shot.width, bottom)))
    assert (image[inside] == field[inside]).all()
    assert not (image[~inside] == VOID).all(axis=-1).any()
    # The stands above the far wall: the venue's green seats, where the generic bowl is red.
    wall = round(camera.project(50, 0, S.FAR_WALL)[1]) - top - 6
    generic = np.asarray(S.surround(camera, P.FIELD, (top, bottom), colors(), 7))

    def green(pixels: np.ndarray) -> float:
        rgb = pixels[:wall].reshape(-1, 3).astype(int)
        return float(((rgb[:, 1] > rgb[:, 0] + 40) & (rgb[:, 1] > rgb[:, 2] + 40)).mean())

    assert green(image) > 0.1
    assert green(generic) < green(image) / 4


def test_under_a_roof_the_open_part_of_the_design_is_roof_not_sky(view):
    camera, (top, _bottom), _image, _inside = view
    band = (top, top + 120)
    outdoor = np.asarray(S.layer(camera, band, colors(), 7, design()))
    indoor = np.asarray(S.layer(camera, band, colors(), 7, design(indoor=True)))
    assert (outdoor == SKY).all(axis=-1).any()
    assert not (indoor == SKY).all(axis=-1).any()


def test_a_thick_slab_beside_an_end_zone_takes_the_far_stands_design():
    far = design()["far"]
    end = [
        {"from": 0.0, "to": 5.0, "kind": "seats", "color": [10, 10, 200]},
        {
            "from": 5.0,
            "to": 12.0,
            "kind": "suites",
            "color": [5, 5, 5],
        },  # a video board, seen large
        {"from": 12.0, "to": 13.0, "kind": "ribbon", "color": [250, 240, 90]},
    ]
    cleaned = V._end(end, far)
    assert cleaned[0]["color"] == [10, 10, 200]  # the end's own seats stay
    assert cleaned[1]["kind"] == "seats" and cleaned[1]["color"] == GREEN
    assert cleaned[2]["kind"] == "ribbon"
