# PixelLab frame pipeline

How the frames in `assets/sprites/frames` beyond the six originals were made (OWN-026, ENG-026). PixelLab's skeleton animator redraws one of the owner's original frames into poses given as joints. The owner owns the output under PixelLab's terms.

Run everything from the private work folder `data/sprites/pixellab-test`, which holds the raw downloads and is not committed. The PixelLab key is read from Claude Code's local config by `mcp.py` and is never written anywhere else.

## Steps

1. **Poses.** `poses2.py` holds every pose: joints placed by hand from the originals' pixels, then angles for each new frame. `python poses2.py batches` writes one file per batch; `overlay2.py` draws them as stick figures to check before spending.
2. **Key colors.** The reference frame is recolored to `key-palette.json`: the owner's Arizona colors, with the four black trims and the two whites made distinct so every pixel maps back to one of the 21 color classes.
3. **Generate.** `run_all.py BATCH ...` submits batches one at a time (the trial allows one job) and `fetch.py` downloads the frames. A batch of 4 to 14 frames costs 3 generations.
4. **Convert.** `assemble.py staging BATCH ...` maps colors to classes (`convert.py`), removes smears, specks and any ball the model drew, applies the reviewed hand fixes in `MANUAL`, and records each frame's hands, chest and lift. The approved fall keeps its Arizona pixels and takes ambiguous classes from a key redraw (`hybrid.py`).
5. **Review.** `review.py BATCH` shows raw output beside two recolored teams; `teams.py` renders every frame in all 64 color sets; `showcase.py` plays each motion with the ball.
6. **Install.** `install.py staging` writes the frame files, `assets/sprites/anchors.json` and `assets/sprites/ball.txt`. The six originals in `base.txt` are never touched.
7. **Regions.** `regions.py` writes `assets/sprites/regions`, saying which uniform part each pixel shows, from the skeleton each frame was drawn from. `regions.py check` draws them for review. Rerun it whenever frames change.

## Known limits

The model drifts colors on about half the pixels; most land within reach of the right class. It also draws motion streaks and sometimes the ball, and those are removed. Hand fixes are listed in `assemble.py` by frame, class and pixel range, so each can be checked or undone.
