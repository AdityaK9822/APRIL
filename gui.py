"""The app window (`GUI=1`, on by default) — a native macOS UI, no browser.

ponytail: AppKit through pyobjc, which vision.py already depends on, so this
costs no new dependency (tkinter would have needed `brew install python-tk`).

AppKit owns the main thread, so main.py runs its dispatcher loop on a worker
thread and everything here is pulled by one repeating timer on the main thread:
new stdout lines, results, vision events, the pending confirm gate. That keeps
every UI touch on the main thread without a single lock.
"""

import os
import queue
import sys
import threading
from collections import deque

import objc
from AppKit import (
    NSApplication, NSApplicationActivationPolicyRegular, NSAttributedString,
    NSBackingStoreBuffered, NSBezelStyleRounded, NSColor, NSFont, NSImage,
    NSImageView, NSMakeRect, NSMakeSize, NSObject, NSScrollView, NSSwitch,
    NSTextField, NSTextView, NSTimer, NSView, NSWindow,
    NSWindowStyleMaskClosable, NSWindowStyleMaskMiniaturizable,
    NSWindowStyleMaskResizable, NSWindowStyleMaskTitled,
    NSFontAttributeName, NSForegroundColorAttributeName, NSControlStateValueOn,
    NSViewWidthSizable, NSViewHeightSizable, NSLineBreakByWordWrapping,
    NSButton, NSAppearance, NSAlert,
)
from AppKit import NSMakeRange, NSMutableParagraphStyle, NSParagraphStyleAttributeName
from Quartz import CGColorCreateSRGB

TICK = 0.15               # seconds between UI pulls; nothing here is expensive
GATE_TIMEOUT = 120        # seconds a pending command waits for an answer
FLAGS = ("VOICE", "VISION", "APRIL_CONFIRM")
WINDOW = (1180, 820)

_requests = queue.Queue()  # (text, reply_queue) — drained by next_request()
_gate = {}                 # the command waiting for approval, if any
_status = {"objects": [], "gesture": None}
_lines = deque(maxlen=400)  # the Activity pane's scrollback
_seq = 0                    # lines ever written, so the pane can ask for new ones
_quit = threading.Event()
_info = lambda: {}          # noqa: E731 — set by build()
_apply = lambda k, v: None  # noqa: E731 — set by build()


# ---- called by main.py (same seams the dispatcher already used) -------------

def take():
    """One queued request as (text, reply_queue), or None. Never blocks."""
    try:
        return _requests.get_nowait()
    except queue.Empty:
        return None


def confirm(command):
    """Ask the window to approve `command`. Blocks the worker until it answers."""
    answered = threading.Event()
    _gate.update(cmd=command, event=answered, yes=False)
    try:
        answered.wait(GATE_TIMEOUT)
        return _gate.get("yes", False)
    finally:
        _gate.clear()


def note(objects=None, gesture=None):
    """Mirror a vision event into the rail. Cheap; called from the poll loop."""
    if objects is not None:
        _status["objects"] = objects
    if gesture is not None:
        _status["gesture"] = gesture


def quit_requested():
    return _quit.is_set()


def scrollback(since):
    """Terminal lines the pane has not shown yet, with a cursor for next time."""
    first = _seq - len(_lines)
    return {"seq": _seq, "lines": list(_lines)[max(0, since - first):]}


class _Tee:
    """stdout, mirrored into the Activity pane.

    ponytail: 400 lines of scrollback is plenty to monitor by. Anything attached
    to the real stdout still gets every byte.
    """

    def __init__(self, stream):
        self.stream = stream
        self._partial = ""

    def write(self, text):
        global _seq
        self.stream.write(text)
        wrote = False
        self._partial += text
        while "\n" in self._partial:
            line, _, self._partial = self._partial.partition("\n")
            _lines.append(line)
            _seq += 1
            wrote = True
        if wrote:
            # Quit goes through NSApplication.terminate_, which skips Python's
            # exit flush — so line-buffer by hand or a piped log loses the tail.
            self.stream.flush()

    def flush(self):
        global _seq
        if self._partial:  # a prompt with no newline — show it anyway
            _lines.append(self._partial)
            _seq += 1
            self._partial = ""
        self.stream.flush()

    def __getattr__(self, name):
        return getattr(self.stream, name)


def mirror():
    """Send everything printed to the Activity pane as well."""
    sys.stdout = _Tee(sys.stdout)
    sys.stderr = _Tee(sys.stderr)


# ---- .env ------------------------------------------------------------------

def merge_env(text, updates):
    """Existing .env text + {key: value} -> new text. Keeps order and comments."""
    lines = text.splitlines()
    left = dict(updates)
    for i, line in enumerate(lines):
        key = line.split("=", 1)[0].strip()
        if key in left:
            lines[i] = f"{key}={left.pop(key)}"
    return "\n".join(lines + [f"{k}={v}" for k, v in left.items()]).strip() + "\n"


def write_env(updates, path=".env"):
    text = open(path).read() if os.path.exists(path) else ""
    with open(path, "w") as f:
        f.write(merge_env(text, {k: ("1" if v else "0") if isinstance(v, bool) else v
                                 for k, v in updates.items()}))


def demo():
    """ponytail: the pure logic is the .env merge and the scrollback cursor."""
    assert merge_env("A=1\n# note\nB=2\n", {"B": "9"}) == "A=1\n# note\nB=9\n"
    assert merge_env("A=1\n", {"C": "3"}) == "A=1\nC=3\n"
    assert merge_env("", {"A": "1"}) == "A=1\n"
    assert merge_env("A = 1\n", {"A": "2"}) == "A=2\n"  # spaces around the key

    tee = _Tee(open(os.devnull, "w"))
    tee.write("one\ntwo\npart")
    assert scrollback(0) == {"seq": 2, "lines": ["one", "two"]}, scrollback(0)
    assert scrollback(1) == {"seq": 2, "lines": ["two"]}
    tee.flush()  # a newline-less prompt still shows
    assert scrollback(2) == {"seq": 3, "lines": ["part"]}
    assert scrollback(99)["lines"] == []  # a cursor ahead of us asks for nothing
    _lines.clear()
    print("gui.py self-check ok")


if __name__ == "__main__":
    demo()


# ---- the window ------------------------------------------------------------

def _parts(hexstr):
    h = hexstr.lstrip("#")
    return [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]


def _rgb(hexstr):
    return NSColor.colorWithSRGBRed_green_blue_alpha_(*_parts(hexstr), 1.0)


def _cg(hexstr):
    """Layer colours come from Quartz, not NSColor.CGColor() — the latter hands
    back an untyped pointer and pyobjc warns about it on every single call."""
    return CGColorCreateSRGB(*_parts(hexstr), 1.0)


PRIMARY, SURFACE, MUTED_BG = _rgb("#4f46e5"), _rgb("#ffffff"), _rgb("#f4f4f5")
BORDER, TEXT, TEXT_MUTED = _rgb("#e4e4e7"), _rgb("#18181b"), _rgb("#71717a")
DANGER, SUCCESS = _rgb("#dc2626"), _rgb("#16a34a")
CG = {"#16a34a": _cg("#16a34a"), "#4f46e5": _cg("#4f46e5"), "#ffffff": _cg("#ffffff"), "#f4f4f5": _cg("#f4f4f5"),
      "#e4e4e7": _cg("#e4e4e7"), "#18181b": _cg("#18181b")}
SUGGESTIONS = ["where am i", "how much disk space is left", "list the python files",
               "what's on my screen"]


def _font(size, weight=None, mono=False):
    """The design system asks for Inter; its own fallback is the system UI face,
    which on macOS is SF Pro — more native here than shipping a webfont."""
    if mono:
        return NSFont.monospacedSystemFontOfSize_weight_(size, weight or 0.0)
    return NSFont.systemFontOfSize_weight_(size, weight) if weight is not None \
        else NSFont.systemFontOfSize_(size)


MEDIUM, SEMIBOLD = 0.23, 0.3  # NSFontWeightMedium / NSFontWeightSemibold


class _Flipped(NSView):
    """Top-left origin, so every frame below reads the way the design does."""

    def isFlipped(self):
        return True


def _view(color=None, radius=0, border=False):
    """A plain surface. `color` is a hex string — layers want CGColor, not NSColor."""
    v = _Flipped.alloc().initWithFrame_(NSMakeRect(0, 0, 10, 10))
    v.setWantsLayer_(True)
    if color is not None:
        v.layer().setBackgroundColor_(CG[color])
    if radius:
        v.layer().setCornerRadius_(radius)
    if border:
        v.layer().setBorderWidth_(1.0)
        v.layer().setBorderColor_(CG["#e4e4e7"])
    return v


def _label(text, size=14, color=TEXT, weight=None):
    f = NSTextField.labelWithString_(text)
    f.setFont_(_font(size, weight))
    f.setTextColor_(color)
    return f


def _wrapping(text, size=13, color=TEXT_MUTED):
    f = _label(text, size, color)
    f.setLineBreakMode_(NSLineBreakByWordWrapping)
    f.setUsesSingleLineMode_(False)
    f.cell().setWraps_(True)
    return f


def _badge(text, color=TEXT_MUTED, fill=None):
    """The design system badge: 4px radius, 12px medium, 2px/4px padding."""
    holder = _view(fill or "#f4f4f5", radius=4)
    inner = _label(text, 12, color, MEDIUM)
    holder.addSubview_(inner)
    holder.inner = inner
    return holder


def _symbol(name):
    return NSImage.imageWithSystemSymbolName_accessibilityDescription_(name, None)


def _icon_button(symbol, target, action, tooltip):
    b = NSButton.buttonWithImage_target_action_(_symbol(symbol), target, action)
    b.setBezelStyle_(NSBezelStyleRounded)
    b.setToolTip_(tooltip)
    return b


def _set(view, x, y, w, h):
    view.setFrame_(NSMakeRect(x, y, w, h))


class _App(NSObject):
    """Everything on screen, plus the one timer that pulls the worker's output."""

    def init(self):
        self = objc.super(_App, self).init()
        self.seen = 0            # scrollback cursor
        self.awaiting = None     # reply queue for the request in flight
        self.gate_shown = None
        self.activity_open = True
        self.sheet = None
        return self

    # -- construction --------------------------------------------------------

    @objc.python_method
    def build(self):
        style = (NSWindowStyleMaskTitled | NSWindowStyleMaskClosable
                 | NSWindowStyleMaskMiniaturizable | NSWindowStyleMaskResizable)
        self.window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, *WINDOW), style, NSBackingStoreBuffered, False)
        self.window.setTitle_("APRIL")
        self.window.setMinSize_(NSMakeSize(880, 600))
        self.window.setDelegate_(self)
        # the design system is light-only; don't half-inherit a dark appearance
        self.window.setAppearance_(NSAppearance.appearanceNamed_("NSAppearanceNameAqua"))
        root = _view("#f4f4f5")
        self.window.setContentView_(root)
        self.root = root

        self._build_header(root)
        self._build_console(root)
        self._build_rail(root)
        self._layout()
        self.window.center()
        self.window.makeKeyAndOrderFront_(None)
        self.window.makeFirstResponder_(self.draft)

    @objc.python_method
    def _build_header(self, root):
        self.header = _view("#ffffff")
        root.addSubview_(self.header)
        self.header_rule = _view("#e4e4e7")
        self.header.addSubview_(self.header_rule)

        self.logo = NSImageView.alloc().init()
        self.logo.setImage_(_symbol("chevron.left.forwardslash.chevron.right"))
        self.logo.setContentTintColor_(PRIMARY)
        self.brand = _label("APRIL", 15, TEXT, SEMIBOLD)
        self.model_badge = _badge("…", TEXT)
        self.model_badge.inner.setFont_(_font(12, MEDIUM, mono=True))
        self.backend = _label("", 12, TEXT_MUTED)
        self.backend.setFont_(_font(12, mono=True))
        for v in (self.logo, self.brand, self.model_badge, self.backend):
            self.header.addSubview_(v)

        self.confirm_btn = NSButton.buttonWithTitle_target_action_(
            "Confirm before running", self, "toggleConfirm:")
        self.confirm_btn.setImage_(_symbol("shield"))
        self.confirm_btn.setBezelStyle_(NSBezelStyleRounded)
        self.confirm_btn.setButtonType_(2)  # NSButtonTypeSwitch behaviour, push look
        self.confirm_btn.setBordered_(True)
        self.settings_btn = _icon_button("gearshape", self, "openSettings:", "Settings")
        self.quit_btn = _icon_button("power", self, "quitApp:", "Quit APRIL")
        for v in (self.confirm_btn, self.settings_btn, self.quit_btn):
            self.header.addSubview_(v)

    @objc.python_method
    def _build_console(self, root):
        self.console = _view("#ffffff", radius=12, border=True)
        root.addSubview_(self.console)

        self.log_scroll, self.log = self._text_view("#ffffff", 24)
        self.console.addSubview_(self.log_scroll)

        # the confirm gate — a strip that appears only while a command waits
        self.gate = _view("#ffffff", radius=8, border=True)
        self.gate.layer().setBorderColor_(CG["#4f46e5"])
        self.gate_title = _label("Run this command?", 13, TEXT, MEDIUM)
        self.gate_cmd = _label("", 13, TEXT)
        self.gate_cmd.setFont_(_font(13, mono=True))
        self.gate_run = NSButton.buttonWithTitle_target_action_("Run", self, "gateYes:")
        self.gate_run.setBezelStyle_(NSBezelStyleRounded)
        self.gate_run.setBezelColor_(PRIMARY)
        self.gate_run.setKeyEquivalent_("\r")
        self.gate_cancel = NSButton.buttonWithTitle_target_action_("Cancel", self, "gateNo:")
        self.gate_cancel.setBezelStyle_(NSBezelStyleRounded)
        for v in (self.gate_title, self.gate_cmd, self.gate_run, self.gate_cancel):
            self.gate.addSubview_(v)
        self.console.addSubview_(self.gate)
        self.gate.setHidden_(True)

        self.footer_rule = _view("#e4e4e7")
        self.console.addSubview_(self.footer_rule)
        self.chips = []
        for text in SUGGESTIONS:
            b = NSButton.buttonWithTitle_target_action_(text, self, "chip:")
            b.setBezelStyle_(NSBezelStyleRounded)
            b.setFont_(_font(13))
            self.console.addSubview_(b)
            self.chips.append(b)

        self.draft = NSTextField.alloc().init()
        self.draft.setPlaceholderString_("Ask for something — it becomes one shell command")
        self.draft.setFont_(_font(14))
        self.draft.setTarget_(self)
        self.draft.setAction_("send:")
        self.mic_btn = _icon_button("mic", self, "toggleVoice:", "Voice mode")
        self.console.addSubview_(self.mic_btn)
        self.send_btn = NSButton.buttonWithTitle_target_action_("Send", self, "send:")
        self.send_btn.setBezelStyle_(NSBezelStyleRounded)
        self.send_btn.setBezelColor_(PRIMARY)
        self.console.addSubview_(self.draft)
        self.console.addSubview_(self.send_btn)

        self.activity_rule = _view("#e4e4e7")
        self.console.addSubview_(self.activity_rule)
        self.activity_btn = NSButton.buttonWithTitle_target_action_(
            "  ACTIVITY", self, "toggleActivity:")
        self.activity_btn.setImage_(_symbol("chevron.down"))
        self.activity_btn.setBordered_(False)
        self.activity_btn.setFont_(_font(11, MEDIUM))
        self.activity_btn.setContentTintColor_(TEXT_MUTED)
        self.activity_count = _label("0 lines", 11, TEXT_MUTED)
        self.activity_count.setFont_(_font(11, mono=True))
        self.console.addSubview_(self.activity_btn)
        self.console.addSubview_(self.activity_count)
        self.act_scroll, self.act = self._text_view("#f4f4f5", 12, inset=16)
        self.console.addSubview_(self.act_scroll)

    @objc.python_method
    def _build_rail(self, root):
        self.sources = _view("#ffffff", radius=12, border=True)
        root.addSubview_(self.sources)
        self.sources_title = _label("Input sources", 16, TEXT, SEMIBOLD)
        self.sources.addSubview_(self.sources_title)

        self.rows = {}
        for key, symbol, name, desc in (
            ("text", "chevron.left.forwardslash.chevron.right", "Text", "Always on."),
            ("voice", "mic", "Voice", ""),
            ("vision", "video", "Vision", ""),
        ):
            icon = NSImageView.alloc().init()
            icon.setImage_(_symbol(symbol))
            icon.setContentTintColor_(TEXT_MUTED)
            title = _label(name, 14, TEXT, MEDIUM)
            sub = _wrapping(desc)
            self.sources.addSubview_(icon)
            self.sources.addSubview_(title)
            self.sources.addSubview_(sub)
            sw = None
            if key != "text":
                sw = NSSwitch.alloc().init()
                sw.setTarget_(self)
                sw.setAction_("toggleSource:")
                sw.setIdentifier_(key)
                self.sources.addSubview_(sw)
            self.rows[key] = (icon, title, sub, sw)

        # ponytail: unreachable while vision is parked, kept so reconnecting is a
        # one-line change in main.py rather than rebuilding this card.
        self.camera = _view("#ffffff", radius=12, border=True)
        root.addSubview_(self.camera)
        self.camera_title = _label("Camera", 16, TEXT, SEMIBOLD)
        self.camera_meta = _label("", 12, TEXT_MUTED)
        self.camera_meta.setFont_(_font(12, mono=True))
        self.preview = _view("#18181b", radius=8)
        self.preview_note = _label("preview stays on the machine", 12, TEXT_MUTED)
        self.preview.addSubview_(self.preview_note)
        self.gesture_label = _label("LAST GESTURE", 11, TEXT_MUTED, MEDIUM)
        self.gesture_badge = _badge("none yet", SURFACE, "#16a34a")
        self.gesture_badge.inner.setFont_(_font(12, MEDIUM, mono=True))
        self.objects_label = _label("OBJECTS IN VIEW", 11, TEXT_MUTED, MEDIUM)
        self.objects_value = _wrapping("nothing yet")
        self.objects_value.setFont_(_font(12, mono=True))
        for v in (self.camera_title, self.camera_meta, self.preview, self.gesture_label,
                  self.gesture_badge, self.objects_label, self.objects_value):
            self.camera.addSubview_(v)

    @objc.python_method
    def _text_view(self, bg, inset_y, inset=24):
        scroll = NSScrollView.alloc().init()
        scroll.setHasVerticalScroller_(True)
        scroll.setDrawsBackground_(True)
        scroll.setBackgroundColor_(_rgb(bg))
        tv = NSTextView.alloc().initWithFrame_(NSMakeRect(0, 0, 400, 100))
        tv.setEditable_(False)
        tv.setDrawsBackground_(False)
        tv.setTextContainerInset_(NSMakeSize(inset, inset_y))
        tv.setAutoresizingMask_(NSViewWidthSizable)
        tv.textContainer().setWidthTracksTextView_(True)
        scroll.setDocumentView_(tv)
        return scroll, tv

    # -- layout: one function, explicit arithmetic, called on every resize ----

    @objc.python_method
    def _layout(self):
        w, h = self.root.frame().size.width, self.root.frame().size.height
        _set(self.header, 0, 0, w, 56)
        _set(self.header_rule, 0, 55, w, 1)

        x = 16
        _set(self.logo, x, 19, 18, 18); x += 26
        _set(self.brand, x, 18, 82, 20); x += 90
        _set(self.model_badge, x, 20, 78, 18)
        _set(self.model_badge.inner, 4, 1, 70, 16); x += 86
        _set(self.backend, x, 20, 220, 16)

        right = w - 16
        for btn, bw in ((self.quit_btn, 32), (self.settings_btn, 32)):
            right -= bw
            _set(btn, right, 12, bw, 32)
            right -= 8
        _set(self.confirm_btn, right - 196, 12, 196, 32)

        body_y, pad = 72, 16
        rail_w = 320
        con_w = max(360, w - rail_w - pad * 3)
        con_h = h - body_y - pad
        _set(self.console, pad, body_y, con_w, con_h)

        act_h = 32 + (176 if self.activity_open else 0)
        foot_h = 16 + 32 + 12 + 40 + 16
        gate_h = 88 if not self.gate.isHidden() else 0
        log_h = max(80, con_h - act_h - foot_h - gate_h)
        _set(self.log_scroll, 1, 1, con_w - 2, log_h)

        y = log_h
        if gate_h:
            _set(self.gate, 24, y + 8, con_w - 48, gate_h - 16)
            gw = con_w - 48
            _set(self.gate_title, 16, 12, 200, 18)
            _set(self.gate_cmd, 16, 34, gw - 32, 18)
            _set(self.gate_run, 16, 56, 72, 32)
            _set(self.gate_cancel, 96, 56, 84, 32)
            y += gate_h

        _set(self.footer_rule, 0, y, con_w, 1)
        cx = 16
        for b in self.chips:
            bw = b.intrinsicContentSize().width + 8
            _set(b, cx, y + 16, bw, 32)
            cx += bw + 8
        _set(self.draft, 16, y + 60, con_w - 16 - 8 - 40 - 8 - 88 - 16, 40)
        _set(self.mic_btn, con_w - 16 - 88 - 8 - 40, y + 60, 40, 40)
        _set(self.send_btn, con_w - 16 - 88, y + 60, 88, 40)

        y += foot_h
        _set(self.activity_rule, 0, y, con_w, 1)
        _set(self.activity_btn, 8, y + 4, 140, 24)
        _set(self.activity_count, con_w - 96, y + 8, 80, 16)
        self.act_scroll.setHidden_(not self.activity_open)
        if self.activity_open:
            _set(self.act_scroll, 1, y + 32, con_w - 2, con_h - (y + 32) - 1)

        rail_x = w - pad - rail_w
        _set(self.sources, rail_x, body_y, rail_w, 268)
        _set(self.sources_title, 24, 24, 200, 20)
        ry = 60
        for key in ("text", "voice", "vision"):
            icon, title, sub, sw = self.rows[key]
            _set(icon, 24, ry + 2, 16, 16)
            _set(title, 48, ry, 160, 18)
            _set(sub, 48, ry + 22, rail_w - 48 - 24 - (44 if sw else 0), 34)
            if sw:
                _set(sw, rail_w - 24 - 38, ry, 38, 22)
            ry += 68

        cam_y = body_y + 268 + 16
        cam_w, prev_h = rail_w, int((rail_w - 48) * 9 / 16)
        cam_h = 24 + 20 + 16 + prev_h + 16 + 18 + 8 + 20 + 16 + 18 + 8 + 34 + 24
        _set(self.camera, rail_x, cam_y, cam_w, cam_h)
        _set(self.camera_title, 24, 24, 120, 20)
        _set(self.camera_meta, cam_w - 24 - 140, 26, 140, 16)
        self.camera_meta.setAlignment_(2)  # right
        _set(self.preview, 24, 60, cam_w - 48, prev_h)
        _set(self.preview_note, 0, prev_h / 2 - 8, cam_w - 48, 16)
        self.preview_note.setAlignment_(1)  # centre
        gy = 60 + prev_h + 16
        _set(self.gesture_label, 24, gy, 200, 16)
        _set(self.gesture_badge, 24, gy + 24, 96, 18)
        _set(self.gesture_badge.inner, 4, 1, 88, 16)
        _set(self.objects_label, 24, gy + 60, 200, 16)
        _set(self.objects_value, 24, gy + 84, cam_w - 48, 34)

    def windowDidResize_(self, note):
        self._layout()

    # -- the one timer: everything the worker produced since last tick -------

    def tick_(self, timer):
        chunk = scrollback(self.seen)
        if chunk["lines"]:
            self._append_activity(chunk["lines"])
            self.seen = chunk["seq"]

        if self.awaiting is not None:
            try:
                self._append_turn(self.awaiting.get_nowait())
                self.awaiting = None
                self.send_btn.setEnabled_(True)
                self.draft.setEnabled_(True)
            except queue.Empty:
                pass

        cmd = _gate.get("cmd")
        if cmd != self.gate_shown:
            self.gate_shown = cmd
            self.gate.setHidden_(cmd is None)
            if cmd:
                self.gate_cmd.setStringValue_("$ " + cmd)
            self._layout()

        self._refresh_state()

    @objc.python_method
    def _refresh_state(self):
        s = _info()
        self.model_badge.inner.setStringValue_(s.get("model", ""))
        self.backend.setStringValue_(s.get("base_url", "").split("://")[-1])
        self.confirm_btn.setState_(NSControlStateValueOn if s.get("confirm") else 0)
        icon, _, sub, sw = self.rows["voice"]
        on = bool(s.get("voice"))
        sw.setState_(NSControlStateValueOn if on else 0)
        icon.setContentTintColor_(PRIMARY if on else TEXT_MUTED)
        sub.setStringValue_(f"Listening for {s['wake_word']} · mlx-whisper" if on
                            else "Off — turn on with the mic button")
        self.mic_btn.setImage_(_symbol("mic.fill" if on else "mic"))
        self.mic_btn.setContentTintColor_(PRIMARY if on else TEXT_MUTED)
        self.mic_btn.setToolTip_("Voice mode is on — say the wake word" if on
                                 else "Turn on voice mode")

        # No "vision" key means the backend has no vision at all — the row stays
        # so the surface is ready when it comes back, but it cannot be switched on.
        icon, _, sub, sw = self.rows["vision"]
        parked = "vision" not in s
        vision_on = bool(s.get("vision"))
        sw.setEnabled_(not parked)
        sw.setState_(NSControlStateValueOn if vision_on else 0)
        icon.setContentTintColor_(PRIMARY if vision_on else TEXT_MUTED)
        sub.setStringValue_("Parked — not wired to the backend" if parked else
                            ("Apple Vision gestures · YOLO11n objects" if vision_on
                             else "Off — needs VISION=1 at startup"))
        self.camera.setHidden_(not vision_on)
        self.camera_meta.setStringValue_(f"{s.get('fps', '')} fps · {s.get('width', '')} px")
        self.gesture_badge.inner.setStringValue_(_status["gesture"] or "none yet")
        self.objects_value.setStringValue_(", ".join(_status["objects"]) or "nothing yet")

    # -- rendering -----------------------------------------------------------

    @objc.python_method
    def _write(self, tv, text, size=14, color=TEXT, weight=None, mono=False, spacing=0):
        para = NSMutableParagraphStyle.alloc().init()
        para.setParagraphSpacing_(spacing)
        para.setLineBreakMode_(NSLineBreakByWordWrapping)
        attrs = {NSFontAttributeName: _font(size, weight, mono),
                 NSForegroundColorAttributeName: color,
                 NSParagraphStyleAttributeName: para}
        tv.textStorage().appendAttributedString_(
            NSAttributedString.alloc().initWithString_attributes_(text, attrs))
        tv.scrollRangeToVisible_(NSMakeRange(tv.textStorage().length(), 0))

    @objc.python_method
    def _append_turn(self, r):
        kind = r.get("kind")
        self._write(self.log, f"{r.get('source', 'you')}   ", 12, TEXT_MUTED, MEDIUM)
        self._write(self.log, r.get("request", "") + "\n", 14, TEXT, spacing=6)
        if kind == "command":
            self._write(self.log, "$ ", 13, PRIMARY, MEDIUM, mono=True)
            self._write(self.log, r.get("cmd", "") + "\n", 13, TEXT, MEDIUM, mono=True)
            if r.get("output"):
                self._write(self.log, r["output"] + "\n", 13, TEXT_MUTED, mono=True, spacing=18)
        elif kind == "image":
            self._write(self.log, r.get("image", "image") + "\n", 12, TEXT_MUTED, mono=True)
            self._write(self.log, r.get("output", "") + "\n", 14, TEXT, spacing=18)
        else:
            self._write(self.log, r.get("output", "") + "\n", 13, TEXT_MUTED, spacing=18)

    @objc.python_method
    def _append_activity(self, lines):
        for line in lines:
            cmd = line.startswith("$ ")  # the echo is the thing worth spotting
            self._write(self.act, line + "\n", 12,
                        TEXT if cmd else TEXT_MUTED, MEDIUM if cmd else None, mono=True)
        n = self.act.textStorage().string().count("\n")
        self.activity_count.setStringValue_(f"{n} line" + ("" if n == 1 else "s"))

    # -- actions -------------------------------------------------------------

    @objc.python_method
    def _ask(self, text):
        text = text.strip()
        if not text or self.awaiting is not None:
            return
        self.awaiting = queue.Queue()
        _requests.put((text, self.awaiting))
        self.draft.setStringValue_("")
        self.send_btn.setEnabled_(False)
        self.draft.setEnabled_(False)

    def send_(self, sender):
        self._ask(self.draft.stringValue())

    def chip_(self, sender):
        self._ask(sender.title())

    def gateYes_(self, sender):
        self._answer_gate(True)

    def gateNo_(self, sender):
        self._answer_gate(False)

    @objc.python_method
    def _answer_gate(self, yes):
        if _gate:
            _gate["yes"] = yes
            _gate["event"].set()

    def toggleActivity_(self, sender):
        self.activity_open = not self.activity_open
        sender.setImage_(_symbol("chevron.down" if self.activity_open else "chevron.right"))
        self._layout()

    def toggleVoice_(self, sender):
        self._flip("VOICE", not bool(_info().get("voice")))

    def toggleConfirm_(self, sender):
        self._flip("APRIL_CONFIRM", sender.state() == NSControlStateValueOn)

    def toggleSource_(self, sender):
        self._flip(sender.identifier().upper(), sender.state() == NSControlStateValueOn)

    @objc.python_method
    def _flip(self, key, on):
        problem = _apply(key, on)
        if problem:
            alert = NSAlert.alloc().init()
            alert.setMessageText_(problem)
            alert.beginSheetModalForWindow_completionHandler_(self.window, None)
        self._refresh_state()

    def quitApp_(self, sender):
        NSApplication.sharedApplication().terminate_(None)

    def windowWillClose_(self, note):
        _quit.set()

    def applicationShouldTerminateAfterLastWindowClosed_(self, app):
        return True

    def applicationWillTerminate_(self, note):
        _quit.set()

    # -- settings sheet ------------------------------------------------------

    def openSettings_(self, sender):
        s = _info()
        panel = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, 560, 470), NSWindowStyleMaskTitled,
            NSBackingStoreBuffered, False)
        panel.setAppearance_(NSAppearance.appearanceNamed_("NSAppearanceNameAqua"))
        body = _view("#ffffff")
        panel.setContentView_(body)

        body.addSubview_(_label("Settings", 16, TEXT, SEMIBOLD))
        body.subviews()[-1].setFrame_(NSMakeRect(24, 24, 200, 20))
        hint = _label("Everything here writes to .env. Restart to apply.", 13, TEXT_MUTED)
        _set(hint, 24, 46, 460, 18)
        body.addSubview_(hint)

        self.fields = {}
        y = 84
        for key, value, width in (("OPENAI_API_BASE_URL", s.get("base_url", ""), 512),
                                  ("OPENAI_MODEL", s.get("model", ""), 248),
                                  ("OPENAI_API_KEY", s.get("api_key", ""), 248)):
            lab = _label(key, 14, TEXT, MEDIUM)
            field = NSTextField.alloc().init()
            field.setStringValue_(value)
            field.setFont_(_font(14, mono=True))
            x = 24 if width == 512 or key == "OPENAI_MODEL" else 288
            if key == "OPENAI_API_KEY":
                y -= 64
            _set(lab, x, y, width, 18)
            _set(field, x, y + 22, width, 40)
            body.addSubview_(lab)
            body.addSubview_(field)
            self.fields[key] = field
            y += 64 if key != "OPENAI_MODEL" else 0
            if key == "OPENAI_MODEL":
                y += 64

        self.checks = {}
        y += 12
        for key, text in (("VOICE", "VOICE — wake word, speech in, speech out"),
                          ("VISION", "VISION — camera gestures and objects"),
                          ("APRIL_CONFIRM",
                           "APRIL_CONFIRM — approve each command before it runs")):
            box = NSButton.checkboxWithTitle_target_action_(text, None, None)
            box.setState_(NSControlStateValueOn if s.get(
                {"VOICE": "voice", "VISION": "vision"}.get(key, "confirm")) else 0)
            box.setFont_(_font(14))
            _set(box, 24, y, 512, 22)
            body.addSubview_(box)
            self.checks[key] = box
            y += 30

        warn = _wrapping("With confirmation off, commands run on this machine with full "
                         "shell access and no sandbox.", 12, TEXT_MUTED)
        warning_box = _view("#f4f4f5", radius=8, border=True)
        _set(warning_box, 24, y + 8, 512, 48)
        _set(warn, 40, 10, 456, 32)
        icon = NSImageView.alloc().init()
        icon.setImage_(_symbol("exclamationmark.triangle"))
        icon.setContentTintColor_(DANGER)
        _set(icon, 14, 15, 16, 16)
        warning_box.addSubview_(icon)
        warning_box.addSubview_(warn)
        body.addSubview_(warning_box)

        save = NSButton.buttonWithTitle_target_action_("Save to .env", self, "saveSettings:")
        save.setBezelStyle_(NSBezelStyleRounded)
        save.setBezelColor_(PRIMARY)
        save.setKeyEquivalent_("\r")
        _set(save, 560 - 24 - 120, y + 72, 120, 32)
        cancel = NSButton.buttonWithTitle_target_action_("Cancel", self, "closeSettings:")
        cancel.setBezelStyle_(NSBezelStyleRounded)
        _set(cancel, 560 - 24 - 120 - 88, y + 72, 80, 32)
        body.addSubview_(save)
        body.addSubview_(cancel)

        self.sheet = panel
        self.window.beginSheet_completionHandler_(panel, None)

    def closeSettings_(self, sender):
        if self.sheet:
            self.window.endSheet_(self.sheet)
            self.sheet = None

    def saveSettings_(self, sender):
        values = {k: f.stringValue() for k, f in self.fields.items()}
        flags = {k: b.state() == NSControlStateValueOn for k, b in self.checks.items()}
        problems = [p for k, v in flags.items() if (p := _apply(k, v))]
        write_env(dict(values, **flags))
        self.closeSettings_(sender)
        if problems:
            alert = NSAlert.alloc().init()
            alert.setMessageText_(" · ".join(problems))
            alert.beginSheetModalForWindow_completionHandler_(self.window, None)
        self._refresh_state()


def build(info, apply_setting):
    """Open the window. Must be called on the main thread, before run()."""
    global _info, _apply, _app
    _info, _apply = info, apply_setting
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyRegular)
    _app = _App.alloc().init()
    app.setDelegate_(_app)
    _app.build()
    NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
        TICK, _app, "tick:", None, True)
    return _app


def run():
    """Hand the main thread to AppKit. Returns when the window closes."""
    app = NSApplication.sharedApplication()
    app.activateIgnoringOtherApps_(True)
    app.run()
