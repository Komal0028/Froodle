

import av
import cv2
import numpy as np
from streamlit_webrtc import VideoProcessorBase

from hand_tracker import HandTracker
from drawing import DrawingCanvas
from utils import PointSmoother, COLOR_PALETTE, DEFAULT_BRUSH_SIZE, DEFAULT_ERASER_SIZE


class WhiteboardProcessor(VideoProcessorBase):
    """
    streamlit-webrtc calls recv() once per incoming video frame, on a
    background thread. We keep all whiteboard state (canvas, brush
    settings, last action) as instance attributes here, and the
    Streamlit UI (sidebar buttons/sliders) mutates those same attributes
    through the processor instance it gets back from webrtc_streamer().
    """

    def __init__(self):
        self.tracker = HandTracker(max_hands=1)
        self.canvas = None  # created on first frame once we know width/height
        self.smoother = PointSmoother(window_size=6)

        # UI-controlled settings (set from the Streamlit sidebar)
        self.current_color_name = "White"
        self.brush_size = DEFAULT_BRUSH_SIZE
        self.show_landmarks = False

        # Read-only status the UI displays back to the user
        self.current_action = "Idle"
        self.num_hands = 0
        self.confidence = 0.0
        self.last_saved_path = None

        # One-shot action flags, set by button clicks, consumed on next frame
        self._request_clear = False
        self._request_undo = False
        self._request_redo = False
        self._request_save = False

        self._clear_confirm_frames = 0

    # -----------------------------------------------------------------
    # Called from the Streamlit UI thread (button clicks / sliders)
    # -----------------------------------------------------------------
    def request_clear(self):
        self._request_clear = True

    def request_undo(self):
        self._request_undo = True

    def request_redo(self):
        self._request_redo = True

    def request_save(self):
        self._request_save = True

    # -----------------------------------------------------------------
    # Called by streamlit-webrtc once per video frame
    # -----------------------------------------------------------------
    def recv(self, frame: av.VideoFrame) -> av.VideoFrame:
        img = frame.to_ndarray(format="bgr24")
        img = cv2.flip(img, 1)  # mirror, feels natural
        height, width, _ = img.shape

        if self.canvas is None or self.canvas.width != width or self.canvas.height != height:
            self.canvas = DrawingCanvas(width, height)

        self._consume_pending_requests()

        img, self.num_hands = self.tracker.find_hands(img, draw_landmarks=self.show_landmarks)
        landmarks = self.tracker.get_landmark_positions(img)

        if landmarks:
            self.confidence = self.tracker.get_hand_confidence()
            fingers = self.tracker.fingers_up(landmarks)
            self._handle_gesture(fingers, landmarks)
        else:
            self.current_action = "Idle"
            self.canvas.end_stroke()
            self.smoother.reset()

        img = self.canvas.overlay_on_frame(img)
        self._draw_hud(img)

        return av.VideoFrame.from_ndarray(img, format="bgr24")

    def _consume_pending_requests(self):
        if self._request_clear:
            self.canvas.clear()
            self._request_clear = False
        if self._request_undo:
            self.canvas.undo()
            self._request_undo = False
        if self._request_redo:
            self.canvas.redo()
            self._request_redo = False
        if self._request_save:
            self.last_saved_path = self.canvas.save()
            self._request_save = False

    def _handle_gesture(self, fingers, landmarks):
        """Identical gesture mapping to main.py's AirWhiteboardApp._handle_gesture."""
        index_tip = tuple(landmarks[8][1:])
        total_up = sum(fingers)

        if fingers == [1, 1, 1, 1, 1]:
            self._clear_confirm_frames += 1
            self.current_action = f"Hold palm to clear ({self._clear_confirm_frames}/20)"
            if self._clear_confirm_frames > 20:
                self.canvas.clear()
                self._clear_confirm_frames = 0
            self.canvas.end_stroke()
            self.smoother.reset()
            return
        else:
            self._clear_confirm_frames = 0

        if fingers == [1, 0, 0, 0, 0]:
            self.current_action = "Thumb up: Save"
            self.last_saved_path = self.canvas.save()
            self.canvas.end_stroke()
            self.smoother.reset()
            return

        if total_up == 0:
            self.current_action = "Eraser"
            smooth_point = self.smoother.smooth(*index_tip)
            self.canvas.erase_point(smooth_point, DEFAULT_ERASER_SIZE)
            return

        if fingers == [0, 1, 1, 0, 0]:
            self.current_action = "Move (no draw)"
            self.canvas.end_stroke()
            self.smoother.reset()
            return

        if fingers == [0, 1, 0, 0, 0]:
            self.current_action = "Drawing"
            smooth_point = self.smoother.smooth(*index_tip)
            if self.canvas.last_point is None:
                self.canvas.start_stroke()
            color = COLOR_PALETTE[self.current_color_name]
            self.canvas.draw_point(smooth_point, color, self.brush_size)
            return

        self.current_action = "Idle"
        self.canvas.end_stroke()
        self.smoother.reset()

    def _draw_hud(self, img):
        cv2.putText(img, f"Gesture: {self.current_action}", (16, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2, cv2.LINE_AA)
        if self.num_hands > 0:
            cv2.putText(img, f"Confidence: {self.confidence*100:.0f}%", (16, 58),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 255), 2, cv2.LINE_AA)
        elif self.num_hands == 0:
            cv2.putText(img, "Show your hand to the camera", (16, 58),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 180, 255), 2, cv2.LINE_AA)
