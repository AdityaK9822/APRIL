# Open_INT — Architecture

## Flow
```
  ┌──────────── next_request() — polls only the enabled sources ────────────┐
  │  input()          typed line — only when GUI=0 (app mode reads no stdin)│
  │  voice.py         wake word ──► record-to-silence ──► mlx-whisper       │
  │  gui.py           window Send ──► queued, reply rendered on the timer   │
  └────────────────────────────────┬───────────────────────────────────────┘
                                   │  (mic closed before the turn)
                    ┌──────────────┴───────────────┐
            image_for(request)?              otherwise
                    │                              │
        ┌───────────▼───────────┐      ┌───────────▼────────────┐
        │ ask_about_image()     │      │ ask_command()          │
        │ screenshot / webcam / │      │ system prompt only,    │
        │ literal path → VLM    │      │ no history → ONE cmd   │
        └───────────┬───────────┘      └───────────┬────────────┘
                    │                              │
                    │                    confirm() if OPEN_INT_CONFIRM=1
                    │                    (app turn? the window answers it)
                    │                              │
                    │              subprocess.run(shell=True, timeout=60)
                    │                              │
                    └────────► print ─────◄────────┘
                               ├─► voice.speak() if VOICE=1
                               └─► reply.put(result) for an app turn
```

## Components (`main.py`)
| Piece | Role |
|-------|------|
| `client` / `MODEL` | OpenAI SDK + model from `.env`; defaults to Ollama + `gemma3:4b` |
| `SYS` | System prompt: "turn request into ONE shell command", seeded with `platform.system()` + `os.getcwd()` |
| `ask_command(request)` | One stateless completion; strips code fences; returns the command |
| `image_for(request)` | Literal file path → screenshot words. `None` means "this is a command request" |
| `ask_about_image(...)` | Sends `image_url` as a base64 `data:` URI. Prose answer, never a command |
| `next_request()` | The dispatcher — round-robin poll across enabled sources |
| `run_command(cmd)` | `subprocess.run(shell=True, timeout=60)`; combined output |
| `confirm(command, app_turn)` | `OPEN_INT_CONFIRM=1` gate; window > voice > typed |
| `_state()` / `_apply_setting()` | What the rail shows, and the runtime flags it may flip (VOICE imports lazily) |
| `_set_mic(want)` | Opens/closes the mic to match `VOICE`; on failure says why and turns voice off |
| `loop()` | The turn loop. A worker thread in GUI mode, the main thread when `GUI=0` |
| main `while` | Routes to image or command, runs it, prints `$ cmd` + output, optionally speaks |

## Components (`voice.py`, imported only when `VOICE=1`)
| Piece | Role |
|-------|------|
| `start()` / `stop()` | Open/close the mic — it stays shut the rest of the time. Called by `_set_mic` |
| `wake_detected()` | One mic frame (~32 ms) through Porcupine; pollable without spinning |
| `capture()` | Record until `SILENCE_FRAMES` quiet frames, transcribe with mlx-whisper |
| `listen()` | Convenience: `start` → wake-or-typed → `capture` → `stop` |
| `speak(text)` | Piper CLI → temp WAV → `afplay`; falls back to macOS `say` |
| `_pcm_to_float`, `_rms`, `_is_silent` | int16 frame helpers; covered by the self-check |

## Key behaviors
- No conversation history — each request is independent.
- The mic follows the live `VOICE` flag inside the poll loop, so the window's mic
  button turns voice on and off mid-poll without restarting anything.
- App mode (`GUI=1`, the default) reads no stdin: the window is the interface and
  the Activity pane is the terminal. `GUI=0` is the original terminal loop, untouched.
- Every command is echoed as `$ <command>` + output, so the user sees what ran.
- Window requests are queued into `next_request()`, not run on the UI thread —
  that is what keeps one turn at a time with the mic shut.
- **Turn-based**: STT, LLM, VLM and TTS never run simultaneously.
  `next_request()` closes the mic in a `finally` before returning.
- The dispatcher poll is cheap at idle because the mic blocks for about one
  32 ms frame.
- The VLM is on-demand only, on the screenshot path.

## What's NOT here
No socket and no server (the UI is in-process AppKit), no streaming, no async, no persistence, no conversation history, no
retry/backoff,
no barge-in (can't interrupt TTS by talking), no
sandboxing or allowlist on command execution. No camera input at all right now —
`vision.py` is in `parked/` and nothing imports it.
