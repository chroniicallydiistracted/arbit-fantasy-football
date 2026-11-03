# Player sprites

Pixel art for Arbit's play animations. Owned by the project owner (OWN-024, OWN-026).

`source/player-clip-group.png` is the original sheet: 6 poses, in 32 team color sets and 2 skin tones. Its rows are the 32 NFL teams in alphabetical order by city, Arizona first. `frames/base.txt` holds those 6 poses at the art's true size of about 32 pixels tall. Every other frame was drawn by PixelLab from one of them and approved by the owner (OWN-026). [How they were made](../../scripts/sprites/pixellab/README.md).

`palette.json` gives every color class its color in each of the 64 sets, so one drawing serves every team and both skin tones.

## The ball

Frames never include the ball (OWN-027). `ball.txt` is the one ball sprite, taken from the owner's `arm` pose, and a renderer draws it over the frame. `anchors.json` gives each frame's near and far hands and its chest, in pixels from the frame's top left, plus `lift`, how far the frame's lowest pixel sits above the ground for jumps and dives. Carriers hold the ball at the chest; passers and punters hold it in the near hand.

## Real uniforms

`regions/` mirrors `frames/`: for each pixel, which part of the uniform it shows. The letters are `H` helmet, `M` facemask, `J` jersey, `P` pants, `K` cleats, `0`–`9` socks from top to bottom, and `.` for anything else. The sheet's classes can't say this themselves, because its teams wore one color on helmet and pants and another on jersey and socks. `scripts/sprites/pixellab/regions.py` makes the maps from the skeletons the frames were drawn from.

`scripts/sprites/uniforms.py` measures a uniform from its Gridiron sheet and paints a frame with it, shading each color the way this sheet does (OWN-028). Gridiron sheets are licensed for personal use only, so measured colors and painted renders stay in ignored `data/` folders (OWN-015).

## Previews

[`preview/all-frames.png`](preview/all-frames.png) shows every frame, with frames drawn from the originals labeled in yellow. Sample plays: [pass](preview/play-pass.gif), [run](preview/play-run.gif), [sack](preview/play-sack.gif), [field goal](preview/play-fg.gif) and [punt](preview/play-punt.gif).

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
| `r` | One stray brown pixel in `run2`, the same in every set |

`scripts/sprites/frames.py` loads and checks frames, and `tests/contracts/test_sprite_frames.py` keeps them valid. Rebuild the previews with:

```sh
uv run --no-project --with pillow --with numpy python scripts/sprites/preview.py
```
