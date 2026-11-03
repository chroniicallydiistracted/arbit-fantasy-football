# Real uniforms on the sprites — 2026-11-03

The owner's direction (OWN-028): "Do not infer the uniform colors. I have all 250 renditions and combinations of uniforms for every team in 2026." They added the set to ignored `data/Gridiron_2026_Uniforms`. It is Gridiron art under the private personal-use permission (OWN-015), so the sheets, the colors measured from them and anything painted with them stay out of Git.

**Result:** every frame can now be painted in the uniform a team actually wore. Each color is measured from that uniform's sheet at a fixed place on Gridiron's template. The shading follows the owner's original sprite sheet. All 202 single-version sheets measured with no failures, and each was checked by eye beside the stand and run frames painted from it. The seven CHI at SEA plays were re-rendered in what Gridiron's week 8 page lists for that game.

## What the owner's set holds

The manifest lists 260 sheets for 32 teams. Of these, 55 are `TBA` placeholders and are never used as real. Another 202 are 400×500 single-version sheets. The last 3 (`DAL_AA`, `DAL_AA2` and `NE_HH`) are 1280×1600 animated GIFs that alternate between two versions of the uniform, such as navy socks and white socks. Nothing on the page says which version was worn. Measuring refuses those three unless a version is named.

## Which uniform a game used

Gridiron's week page is the source. Rechecked on 2026-11-03, week 8 lists CHI at SEA (event 401873036) with Chicago `B2` (white jersey, navy pants), Seattle `E` (navy jersey, grey pants) and field `SEA_2023-2026^3`. On 2026-10-31 Chicago was still TBA and the field unlisted. The renders from 2026-11-02 used a guessed field (`^1`) and a white stand-in for Chicago; both are replaced.

## Why the frames needed a map

The owner's sheet gives helmet and pants one set of color classes, and jersey and socks another, because every team on it wore one color on both. Real uniforms don't: Seattle `E` has a navy helmet and grey pants, and Chicago `B2` a white jersey and white socks with navy and orange stripes.

`assets/sprites/regions` now says which part of the uniform each pixel shows: helmet, facemask, jersey, pants, socks (with height down the sock) or cleats. `scripts/sprites/pixellab/regions.py` assigns each pixel to the nearest bone of the skeleton its frame was drawn from, choosing only among the parts its color class can be. For example, a helmet-or-pants pixel goes to whichever of the head and the thighs is nearer. The six originals use their hand-placed joints. `arm` has no skeleton, so it is split by height. All 59 maps were checked by eye, including the falls and the dives.

## How colors are measured

`scripts/sprites/uniforms.py` reads these places on the 400×500 template.

| Part | Where | Rule |
| --- | --- | --- |
| Helmet, jersey, pants | The front views | The most common color, with near-identical colors merged |
| Helmet stripe | The top-view swatch, inside its frame | The most common color that differs from the shell, or none if the sheet draws no swatch |
| Facemask | The front bars | The most common color that isn't background or outline |
| Numbers | The front "11" | The most common color that differs from the jersey |
| Pants stripe | The side swatch | The most common color that differs from the pants |
| Socks | Down the front lower leg | Each row's color, so stripes keep their height |
| Cleats | The front cleat | The most common color |

Background is the white reachable from the sheet's edges, so white gear inside an outline counts as gear. Outlines and edge blends are left out by counting only pixels whose neighbours match. A trim must differ from the color under it and cover at least 4% of its place.

## How colors are shaded

The owner's sheet shades every set with fixed ratios, and `ramp` reproduces all 64 sets within one level:

| Family | Highlight | Shadows | Lightest |
| --- | --- | --- | --- |
| Helmet and pants | ×1.234 | ×0.85 | Highlight blended 31% toward white |
| Jersey and socks | ×1.177 | ×0.622, ×0.41 | |
| Trim | ×1.234 | ×0.85, ×0.43 | Highlight blended 31% toward white |
| Facemask | ×1.887 | | |

A measured color is darkened only as far as needed for its highlight to fit, as the sheet does for its own whites (base 217, highlight 255).

## Encoding

GIFs allow 256 colors. The old encoder chose 128 per frame and turned Chicago's orange stripe into the first-down line's yellow and its white jersey green-grey. Every sprite color is now kept exactly, and the field shares the remaining slots, chosen from all of a play's frames at quarter size. Identical frames now merge without changing a play's length, and the files are 6–87% smaller (0.5–10.2 MB).

## Limits

- **One trim color per part.** Jersey trim is the number color, so Seattle's lime shoulders show as its grey number color. Helmet logos, thin piping and patterns like Seattle's feathered pants stripe are too thin to measure and are not drawn.
- **Socks are about six pixels tall.** A stripe survives if it fills a quarter of the stretch one pixel covers, so Chicago's navy, orange and navy stripes come out as an orange and a navy pixel row.
- **Black uniforms** go almost to the black outline, as black jerseys do on the owner's own sheet.
- **Skin tones** are still placeholders, alternated by ESPN id. Nothing here measures a real player.
- **No sync lane yet.** Which uniform a game used comes from a manual read of the week page.
