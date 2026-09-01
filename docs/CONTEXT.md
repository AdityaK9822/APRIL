# Open_INT — Context

## What this is
A minimal local assistant: you give a request (typed or spoken), a
local model turns it into ONE shell command, it runs on the host Mac, and you see
`$ cmd` + output (and hear it, in voice mode). It launches as a native macOS
window — no terminal and no browser; an Activity pane in the window shows every
command as it runs. Requests about an image go to the
same model as a vision question instead, and get a spoken/printed answer.

## Layout
- `main.py` — the loop, the input dispatcher, and the command/image routing.
- `voice.py` — optional voice I/O.
- `parked/` — out of the backend for now: `vision.py` and its assets.
- `gui.py` — the app window (default), a fourth input source on the same dispatcher.
- `AGENTS.md` at the root (tool convention); `docs/` holds CONTEXT / ARCHITECTURE / ROADMAP.

## Goal
An always-available local assistant with real system access — inspect the machine,
run commands, automate small tasks — without sending data to a cloud provider.

## Current state (2026-08-29)
- **Model: `gemma3:4b` via Ollama, one model for both jobs** — command translation
  and image reasoning. Replaced `qwen2.5-coder:1.5b`, which has no vision.
- **Vision is parked** (2026-08-29): `vision.py` moved to `parked/`, nothing in
  `main.py` imports it, and its deps are commented out in `requirements.txt`.
  The app window still shows a Vision row, greyed out and unswitchable. Focus is
  voice. `parked/README.md` says how to reconnect it.
- `main.py` (~200 lines): dispatcher polls whichever input sources are enabled,
  routes the request to either a shell command or a vision question, optionally
  gates execution behind a confirmation, prints and optionally speaks the result.
- `voice.py` (`VOICE=1`, or the mic button in the window): Porcupine wake word → record-to-silence →
  mlx-whisper STT. Replies spoken with Piper (falls back to macOS `say`).
  Exposes `start/stop/wake_detected/capture` so the dispatcher can poll it.
  Voice can be turned on at runtime from the window's mic button — the module
  imports lazily and the dispatcher opens the mic on the next poll. If the mic
  cannot open (no `PICOVOICE_ACCESS_KEY`, no permission) the reason prints into
  the Activity pane and voice switches itself back off.
- Backend from `.env`: `OPENAI_API_KEY` / `OPENAI_API_BASE_URL` / `OPENAI_MODEL`.
  Point these at a bigger or cloud model to test — nothing else changes.
- `requirements.txt` splits core / voice-only / parked deps.

### Why Apple Vision and not MediaPipe (kept for when vision returns)
MediaPipe was the first choice. Its `1.0.1` wheel *does* install on Python 3.14,
but crashes on recognizer init here — `DrishtiMetalHelper ... Service is
unavailable`, with the CPU delegate explicitly requested and with the sandbox
off. Apple's Vision framework via `pyobjc` gives the same 21 landmarks, needs no
model download, and keeps everything in the one venv. Measured 12 ms/frame.

### Measured cost of the parked vision loop (M-series, 16GB)
| Stage | Cost |
|-------|------|
| hand pose (every frame) | ~12 ms |
| YOLO11n on MPS (every 12th frame) | ~13 ms steady, ~2.5s first call |
| model load + MPS warmup | ~3 s, once at startup |
Worst frame ≈ 25 ms against a 125 ms budget at 8 fps — lots of headroom.

## Running
```
./venv/bin/pip install -r requirements.txt
ollama pull gemma3:4b
./venv/bin/python main.py                       # app mode — opens the window
GUI=0 ./venv/bin/python main.py                 # old terminal loop

# voice mode:
mkdir -p voices && ./venv/bin/python -m piper.download_voices en_US-lessac-medium --data-dir voices
# add VOICE=1 + PICOVOICE_ACCESS_KEY to .env, then run main.py
```
Self-checks: `./venv/bin/python voice.py`, `./venv/bin/python gui.py`,
`./venv/bin/python parked/vision.py`.

**macOS permissions** — each is a one-time interactive grant, and the first run
is what triggers the prompt:
- **Microphone** (`VOICE=1`).
- **Screen Recording** — needed by `screencapture` for "what's on my screen".
  Without it `screencapture` exits with `could not create image from display`.
Grant these to whatever app hosts the terminal (Terminal, iTerm, VS Code).

First voice run downloads `whisper-base.en-mlx` (~150 MB). (Camera permission and
the YOLO weights only matter if you reconnect `parked/vision.py`.)

## Constraints / decisions
- No sandbox on command execution — full shell access is the point. The only
  guard is opt-in `OPEN_INT_CONFIRM=1`, off by default.
- Stdlib-only for system access (`os`, `platform`, `subprocess`).
- `main.py`, `voice.py`, `gui.py` are the sanctioned files. `gui.py`
  earned the fourth slot as a whole I/O surface, the same shape as the other two:
  opt-in, imported only when its flag is set, and ignorant of the model.
- The UI is in-process AppKit, so nothing listens on a socket. The browser
  dashboard it replaced needed a localhost-only bind to stay safe; this needs no
  such promise.
- Everything local: gemma3:4b, mlx-whisper, Piper, Porcupine.
- App mode owns the interface: stdin is not read at all (`GUI=1`), so the process
  survives a closed terminal. `GUI=0` restores the original `input()` loop.
- In app mode the dispatcher (and so the mic) runs on a worker thread,
  because AppKit requires the main thread. Still one turn at a time.
- Turn-based by design — STT, LLM, VLM, TTS and the camera are never live at the
  same time. The mic and camera are closed before a turn runs.
- The VLM is on-demand only (1–5 s per call), never in the camera loop.
