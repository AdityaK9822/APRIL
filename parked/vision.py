"""Camera perception for APRIL — hand gestures + object detection.

Opt-in: main.py only imports this when VISION=1. Heavy deps import lazily so
`python vision.py` (the self-check) needs nothing but numpy.

Gestures come from Apple's Vision framework (VNDetectHumanHandPoseRequest ->
21 landmarks) classified by the heuristics below. MediaPipe was the first
choice but its 1.0.1 wheel crashes on init here (Metal helper unavailable, CPU
delegate included), so this route keeps everything in one venv and native.

Events are strings: "gesture:thumbs_up", "objects:cup,laptop,person".
The camera is only open between start() and stop() — same rule as the mic.
"""
import math
import os
import tempfile
import time

MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")
YOLO_WEIGHTS = os.getenv("YOLO_WEIGHTS", "yolo11n.pt")
CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", "0"))
DEVICE = os.getenv("VISION_DEVICE", "mps")

# ponytail: fps cap and frame width are THE tuning knobs. 8fps/640px keeps a
# 16GB Mac quiet; raise FPS for snappier gestures, lower it if fans spin up.
FPS = float(os.getenv("VISION_FPS", "8"))
FRAME_WIDTH = int(os.getenv("VISION_WIDTH", "640"))
OBJECT_EVERY = int(os.getenv("VISION_OBJECT_EVERY", "12"))  # YOLO every Nth frame, 0 = off

STABLE_FRAMES = 3     # hold a gesture this many frames before it fires
COOLDOWN_FRAMES = 16  # then ignore it this long (~2s at 8fps) so a hold can't spam

MIN_JOINT_CONF = 0.3
MIN_OBJECT_CONF = 0.5
EXTENDED_RATIO = 1.15  # tip must be this much farther from the wrist than the knuckle

# Apple Vision joint names, grouped (knuckle, middle joint, tip) per finger.
FINGERS = {
    "thumb": ("ThumbCMC", "ThumbMP", "ThumbTip"),
    "index": ("IndexMCP", "IndexPIP", "IndexTip"),
    "middle": ("MiddleMCP", "MiddlePIP", "MiddleTip"),
    "ring": ("RingMCP", "RingPIP", "RingTip"),
    "little": ("LittleMCP", "LittlePIP", "LittleTip"),
}

_cam = _request = _yolo = None
_debounce = None
_frame_no = 0
_next_frame = 0.0


class Debounce:
    """Turn per-frame gesture labels into one event per deliberate hold.

    A label must persist `stable` frames before it fires; after firing, the
    same label is ignored for `cooldown` frames. Without this, one held pose
    emits an event every single frame.
    """

    def __init__(self, stable=STABLE_FRAMES, cooldown=COOLDOWN_FRAMES):
        self.stable, self.cooldown = stable, cooldown
        self.label, self.held, self.quiet = None, 0, 0

    def update(self, label):
        """Feed this frame's label (or None). Returns a label to fire, or None."""
        self.quiet = max(0, self.quiet - 1)
        if label != self.label:
            self.label, self.held = label, 0
        self.held += 1
        if label and self.held >= self.stable and not self.quiet:
            self.quiet = self.cooldown
            return label
        return None


def extended_fingers(points):
    """Which fingers look straight, from {joint: (x, y, confidence)}.

    A finger counts as extended when its tip sits meaningfully farther from the
    wrist than its knuckle does — which holds however the hand is rotated.
    """
    wrist = points.get("Wrist")
    if not wrist or wrist[2] < MIN_JOINT_CONF:
        return set()
    out = set()
    for finger, (knuckle, _mid, tip) in FINGERS.items():
        a, b = points.get(knuckle), points.get(tip)
        if not a or not b or a[2] < MIN_JOINT_CONF or b[2] < MIN_JOINT_CONF:
            continue
        if math.dist(wrist[:2], b[:2]) > math.dist(wrist[:2], a[:2]) * EXTENDED_RATIO:
            out.add(finger)
    return out


def classify(points):
    """{joint: (x, y, confidence)} -> a gesture label, or None if it's not one.

    Vision's origin is bottom-left, so a larger y means higher up the frame —
    that is what separates a thumbs up from a thumbs down.
    """
    up = extended_fingers(points)
    if up == {"thumb"}:
        thumb, wrist = points["ThumbTip"], points["Wrist"]
        return "thumbs_up" if thumb[1] > wrist[1] else "thumbs_down"
    if up == {"index", "middle"}:
        return "victory"
    if up == {"index"}:
        return "point_up"
    if up == {"thumb", "index", "little"}:
        return "love"
    if len(up) >= 4:
        return "open_palm"
    if not up and points.get("Wrist", (0, 0, 0))[2] >= MIN_JOINT_CONF:
        return "fist"
    return None


def format_events(gesture, objects):
    """Build the event strings for one frame (either may be empty/None)."""
    events = []
    if gesture:
        events.append(f"gesture:{gesture}")
    if objects:
        events.append("objects:" + ",".join(objects))
    return events


def _load_models():
    global _request, _yolo
    if _request is not None:
        return
    import Vision

    _build_joint_names()
    _request = Vision.VNDetectHumanHandPoseRequest.alloc().init()
    _request.setMaximumHandCount_(1)
    if OBJECT_EVERY > 0:
        import numpy as np
        from ultralytics import YOLO

        _yolo = YOLO(YOLO_WEIGHTS)  # ultralytics downloads it on first use
        # First MPS inference costs ~2.5s to compile. Spend it here, at startup,
        # instead of stalling the poll loop on the first object frame.
        _detect_objects(np.zeros((360, FRAME_WIDTH, 3), dtype="uint8"))


def start():
    """Open the camera and load models. Models stay loaded across stop()/start()."""
    global _cam, _debounce, _frame_no
    import cv2

    _load_models()
    if _cam is None:
        _debounce, _frame_no = Debounce(), 0
        _cam = cv2.VideoCapture(CAMERA_INDEX)
        if not _cam.isOpened():
            raise SystemExit(
                f"VISION=1 but camera {CAMERA_INDEX} won't open "
                "(System Settings > Privacy & Security > Camera)"
            )


def stop():
    """Release the camera. Keeps the models resident for the next start()."""
    global _cam
    if _cam is not None:
        _cam.release()
        _cam = None


def _pace():
    """Sleep just enough to hold the FPS cap."""
    global _next_frame
    now = time.monotonic()
    if now < _next_frame:
        time.sleep(_next_frame - now)
    _next_frame = max(now, _next_frame) + 1.0 / FPS


def _hand_points(frame):
    """Run Apple Vision on a BGR frame -> {joint: (x, y, confidence)}."""
    import cv2
    import Vision
    from Foundation import NSData

    # ponytail: JPEG round-trip into VNImageRequestHandler (~2ms) instead of
    # hand-building a CGImage. Swap to CVPixelBuffer only if fps ever hurts.
    ok, buf = cv2.imencode(".jpg", frame)
    if not ok:
        return {}
    raw = buf.tobytes()
    handler = Vision.VNImageRequestHandler.alloc().initWithData_options_(
        NSData.dataWithBytes_length_(raw, len(raw)), {}
    )
    handler.performRequests_error_([_request], None)
    results = _request.results()
    if not results:
        return {}
    points, _ = results[0].recognizedPointsForJointsGroupName_error_(
        Vision.VNHumanHandPoseObservationJointsGroupNameAll, None
    )
    out = {}
    for name, point in (points or {}).items():
        location = point.location()
        out[_JOINT_NAMES.get(str(name), str(name))] = (
            location.x, location.y, point.confidence()
        )
    return out


# Vision reports joints by short codes (e.g. "VNHLKTTIP"); map them to our names.
_JOINT_NAMES = {}


def _build_joint_names():
    import Vision

    wanted = ["Wrist"] + [j for group in FINGERS.values() for j in group]
    for name in wanted:
        const = getattr(Vision, f"VNHumanHandPoseObservationJointName{name}", None)
        if const is not None:
            _JOINT_NAMES[str(const)] = name


def poll():
    """Grab one frame and return its events (usually empty). Requires start().

    Paces itself to FPS, so calling this in a tight loop does not spin the CPU.
    """
    global _frame_no
    import cv2

    _pace()
    ok, frame = _cam.read()
    if not ok:
        return []
    _frame_no += 1
    if frame.shape[1] > FRAME_WIDTH:
        height = round(frame.shape[0] * FRAME_WIDTH / frame.shape[1])
        frame = cv2.resize(frame, (FRAME_WIDTH, height))

    gesture = _debounce.update(classify(_hand_points(frame)))
    objects = (
        _detect_objects(frame)
        if _yolo is not None and _frame_no % OBJECT_EVERY == 0
        else None
    )
    return format_events(gesture, objects)


def _detect_objects(frame):
    global DEVICE
    try:
        result = _yolo.predict(frame, verbose=False, conf=MIN_OBJECT_CONF, device=DEVICE)[0]
    except Exception:
        # ponytail: MPS is flaky on some torch builds; drop to CPU for good.
        DEVICE = "cpu"
        result = _yolo.predict(frame, verbose=False, conf=MIN_OBJECT_CONF, device="cpu")[0]
    return sorted({result.names[int(c)] for c in result.boxes.cls})


def snapshot(path=None):
    """Save one camera frame to a PNG and return its path.

    Reuses the open camera if there is one, otherwise opens and closes its own
    so main.py can answer "what am I holding?" without VISION's poll loop.
    """
    import cv2

    path = path or os.path.join(tempfile.gettempdir(), "april_cam.png")
    cam = _cam if _cam is not None else cv2.VideoCapture(CAMERA_INDEX)
    try:
        ok, frame = cam.read()
    finally:
        if cam is not _cam:
            cam.release()
    if not ok:
        raise SystemExit(f"camera {CAMERA_INDEX} gave no frame")
    cv2.imwrite(path, frame)
    return path


if __name__ == "__main__":
    def hand(extended, thumb_y=0.9, wrist_y=0.5):
        """Synthetic landmarks: named fingers straight, the rest curled."""
        points = {"Wrist": (0.5, wrist_y, 0.9)}
        for finger, (knuckle, mid, tip) in FINGERS.items():
            reach = 0.30 if finger in extended else 0.10
            y = thumb_y if finger == "thumb" and "thumb" in extended else wrist_y + reach
            points[knuckle] = (0.5, wrist_y + 0.10, 0.9)
            points[mid] = (0.5, wrist_y + reach * 0.7, 0.9)
            points[tip] = (0.5, y if finger == "thumb" else wrist_y + reach, 0.9)
        return points

    assert extended_fingers(hand({"index"})) == {"index"}
    assert extended_fingers(hand({"index", "middle"})) == {"index", "middle"}
    assert extended_fingers(hand(set())) == set()
    assert extended_fingers({}) == set()  # no wrist -> nothing

    assert classify(hand({"thumb"}, thumb_y=0.9)) == "thumbs_up"
    assert classify(hand({"thumb"}, thumb_y=0.1)) == "thumbs_down"
    assert classify(hand({"index", "middle"})) == "victory"
    assert classify(hand({"index"})) == "point_up"
    assert classify(hand({"thumb", "index", "little"})) == "love"
    assert classify(hand({"thumb", "index", "middle", "ring", "little"})) == "open_palm"
    assert classify(hand({"index", "middle", "ring", "little"})) == "open_palm"
    assert classify(hand(set())) == "fist"
    assert classify({}) is None  # nothing detected is not a fist

    low = {k: (x, y, 0.05) for k, (x, y, _) in hand({"index"}).items()}
    assert classify(low) is None  # low-confidence joints are ignored

    d = Debounce(stable=3, cooldown=5)
    assert [d.update("thumbs_up") for _ in range(2)] == [None, None]
    assert d.update("thumbs_up") == "thumbs_up"                     # fires on the 3rd
    assert [d.update("thumbs_up") for _ in range(4)] == [None] * 4  # cooldown holds
    assert d.update("thumbs_up") == "thumbs_up"                     # then repeats

    d = Debounce(stable=2, cooldown=5)
    assert d.update("victory") is None
    assert d.update("victory") == "victory"
    assert d.update(None) is None            # dropping the pose resets the hold
    assert d.update("victory") is None       # ...and it must be held again
    assert [d.update(None) for _ in range(4)] == [None] * 4  # no hand, no events

    assert format_events(None, None) == []
    assert format_events("thumbs_up", None) == ["gesture:thumbs_up"]
    assert format_events(None, ["cup", "laptop"]) == ["objects:cup,laptop"]
    assert format_events("fist", ["person"]) == ["gesture:fist", "objects:person"]

    print("vision.py self-check OK")
