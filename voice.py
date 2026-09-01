"""Voice I/O for APRIL — wake word + local STT (mlx-whisper) + local TTS (Piper).

Opt-in: main.py only imports this when VOICE=1. All heavy deps are imported here.
"""
import os
import subprocess
import sys
import select
import tempfile

import numpy as np

WHISPER_MODEL = os.getenv("WHISPER_MODEL", "mlx-community/whisper-base.en-mlx")
PIPER_VOICE = os.getenv("PIPER_VOICE", "en_US-lessac-medium")
WAKE_WORD = os.getenv("WAKE_WORD", "computer")
VOICES_DIR = os.path.join(os.path.dirname(__file__), "voices")

# ponytail: fixed RMS gate + frame count for end-of-speech. Tune these two if it
# cuts you off or never stops. Proper VAD (silero/webrtcvad) only if this annoys.
SILENCE_RMS = 400          # int16 RMS below this counts as silence
SILENCE_FRAMES = 28        # ~0.9s of silence ends the utterance (32ms/frame)
MAX_UTTERANCE_FRAMES = 320  # ~10s hard cap

_porcupine = None
_recorder = None


def _pcm_to_float(frames):
    """list[int] int16 samples -> float32 ndarray in [-1, 1), what whisper wants."""
    return np.asarray(frames, dtype=np.float32) / 32768.0


def _rms(frame):
    a = np.asarray(frame, dtype=np.float32)
    return float(np.sqrt(np.mean(a * a))) if a.size else 0.0


def _is_silent(frame, thresh=SILENCE_RMS):
    return _rms(frame) < thresh


def _stdin_line():
    """Return a typed line if one is waiting on stdin, else None (non-blocking)."""
    if select.select([sys.stdin], [], [], 0)[0]:
        return sys.stdin.readline().strip()
    return None


def _ensure_audio():
    global _porcupine, _recorder
    if _porcupine is not None:
        return
    import pvporcupine
    from pvrecorder import PvRecorder

    key = os.getenv("PICOVOICE_ACCESS_KEY")
    if not key:
        raise SystemExit(
            "Voice needs PICOVOICE_ACCESS_KEY in .env "
            "(free key: https://console.picovoice.ai)"
        )
    if WAKE_WORD.endswith(".ppn") or os.sep in WAKE_WORD:
        _porcupine = pvporcupine.create(access_key=key, keyword_paths=[WAKE_WORD])
    else:
        _porcupine = pvporcupine.create(access_key=key, keywords=[WAKE_WORD])
    _recorder = PvRecorder(frame_length=_porcupine.frame_length)


def start():
    """Open the mic. Pair with stop() — the mic stays shut the rest of the time."""
    _ensure_audio()
    _recorder.start()


def stop():
    if _recorder is not None:
        _recorder.stop()


def wake_detected():
    """Read one mic frame; True if the wake word just fired. Requires start().

    Blocks for one frame (~32ms), so polling this does not spin the CPU.
    """
    return _porcupine.process(_recorder.read()) >= 0


def capture():
    """Record until silence, then transcribe. Requires start()."""
    import mlx_whisper

    print("\nlistening…", flush=True)
    samples, quiet = [], 0
    while len(samples) < MAX_UTTERANCE_FRAMES * _porcupine.frame_length:
        frame = _recorder.read()
        samples.extend(frame)
        quiet = quiet + 1 if _is_silent(frame) else 0
        if quiet >= SILENCE_FRAMES:
            break
    text = mlx_whisper.transcribe(
        _pcm_to_float(samples), path_or_hf_repo=WHISPER_MODEL
    )["text"].strip()
    print(f"heard: {text}")
    return text


def listen():
    """Block until the wake word + a spoken utterance, or a typed line. Returns text.

    Mic is only open inside this call, so it can't self-trigger while the model
    thinks or while speak() is playing.
    """
    start()
    try:
        print(f"({WAKE_WORD!r} to talk, or just type) ", end="", flush=True)
        while True:
            typed = _stdin_line()
            if typed is not None:
                return typed
            if wake_detected():
                return capture()
    finally:
        stop()


def speak(text):
    text = text.strip()
    if not text:
        return
    wav = os.path.join(tempfile.gettempdir(), "april_tts.wav")
    try:
        subprocess.run(
            ["piper", "-m", PIPER_VOICE, "--data-dir", VOICES_DIR, "-f", wav],
            input=text, text=True, check=True, capture_output=True,
        )
        subprocess.run(["afplay", wav], check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        # ponytail: piper voice missing / CLI changed -> macOS `say`, still offline
        subprocess.run(["say", text])


if __name__ == "__main__":
    f = _pcm_to_float([0, 32767, -32768, 16384])
    assert f.dtype == np.float32 and -1.0 <= f.min() and f.max() < 1.0, f

    assert _is_silent(np.zeros(512, dtype=np.int16))
    assert not _is_silent((np.ones(512) * 5000).astype(np.int16))

    # end-of-utterance: SILENCE_FRAMES consecutive quiet frames should trip
    loud = (np.ones(512) * 5000).astype(np.int16)
    quiet_run = 0
    for frame in [loud] * 5 + [np.zeros(512, dtype=np.int16)] * SILENCE_FRAMES:
        quiet_run = quiet_run + 1 if _is_silent(frame) else 0
    assert quiet_run == SILENCE_FRAMES

    print("voice.py self-check OK")
