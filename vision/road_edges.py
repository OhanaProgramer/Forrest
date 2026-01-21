import cv2
import numpy as np


def detect_boundary_points(frame, x_band=None):
    """
    Detect boundary evidence within an optional vertical band.

    Args:
        frame: BGR image
        x_band: (x_min, x_max) or None

    Returns:
        {
            "points": list[(x, y)],
            "mean_x": float | None,
            "strength": int
        }
    """

    h, w = frame.shape[:2]

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)

    # Gradient magnitude
    grad_x = cv2.Sobel(blur, cv2.CV_32F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(blur, cv2.CV_32F, 0, 1, ksize=3)
    mag = cv2.magnitude(grad_x, grad_y)
    mag = cv2.normalize(mag, None, 0, 255, cv2.NORM_MINMAX)
    mag = mag.astype(np.uint8)

    _, edges = cv2.threshold(mag, 50, 255, cv2.THRESH_BINARY)

    # Apply vertical band if provided
    if x_band is not None:
        x_min, x_max = x_band
        mask = np.zeros_like(edges)
        mask[:, x_min:x_max] = 255
        edges = cv2.bitwise_and(edges, mask)

    ys, xs = np.where(edges > 0)

    if len(xs) == 0:
        return {
            "points": [],
            "mean_x": None,
            "strength": 0,
        }

    points = list(zip(xs.tolist(), ys.tolist()))
    mean_x = float(np.mean(xs))
    strength = len(points)

    return {
        "points": points,
        "mean_x": mean_x,
        "strength": strength,
    }