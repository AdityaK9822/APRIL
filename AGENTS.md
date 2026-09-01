# Open_INT — Agent Instructions

Read `docs/CONTEXT.md` and `docs/ARCHITECTURE.md` first (roadmap in
`docs/ROADMAP.md`). This file stays at the project root by convention; the
rest of the docs live in `docs/`. This file is for any AI agent or model asked
to modify this project.

## Ground rules
- **Laziest solution that works.** `main.py`, `voice.py` and `vision.py` are the
  `gui.py` are the sanctioned files — each subsystem is self-contained and
  imported only when `VOICE=1` / `GUI=1`. No new file without a real reason.
  `parked/` holds what is out of the backend for now; nothing imports from it.
  Stdlib before dependencies. One line before fifty.
- **Don't neuter command execution.** Full shell access is a deliberate feature.
  Safety features are allowed only as opt-in (env var / flag), off by default.
- **Stdlib-only for system access:** `os`, `platform`, `subprocess`. New pip deps
  need a one-line justification in the PR/commit message. Add them to
  `requirements.txt`; voice-only deps stay marked as such.
- **Preserve the terminal echo** of every command run — the user must see what
  executed. That holds for window requests too: they print through the same
  `print`, which the Activity pane mirrors.

## When you change something
1. Update `docs/CONTEXT.md` "Current state" if behavior/model/backend changed.
2. Update `docs/ARCHITECTURE.md` if the flow or components changed.
3. Move the item from `docs/ROADMAP.md` to done, or add new deferred items there.
4. Leave `# ponytail:` comments on any deliberate corner cut (naming the ceiling).

## Testing
No framework. If you add non-trivial logic (a parser, a branch, a loop), leave one
runnable check — an `assert`-based `demo()` under `if __name__ == "__main__"` guard
or a single `test_*.py`. Trivial changes need no test.

## Model / backend notes
- Small local models (e.g. `qwen2.5-coder:1.5b`) are unreliable — they may add
  prose or fences around the command. `ask_command()` strips fences; don't add
  more workarounds, document swapping to a bigger model instead.
- Backend is env-driven: `OPENAI_API_KEY` / `OPENAI_API_BASE_URL` / `OPENAI_MODEL`
  in `.env`, defaulting to Ollama.

## Voice notes (`voice.py`, `VOICE=1`)
- All local: Porcupine (wake word) + mlx-whisper (STT) + Piper (TTS, `say` fallback).
- Needs a free `PICOVOICE_ACCESS_KEY`. `WAKE_WORD` is a built-in name or a `.ppn`
  path ("Hey April" is made in the Picovoice console).
- Mic is only open between `start()` and `stop()` — keep it that way (no
  self-trigger during LLM/TTS). `main._set_mic()` is the only caller now; it
  tracks the live `VOICE` flag so the window's mic button works mid-poll, and it
  catches `BaseException` on purpose — `_ensure_audio()` raises `SystemExit`,
  which would otherwise kill the worker thread in silence. Silence gate is two constants at the top.
- `wake_detected()` blocks one ~32 ms frame; that is what makes polling it cheap.
  Don't "optimise" it into a busy spin.

## App notes (`gui.py`, `GUI=1`)
- AppKit via pyobjc, which vision mode already required — no tkinter (that would
  need `brew install python-tk`), no web framework, no new dependency.
- **AppKit owns the main thread.** `gui.build()` and every UI call must happen
  there; the turn loop runs on a worker thread. The `_App.tick_` timer is the one
  place worker output crosses over — keep it that way and you need no locks.
- Plain Python helpers on `_App` need `@objc.python_method`, or pyobjc tries to
  expose them as selectors and refuses the ones taking extra arguments.
- Layer colours come from `_cg()` (Quartz), never `NSColor.CGColor()` — the
  latter warns on every call, and stderr is teed into the Activity pane.
- **App mode is the default** (`GUI=1`). It reads no stdin, so nothing may call
  `input()` on that path — the Activity pane is the terminal and the window's
  close button is the way out. `GUI=0` keeps the original terminal loop working;
  don't break it.
- Rail toggles are runtime-only; only the settings sheet writes `.env`.
  `merge_env` and the scrollback cursor are pure and self-checked.

## Vision is parked
`vision.py` lives in `parked/` and nothing in the backend imports it. Do not wire
it back in as a side effect of another change — the focus is voice. The app
window keeps a greyed-out Vision row on purpose (`"vision" not in state` is what
marks it parked); `parked/README.md` has the reconnect steps.
