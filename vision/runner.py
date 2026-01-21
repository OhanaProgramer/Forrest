# vision/runner.py
import cv2

_hog = cv2.HOGDescriptor()
_hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

def detect_runner(frame, scale=0.5, conf_threshold=0.4):
    """
    Detect primary runner (person) in frame.

    Returns:
        {
            "box": (x, y, w, h) or None,
            "confidence": float
        }
    """

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(gray, None, fx=scale, fy=scale)

    boxes, weights = _hog.detectMultiScale(
        small,
        winStride=(8, 8),
        padding=(8, 8),
        scale=1.05
    )

    best = None
    best_weight = 0.0

    for (x, y, w, h), weight in zip(boxes, weights):
        if weight > best_weight:
            best_weight = weight
            best = (x, y, w, h)

    if best_weight < conf_threshold:
        return {"box": None, "confidence": 0.0}

    # scale box back up
    x, y, w, h = best
    box = (
        int(x / scale),
        int(y / scale),
        int(w / scale),
        int(h / scale),
    )

    return {
        "box": box,
        "confidence": float(best_weight)
    }


# from interfaces.vision_output import RunnerObservation

# def detect_runner(frame) -> RunnerObservation:
#     # Placeholder: assume runner centered and visible
#     return RunnerObservation(
#         visible=True,
#         lateral_offset_m=0.0,
#         forward_distance_m=3.0,
#         heading_offset_deg=0.0,
#         confidence=0.9
#     )