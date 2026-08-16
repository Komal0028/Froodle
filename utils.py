"""
utils.py
--------
WHY THIS FILE EXISTS:
Small, reusable helper pieces that don't belong to any single class:
FPS measurement, point smoothing (so the line doesn't shake), distance
math, and the color palette used by the whiteboard toolbar.
"""

import time
import math
from collections import deque


class FPSCounter:
    def __init__(self):
        self.prev_time = time.time()
        self.fps = 0

    def update(self):
        current_time = time.time()
        elapsed = current_time - self.prev_time
        self.fps = 1 / elapsed if elapsed > 0 else 0
        self.prev_time = current_time
        return int(self.fps)


class PointSmoother:
    def __init__(self, window_size: int = 5):
        self.window_size = window_size
        self.x_history = deque(maxlen=window_size)
        self.y_history = deque(maxlen=window_size)

    def smooth(self, x: int, y: int):
        self.x_history.append(x)
        self.y_history.append(y)
        smoothed_x = int(sum(self.x_history) / len(self.x_history))
        smoothed_y = int(sum(self.y_history) / len(self.y_history))
        return smoothed_x, smoothed_y

    def reset(self):
        self.x_history.clear()
        self.y_history.clear()


def euclidean_distance(point1, point2) -> float:
    return math.hypot(point2[0] - point1[0], point2[1] - point1[1])


COLOR_PALETTE = {
    "White":   (255, 255, 255),
    "Red":     (60, 60, 255),
    "Green":   (120, 220, 120),
    "Blue":    (255, 140, 60),
    "Yellow":  (60, 220, 240),
    "Purple":  (220, 100, 200),
    "Eraser":  (0, 0, 0),
}

DEFAULT_BRUSH_SIZE = 8
DEFAULT_ERASER_SIZE = 40
MIN_BRUSH_SIZE = 2
MAX_BRUSH_SIZE = 40
