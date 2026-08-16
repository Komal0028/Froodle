"""
drawing.py
----------
WHY THIS FILE EXISTS:
This is the "whiteboard" itself: a canvas that knows how to draw ink,
erase, undo/redo, clear, and save as PNG.
"""

import os
import time
import cv2
import numpy as np


class DrawingCanvas:
    def __init__(self, width: int, height: int, max_history: int = 25):
        self.width = width
        self.height = height
        self.canvas = np.zeros((height, width, 3), dtype=np.uint8)

        self.max_history = max_history
        self.undo_stack = []
        self.redo_stack = []

        self.last_point = None

    def start_stroke(self):
        self._push_history()
        self.last_point = None

    def draw_point(self, point, color, thickness):
        if self.last_point is not None:
            cv2.line(self.canvas, self.last_point, point, color, thickness, lineType=cv2.LINE_AA)
        else:
            cv2.circle(self.canvas, point, max(thickness // 2, 1), color, -1, cv2.LINE_AA)
        self.last_point = point

    def erase_point(self, point, size):
        if self.last_point is not None:
            cv2.line(self.canvas, self.last_point, point, (0, 0, 0), size, cv2.LINE_AA)
        cv2.circle(self.canvas, point, size // 2, (0, 0, 0), -1, cv2.LINE_AA)
        self.last_point = point

    def end_stroke(self):
        self.last_point = None

    def _push_history(self):
        self.undo_stack.append(self.canvas.copy())
        if len(self.undo_stack) > self.max_history:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def undo(self):
        if self.undo_stack:
            self.redo_stack.append(self.canvas.copy())
            self.canvas = self.undo_stack.pop()
            return True
        return False

    def redo(self):
        if self.redo_stack:
            self.undo_stack.append(self.canvas.copy())
            self.canvas = self.redo_stack.pop()
            return True
        return False

    def clear(self):
        self._push_history()
        self.canvas = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        self.last_point = None

    def overlay_on_frame(self, frame):
        gray = cv2.cvtColor(self.canvas, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(gray, 10, 255, cv2.THRESH_BINARY)
        mask_inv = cv2.bitwise_not(mask)

        background = cv2.bitwise_and(frame, frame, mask=mask_inv)
        foreground = cv2.bitwise_and(self.canvas, self.canvas, mask=mask)
        return cv2.add(background, foreground)

    def save(self, folder="assets/saved", on_white_background=True):
        os.makedirs(folder, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(folder, f"drawing_{timestamp}.png")

        if on_white_background:
            white_bg = np.full((self.height, self.width, 3), 255, dtype=np.uint8)
            gray = cv2.cvtColor(self.canvas, cv2.COLOR_BGR2GRAY)
            _, mask = cv2.threshold(gray, 10, 255, cv2.THRESH_BINARY)
            mask_inv = cv2.bitwise_not(mask)
            background = cv2.bitwise_and(white_bg, white_bg, mask=mask_inv)
            foreground = cv2.bitwise_and(self.canvas, self.canvas, mask=mask)
            output_image = cv2.add(background, foreground)
        else:
            output_image = self.canvas

        cv2.imwrite(filepath, output_image)
        return filepath
