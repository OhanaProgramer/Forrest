import cv2
from inputs.video_file import VideoFileSource
from vision.runner import detect_runner
from vision.road_edges import detect_boundary_points

# ============================================================
# CONFIG / INPUT
# ============================================================
VIDEO_PATH = "data/video_clean/B.mp4"
source = VideoFileSource(VIDEO_PATH)

# ============================================================
# BOUNDARY TRACKING STATE
# ============================================================
last_boundary_x = None
band_width = 120

# ============================================================
# EMA SMOOTHING STATE (STEP 1)
# ============================================================
runner_cx_smooth = None
boundary_x_smooth = None
EMA_ALPHA = 0.25

# ============================================================
# CONFIDENCE OBJECTS (STEP 3)
# ============================================================
runner_confidence = 0.0
boundary_confidence = 0.0

RUNNER_CONF_DECAY = 0.02
BOUNDARY_CONF_DECAY = 0.015

# ============================================================
# CORRIDOR VISUALIZATION PARAMS (STEP 2)
# ============================================================
CORRIDOR_Y_TOP_RATIO = 0.45
CORRIDOR_Y_BOTTOM_RATIO = 0.95

# ============================================================
# REACTION THRESHOLDS (STEP 4)
# ============================================================
CLEARANCE_CAUTION_PX = 80
CLEARANCE_STOP_PX = 20

RUNNER_CONF_MIN = 0.4
BOUNDARY_CONF_MIN = 0.4

# ============================================================
# MAIN LOOP
# ============================================================
while True:
    frame = source.read()
    if frame is None:
        break

    h, w = frame.shape[:2]
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    display = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

    # ========================================================
    # RUNNER PERCEPTION
    # ========================================================
    runner = detect_runner(frame)
    runner_center_x = None

    if runner["box"]:
        x, y, bw, bh = runner["box"]
        runner_center_x = x + bw // 2

        # EMA smoothing
        if runner_cx_smooth is None:
            runner_cx_smooth = runner_center_x
        else:
            runner_cx_smooth = (
                EMA_ALPHA * runner_center_x +
                (1 - EMA_ALPHA) * runner_cx_smooth
            )

        cv2.rectangle(display, (x, y), (x + bw, y + bh), 255, 2)
        cv2.putText(
            display,
            f"runner_conf_det={runner['confidence']:.2f}",
            (x, y - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            255,
            2,
        )

    # ========================================================
    # RUNNER CONFIDENCE OBJECT
    # ========================================================
    if runner["box"] is not None:
        runner_confidence += 0.15 * runner["confidence"]
    else:
        runner_confidence -= RUNNER_CONF_DECAY

    runner_confidence = max(0.0, min(1.0, runner_confidence))

    # ========================================================
    # BOUNDARY ROI SELECTION
    # ========================================================
    if last_boundary_x is not None:
        band = (
            max(0, int(last_boundary_x - band_width)),
            min(w, int(last_boundary_x + band_width)),
        )
    else:
        band = None

    # ========================================================
    # BOUNDARY ROI VISUALIZATION
    # ========================================================
    if band is not None:
        overlay = display.copy()
        cv2.rectangle(
            overlay,
            (band[0], 0),
            (band[1], h),
            (255, 0, 0),
            -1
        )
        display = cv2.addWeighted(overlay, 0.15, display, 0.85, 0)

    # ========================================================
    # BOUNDARY DETECTION
    # ========================================================
    boundary = detect_boundary_points(frame, band)

    # ========================================================
    # BOUNDARY CONFIDENCE OBJECT
    # ========================================================
    if boundary["strength"] > 0:
        reinforcement = min(0.15, boundary["strength"] / 2000.0)
        boundary_confidence += reinforcement
    else:
        boundary_confidence -= BOUNDARY_CONF_DECAY

    boundary_confidence = max(0.0, min(1.0, boundary_confidence))

    # ========================================================
    # BOUNDARY SMOOTHING
    # ========================================================
    if boundary["mean_x"] is not None:
        boundary_x = int(boundary["mean_x"])
        last_boundary_x = boundary_x

        if boundary_x_smooth is None:
            boundary_x_smooth = boundary_x
        else:
            boundary_x_smooth = (
                EMA_ALPHA * boundary_x +
                (1 - EMA_ALPHA) * boundary_x_smooth
            )

    # Draw boundary points
    for x_pt, y_pt in boundary["points"][::3]:
        display[y_pt, x_pt] = 200

    # ========================================================
    # CORRIDOR METRICS
    # ========================================================
    clearance_px = None
    if runner_cx_smooth is not None and boundary_x_smooth is not None:
        clearance_px = int(boundary_x_smooth - runner_cx_smooth)

    # ========================================================
    # CORRIDOR VISUALIZATION
    # ========================================================
    if runner_cx_smooth is not None and boundary_x_smooth is not None:
        cx = int(runner_cx_smooth)
        bx = int(boundary_x_smooth)

        y_top = int(h * CORRIDOR_Y_TOP_RATIO)
        y_bot = int(h * CORRIDOR_Y_BOTTOM_RATIO)

        left_x = min(cx, bx)
        right_x = max(cx, bx)

        overlay = display.copy()
        cv2.rectangle(
            overlay,
            (left_x, y_top),
            (right_x, y_bot),
            (0, 255, 0),
            -1
        )
        display = cv2.addWeighted(overlay, 0.12, display, 0.88, 0)

        cv2.line(display, (cx, y_top), (cx, y_bot), (0, 255, 255), 2)
        cv2.line(display, (bx, y_top), (bx, y_bot), (0, 0, 255), 2)

    # ========================================================
    # REACTION STATE (STEP 4)
    # ========================================================
    reaction_state = "TRACK"

    if runner_confidence < RUNNER_CONF_MIN:
        reaction_state = "STOP (runner lost)"
    elif boundary_confidence < BOUNDARY_CONF_MIN:
        reaction_state = "TRACK (boundary untrusted)"
    elif clearance_px is None:
        reaction_state = "TRACK"
    elif clearance_px < CLEARANCE_STOP_PX:
        reaction_state = "STOP (boundary)"
    elif clearance_px < CLEARANCE_CAUTION_PX:
        reaction_state = "CAUTION"

    # ========================================================
    # DEBUG OVERLAY
    # ========================================================
    y0 = 30
    dy = 28

    cv2.putText(display, f"runner_cx_s={int(runner_cx_smooth) if runner_cx_smooth else None}",
                (10, y0), cv2.FONT_HERSHEY_SIMPLEX, 0.7, 200, 2)
    cv2.putText(display, f"boundary_x_s={int(boundary_x_smooth) if boundary_x_smooth else None}",
                (10, y0 + dy), cv2.FONT_HERSHEY_SIMPLEX, 0.7, 200, 2)
    cv2.putText(display, f"clearance_px={clearance_px}",
                (10, y0 + 2 * dy), cv2.FONT_HERSHEY_SIMPLEX, 0.7, 200, 2)
    cv2.putText(display, f"runner_conf_obj={runner_confidence:.2f}",
                (10, y0 + 3 * dy), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
    cv2.putText(display, f"boundary_conf_obj={boundary_confidence:.2f}",
                (10, y0 + 4 * dy), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

    # ========================================================
    # REACTION VISUALIZATION
    # ========================================================
    color = (0, 255, 0)
    if "CAUTION" in reaction_state:
        color = (0, 255, 255)
    elif "STOP" in reaction_state:
        color = (0, 0, 255)

    cv2.putText(
        display,
        f"REACTION: {reaction_state}",
        (10, h - 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        color,
        3,
    )

    # ========================================================
    # DISPLAY
    # ========================================================
    cv2.imshow("Forrest – Perception Debug", display)
    if cv2.waitKey(1) & 0xFF == 27:
        break

# ============================================================
# CLEANUP
# ============================================================
source.release()
cv2.destroyAllWindows()