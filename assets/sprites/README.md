# Player sprites

Pixel art for Arbit's play animations. Owned by the project owner (OWN-024).

`source/player-clip-group.png` is the original sheet: 6 poses, in 32 color sets and 2 skin tones. `frames/` holds all 40 frames, those 6 poses plus 34 drawn from them, at the art's true size of about 32 pixels tall. `palette.json` gives every color class its color in each of the 64 sets, so one drawing serves every team.

## Previews

[`preview/all-frames.png`](preview/all-frames.png) shows every frame, with new frames labeled in yellow. Sample plays: [pass](preview/play-pass.gif), [run](preview/play-run.gif), [sack](preview/play-sack.gif), [field goal](preview/play-fg.gif) and [punt](preview/play-punt.gif).

Previews use a plain drawn field and sample situations. The app will use real plays and weekly field art, which stays private: Gridiron art is licensed for the invite-only app and must never enter this repository (OWN-015).

## Editing frames

A frame is a text grid under a `== name` line, one character per pixel, with `.` for empty. Letters are color classes:

| Letters | Meaning |
| --- | --- |
| `j` `n` `b` `a` | Helmet and pants, light to dark |
| `e` `c` `f` `h` | Jersey and socks, light to dark |
| `k` `i` `o` `q` `m` | Trim: stripes and numbers |
| `g` `d` | Skin, light and dark |
| `B` `C` | Ball, light and dark |
| `p` `l` `#` | Facemask greys and black outline |

`scripts/sprites/frames.py` loads and checks frames, and `tests/contracts/test_sprite_frames.py` keeps them valid. Rebuild the previews with:

```sh
uv run --no-project --with pillow --with numpy python scripts/sprites/preview.py
```
