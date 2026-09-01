import base64
import mimetypes
import os
import platform
import re
import select
import subprocess
import sys
import tempfile
import threading

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY", "ollama"),
    base_url=os.getenv("OPENAI_API_BASE_URL", "http://localhost:11434/v1"),
)
MODEL = os.getenv("OPENAI_MODEL", "gemma3:4b")  # does both commands and images

VOICE = os.getenv("VOICE") == "1"
GUI = os.getenv("GUI", "1") == "1"  # the app is the interface; GUI=0 = old terminal loop
CONFIRM = os.getenv("OPEN_INT_CONFIRM") == "1"
if VOICE:
    import voice
if GUI:
    import gui

SYS = (
    f"You translate a request into ONE {platform.system()} shell command. "
    f"cwd is {os.getcwd()}. Reply with ONLY the command, no explanation, no code fences. "
    "Examples: 'where am i' -> pwd ; 'launch Safari' -> open -a Safari"
)

IMAGE_PATH_RE = re.compile(r"[\w./~-]+\.(?:png|jpe?g|webp|gif)\b", re.I)
SCREEN_WORDS = ("screen", "screenshot", "display", "this window", "what's on my")


def ask_command(request):
    reply = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYS},
            {"role": "user", "content": request},
        ],
    ).choices[0].message.content.strip()
    # strip fences if the model adds them anyway
    return re.sub(r"^```\w*\n?|\n?```$", "", reply).strip()


def screenshot(name="open_int_screen.png"):
    path = os.path.join(tempfile.gettempdir(), name)
    subprocess.run(["screencapture", "-x", path], check=True)
    return path


def image_for(request):
    """Path to an image this request is about, or None if it wants a command.

    A real file path in the request wins; else 'screen' words grab a screenshot.
    """
    match = IMAGE_PATH_RE.search(request)
    if match and os.path.exists(os.path.expanduser(match.group())):
        return os.path.expanduser(match.group())
    low = request.lower()
    if any(w in low for w in SCREEN_WORDS):
        return screenshot()
    return None


def ask_about_image(request, path):
    """Ask the VLM about an image. Returns prose — this path never runs commands.

    ponytail: on-demand only (1-5s per call).
    """
    mime = mimetypes.guess_type(path)[0] or "image/png"
    with open(path, "rb") as f:
        url = f"data:{mime};base64,{base64.b64encode(f.read()).decode()}"
    return client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": [
            {"type": "text", "text": request},
            {"type": "image_url", "image_url": {"url": url}},
        ]}],
    ).choices[0].message.content.strip()


def run_command(command):
    """Run one shell command, return its combined output.

    ponytail: full shell access, no allowlist, no sandbox — that is the point.
    OPEN_INT_CONFIRM=1 is the opt-in guard.
    """
    try:
        out = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=60)
        return (out.stdout + out.stderr).strip() or f"(exit {out.returncode})"
    except subprocess.TimeoutExpired:
        return "(timed out after 60s)"


_mic_open = False


def _set_mic(want):
    """Open or close the mic to match the live VOICE flag.

    ponytail: voice.start() raises when the Picovoice key or mic permission is
    missing, and _ensure_audio() raises SystemExit — which in a worker thread
    kills it silently and leaves a window that looks fine and answers nothing.
    So catch everything, say what happened, and turn voice back off rather than
    leaving a switch that lies.
    """
    global VOICE, _mic_open
    if want == _mic_open:
        return
    try:
        voice.start() if want else voice.stop()
        _mic_open = want
    except BaseException as exc:  # SystemExit included, deliberately
        print(f"[voice off — {exc}]")
        VOICE = False
        _mic_open = False


def _typed():
    """A typed line if one is already waiting, else None (never blocks)."""
    return sys.stdin.readline().strip() if select.select([sys.stdin], [], [], 0)[0] else None


def next_request():
    """Block until an enabled input source produces a request.

    Returns `(text, reply)` — `reply` is a queue the browser is waiting on, or
    None for a local request.

    ponytail: naive round-robin poll, no threads. The mic blocks ~one 32 ms
    frame, so this costs nothing at idle, and it is closed before the turn runs —
    STT, LLM, VLM and TTS are never live at the same time.
    """
    if not (VOICE or GUI):
        return input("You: "), None

    ways = ([f"say {voice.WAKE_WORD!r}"] if VOICE else []) + ([] if GUI else ["type"])
    if ways:  # in app mode with no mic there is nothing to prompt for
        print(f"({' / '.join(ways)}) ", end="", flush=True)
    try:
        while True:
            _set_mic(VOICE)  # the mic follows the flag, so the UI can flip it mid-poll
            if GUI:
                if gui.quit_requested():
                    return "exit", None
                asked = gui.take()
                if asked is not None:
                    return asked
            if _mic_open and voice.wake_detected():
                return voice.capture(), None
            typed = None if GUI else _typed()
            if typed is not None:
                return typed, None
    finally:
        _set_mic(False)


def confirm(command, app_turn=False):
    """OPEN_INT_CONFIRM=1 gate. Returns True to run the command.

    ponytail: one answer channel at a time, by priority (window > voice > typed),
    to keep the turn-based rule. Typing works in every mode.
    """
    if app_turn:
        return gui.confirm(command)
    print(f"run `{command}`? [y/N] ", end="", flush=True)
    if VOICE:
        voice.speak(f"Run {command}?")

    if VOICE:
        voice.start()
        try:
            answer = voice.capture()
        finally:
            voice.stop()
        return answer.lower().startswith(("y", "sure", "ok", "go ahead"))

    return input().strip().lower().startswith("y")


def _state():
    """What the browser rail shows. Cheap — polled once a second."""
    return {
        "model": MODEL,
        "base_url": os.getenv("OPENAI_API_BASE_URL", "http://localhost:11434/v1"),
        "api_key": os.getenv("OPENAI_API_KEY", "ollama"),
        "voice": VOICE, "confirm": CONFIRM,
        "wake_word": voice.WAKE_WORD if VOICE else "",
    }  # no "vision" key — the window reads that as parked (see parked/vision.py)


def _apply_setting(key, on):
    """Flip a runtime flag from the browser. Returns a message if it can't."""
    global VOICE, CONFIRM, voice
    if key == "OPEN_INT_CONFIRM":
        CONFIRM = bool(on)
    elif key == "VOICE":
        if on and "voice" not in sys.modules:
            try:
                import voice  # light: Porcupine loads in start(), whisper in capture()
            except Exception as exc:
                return f"Voice could not load: {exc}"
        VOICE = bool(on)
    elif key == "VISION":
        return "Vision is parked — see parked/vision.py."


def loop():
    """One turn at a time, forever.

    ponytail: runs on a worker thread in GUI mode (AppKit owns the main thread)
    and on the main thread when GUI=0. Still one turn at a time, so the
    turn-based rule holds — the mic just opens on this thread now.
    """
    while True:
        request, reply = next_request()
        request = request.strip()
        if not request or request in {"exit", "quit"}:
            if reply is None:
                break
            reply.put({"kind": "note", "request": request, "output": "(nothing to do)"})
            continue

        source = "app" if reply is not None else "typed"
        image = image_for(request)
        if image:
            print(f"[looking at {image}]")
            answer = ask_about_image(request, image)
            print(answer)
            if VOICE:
                voice.speak(answer)
            if reply is not None:
                reply.put({"kind": "image", "source": source, "request": request,
                           "image": os.path.basename(image), "output": answer})
            continue

        command = ask_command(request)
        print(f"$ {command}")
        if CONFIRM and not confirm(command, app_turn=reply is not None):
            print("(skipped)")
            if reply is not None:
                reply.put({"kind": "note", "source": source, "request": request,
                           "output": "Cancelled — nothing ran."})
            continue

        output = run_command(command)
        print(output)
        if reply is not None:
            reply.put({"kind": "command", "source": source, "request": request,
                       "cmd": command, "output": output})


if GUI:
    gui.mirror()  # everything printed from here on also lands in the Activity pane
    gui.build(_state, _apply_setting)
    threading.Thread(target=loop, daemon=True).start()
    gui.run()  # blocks until the window closes
else:
    loop()
