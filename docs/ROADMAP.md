# Open_INT — Roadmap / Future Updates

Ordered rough priority. Move items to "Done" with a date when shipped.

## Next
- [ ] Get a free `PICOVOICE_ACCESS_KEY` into `.env` — the mic button loads voice
      and asks for the mic, and this is the one thing standing between it and a
      working wake word. The failure already reports itself in the Activity pane.
- [ ] Then exercise the whole wake-word → record → transcribe → speak path in the
      app window; it has only ever been run from the terminal.

## Later
### Parked with `parked/vision.py` — reconnect before picking these up
- [ ] Hold a real thumbs-up in front of an uncovered camera and confirm the event
      fires. Everything else was verified: the camera loop holds 8.0 fps, Apple
      Vision returns 21 named joints on a real photo, YOLO returns real classes
      ('person', 'cell phone'). Only a deliberate live gesture is untested.
- [ ] Tune `EXTENDED_RATIO` / `MIN_JOINT_CONF` against a real hand — `classify()`
      is only self-checked against synthetic landmarks. On an incidental hand in
      a photo the joint confidences came back 0.0-0.18, well under the 0.3 floor.
- [ ] Show a live camera preview in the rail (the pane is a placeholder today).

### Voice and the app
- [ ] App: stream long command output instead of rendering it in one block.
- [ ] Package the window as a real .app bundle so it gets a Dock icon and can be
      launched without the venv python on the command line.
- [ ] Voice: barge-in (interrupt TTS by talking).
- [ ] Voice: LLM-summarise long command output before speaking it.
- [ ] Voice: `openWakeWord` as a no-API-key alternative to Porcupine.
- [ ] Persist history / bring back a conversational mode; `--resume` to reload.
- [ ] `/model` and `/backend` slash commands to switch mid-session.
- [ ] Handle Ctrl-C gracefully instead of a traceback (app mode exits cleanly via
      closing the window; only the `GUI=0` terminal loop still tracebacks).

## Considered, not doing (yet)
- Sandboxing / allowlist — conflicts with the "full access" design goal. Revisit
  only if the tool is exposed beyond the local user.
- VLM in the camera loop — far too slow. On-demand only.
- Holding a second model resident for coding — `gemma3:4b` does both jobs.
- Async / multi-agent orchestration — no use case.

## Done
- 2026-08-29 — Mic button in the composer turns voice mode on and off at runtime:
  `voice` imports lazily, the dispatcher opens/closes the mic on the next poll,
  and a mic that won't open reports why and switches voice back off instead of
  killing the worker thread.
- 2026-08-29 — Disconnected vision from the backend: `vision.py` and its assets
  moved to `parked/`, its deps commented out, its docs folded into the parked
  section. The app window keeps a greyed-out Vision row. Focus is voice.
- 2026-08-29 — Migrated the browser dashboard to a native macOS window
  (`gui.py`, AppKit via the pyobjc already there for vision). Same seams, same
  dispatcher; the HTTP server and `web.py` are gone. AppKit takes the main
  thread, so the turn loop moved to a worker thread.
- 2026-08-29 — App mode is the default launch: browser opens automatically, no
  stdin is read, stdout is mirrored into an Activity pane (a virtual terminal)
  and a Quit button stops the process. (Superseded the same day by the native
  window; the browser step is kept here because it is what the dispatcher seams
  were designed against.)
- 2026-08-29 — Web UI (`WEB=1`, `web.py`, since replaced): stdlib `http.server` on 127.0.0.1
  serving one page — transcript, composer, source rail, browser confirm gate,
  settings dialog. Requests join the same dispatcher queue; no new deps.
- 2026-08-27 — Added `run_command` tool (os/platform/subprocess system access).
- 2026-08-27 — Added context docs (CONTEXT, ARCHITECTURE, AGENTS, ROADMAP).
- 2026-08-29 — Dropped the tool-call loop for a stateless "request -> ONE
  command" translator (`ask_command`); fences stripped for weak models.
- 2026-08-29 — Backend config from `.env` (`OPENAI_*`), `requirements.txt`.
- 2026-08-29 — Voice mode (`VOICE=1`, `voice.py`): Porcupine wake word +
  mlx-whisper STT + Piper TTS, all local; typing still works.
- 2026-08-29 — Moved CONTEXT / ARCHITECTURE / ROADMAP into `docs/`.
- 2026-08-29 — Switched to `gemma3:4b` for both command translation and image
  reasoning; added the image path (screenshot / webcam / literal file path).
- 2026-08-29 — Vision mode (`VISION=1`, `vision.py`): Apple Vision hand gestures
  + YOLO11n objects, 8 fps, 640px frames. MediaPipe evaluated and dropped —
  its 3.14 wheel installs but crashes on init (Metal helper unavailable).
- 2026-08-29 — Input dispatcher in `main.py` across text / voice / vision,
  with the gesture→action map.
- 2026-08-29 — Opt-in command confirmation (`OPEN_INT_CONFIRM=1`).
