# Live motion calibration and replay review

LV-003 and LV-005 apply. This follows the approved Live animation rebuild design and the owner's request to preserve plausible movement even when play duration is known. The renderer, play scripts and private review use field yards and elapsed seconds. NGS is offline evidence. Live playback still uses stored NFL play-by-play and roster context.

- Measure snap release, projected field dimensions, horizontal pass speed, first contact and score follow-through. Keep the game split and uncertain event coverage explicit.
- Add regressions in `test_live_motion.py` for snap release, moving catches and goal-line crossing, joint contact and touchback continuation. Update the original fallback where it can put a stationary carrier at the tackle spot.
- In `motion.py`, `motion_pass.py` and `motion_kick.py`, retain official spots as event anchors and solve plausible movement through them. Separate play timing from follow-through. Keep every supported credit on the same actor timeline. In `motion_scene.ts`, preserve field-space rendering and resolve rolling/bouncing with deceleration.
- Compare the rebuilt replay with the deployed baseline and with available tracking on a common field and snap-relative timebase. Manually review actual browser renders at real playback speed and inspect sequences around reported failures. Run the broader Python and browser checks after visual iteration, then document coverage and limits in the handoff.
