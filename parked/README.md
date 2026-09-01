# Parked

Out of the backend, kept for when it comes back.

## `vision.py` — camera perception (was `VISION=1`)
Apple Vision hand gestures + YOLO11n objects at 8 fps. Disconnected on
2026-08-29 to focus on voice; nothing in `main.py` imports it any more, and the
app window still shows a Vision row, greyed out.

Its assets sit beside it: `yolo11n.pt` (YOLO weights, re-downloadable) and
`gesture_recognizer.task` (a MediaPipe leftover from the approach that was
dropped — see "Why Apple Vision and not MediaPipe" in `docs/CONTEXT.md`).

Still self-contained and still self-checking: `./venv/bin/python parked/vision.py`.

To reconnect: restore the `VISION` flag and the `import vision` in `main.py`,
put back the vision branches in `image_for()`, `next_request()` and `confirm()`,
and drop the parked handling from the Vision row in `gui.py`.
