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
