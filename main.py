"""
main.py
-------
Entry point: webcam loop, on-screen toolbar UI, gesture->action logic.
RUN WITH: python main.py
Keyboard: q/Esc=quit, c=clear, s=save, u=undo, r=redo, l=toggle landmarks,
f=fullscreen, +/- = brush size.
"""

import os
import sys
import cv2
import numpy as np

from hand_tracker import HandTracker
from drawing import DrawingCanvas
from ai_explainer import DrawingExplainer
from utils import (
    FPSCounter,
    PointSmoother,
    COLOR_PALETTE,
    DEFAULT_BRUSH_SIZE,
    DEFAULT_ERASER_SIZE,
    MIN_BRUSH_SIZE,
    MAX_BRUSH_SIZE,
)

WINDOW_NAME = "AI Air Whiteboard"
FRAME_WIDTH, FRAME_HEIGHT = 1280, 720
TOOLBAR_HEIGHT = 90


class AirWhiteboardApp:
    def __init__(self):
        self.cap = self._open_camera()
        self.tracker = HandTracker(max_hands=2)
        self.canvas = DrawingCanvas(FRAME_WIDTH, FRAME_HEIGHT - TOOLBAR_HEIGHT)
        self.explainer = DrawingExplainer()
        self.fps_counter = FPSCounter()
        self.smoother = PointSmoother(window_size=6)

        self.current_color_name = "White"
        self.brush_size = DEFAULT_BRUSH_SIZE
        self.show_landmarks = False
        self.show_fps = True
        self.is_fullscreen = False
        self.camera_on = True
        self.current_action = "Idle"
        self.clear_confirm_frames = 0
        self.status_message = ""
        self.status_timer = 0
        self._quit_requested = False

        self.toolbar_buttons = self._build_toolbar_layout()

        cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(WINDOW_NAME, FRAME_WIDTH, FRAME_HEIGHT)
        cv2.setMouseCallback(WINDOW_NAME, self._on_mouse_click)

    def _open_camera(self):
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("❌ ERROR: Could not access the webcam.")
            sys.exit(1)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT - TOOLBAR_HEIGHT)
        return cap

    def _build_toolbar_layout(self):
        buttons = []
        x = 20
        for name in COLOR_PALETTE:
            buttons.append({"type": "color", "name": name, "rect": (x, 15, x + 50, 65)})
            x += 65

        action_names = ["Undo", "Redo", "Clear", "Save", "Landmarks", "Explain"]
        x = FRAME_WIDTH - 20 - len(action_names) * 130
        for name in action_names:
            buttons.append({"type": "action", "name": name, "rect": (x, 15, x + 115, 65)})
            x += 130
        return buttons

    def _on_mouse_click(self, event, x, y, flags, param):
        if event != cv2.EVENT_LBUTTONDOWN:
            return
        for button in self.toolbar_buttons:
            x1, y1, x2, y2 = button["rect"]
            if x1 <= x <= x2 and y1 <= y <= y2:
                self._activate_button(button)

    def _activate_button(self, button):
        if button["type"] == "color":
            self.current_color_name = button["name"]
        else:
            name = button["name"]
            if name == "Undo":
                self.canvas.undo()
            elif name == "Redo":
                self.canvas.redo()
            elif name == "Clear":
                self.canvas.clear()
                self._set_status("Canvas cleared")
            elif name == "Save":
                self._save_drawing()
            elif name == "Landmarks":
                self.show_landmarks = not self.show_landmarks
            elif name == "Explain":
                self._explain_drawing()

    def _set_status(self, message, duration_frames=60):
        self.status_message = message
        self.status_timer = duration_frames

    def _save_drawing(self):
        path = self.canvas.save()
        self._set_status(f"Saved: {os.path.basename(path)}")
        return path

    def _explain_drawing(self):
        path = self._save_drawing()
        self._set_status("Asking AI to explain your drawing...")
        explanation = self.explainer.explain(path)
        print("\n🤖 AI Explanation of your drawing:\n" + explanation + "\n")
        self._set_status("See terminal for AI explanation")

    def _handle_gesture(self, fingers, landmarks):
        index_tip = tuple(landmarks[8][1:])
        total_up = sum(fingers)

        if fingers == [1, 1, 1, 1, 1]:
            self.clear_confirm_frames += 1
            self.current_action = f"Hold open palm to clear... ({self.clear_confirm_frames}/20)"
            if self.clear_confirm_frames > 20:
                self.canvas.clear()
                self._set_status("Canvas cleared (gesture)")
                self.clear_confirm_frames = 0
            self.canvas.end_stroke()
            self.smoother.reset()
            return
        else:
            self.clear_confirm_frames = 0

        if fingers == [1, 0, 0, 0, 0]:
            self.current_action = "Thumb up: Save"
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

    def _draw_glass_panel(self, frame, x1, y1, x2, y2, alpha=0.55, color=(40, 40, 40)):
        overlay = frame.copy()
        cv2.rectangle(overlay, (x1, y1), (x2, y2), color, -1)
        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
        cv2.rectangle(frame, (x1, y1), (x2, y2), (90, 90, 90), 1, cv2.LINE_AA)

    def _draw_toolbar(self, frame):
        self._draw_glass_panel(frame, 0, 0, FRAME_WIDTH, TOOLBAR_HEIGHT, alpha=0.75, color=(25, 25, 30))

        for button in self.toolbar_buttons:
            x1, y1, x2, y2 = button["rect"]
            if button["type"] == "color":
                bgr = COLOR_PALETTE[button["name"]]
                cv2.rectangle(frame, (x1, y1), (x2, y2), bgr, -1, cv2.LINE_AA)
                border = (255, 255, 255) if button["name"] == self.current_color_name else (100, 100, 100)
                thickness = 3 if button["name"] == self.current_color_name else 1
                cv2.rectangle(frame, (x1, y1), (x2, y2), border, thickness, cv2.LINE_AA)
            else:
                highlight = (70, 130, 230) if button["name"] == "Explain" else (55, 55, 60)
                cv2.rectangle(frame, (x1, y1), (x2, y2), highlight, -1, cv2.LINE_AA)
                cv2.rectangle(frame, (x1, y1), (x2, y2), (150, 150, 150), 1, cv2.LINE_AA)
                text_size = cv2.getTextSize(button["name"], cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
                tx = x1 + (x2 - x1 - text_size[0]) // 2
                ty = y1 + (y2 - y1 + text_size[1]) // 2
                cv2.putText(frame, button["name"], (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (240, 240, 240), 1, cv2.LINE_AA)

    def _draw_hud(self, frame, num_hands, confidence):
        y = TOOLBAR_HEIGHT + 30
        if self.show_fps:
            cv2.putText(frame, f"FPS: {self.fps_counter.update()}", (20, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 120), 2, cv2.LINE_AA)
            y += 28

        cv2.putText(frame, f"Gesture: {self.current_action}", (20, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)
        y += 28

        if num_hands > 0:
            cv2.putText(frame, f"Hand confidence: {confidence*100:.0f}%", (20, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 255), 2, cv2.LINE_AA)
            y += 28

        if num_hands > 1:
            cv2.putText(frame, "Multiple hands detected - using the first one", (20, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (60, 60, 255), 2, cv2.LINE_AA)
            y += 28
        elif num_hands == 0:
            cv2.putText(frame, "No hand detected - show your hand to the camera", (20, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 180, 255), 2, cv2.LINE_AA)
            y += 28

        cv2.putText(frame, f"Brush size: {self.brush_size}", (20, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)

        if self.status_timer > 0:
            cv2.putText(frame, self.status_message, (20, FRAME_HEIGHT - 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2, cv2.LINE_AA)
            self.status_timer -= 1

    def run(self):
        print("✅ AI Air Whiteboard started. Press 'q' or ESC in the window to quit.")
        while True:
            success, frame = self.cap.read()
            if not success:
                print("❌ ERROR: Lost connection to webcam.")
                break

            frame = cv2.flip(frame, 1)
            video_area = frame[TOOLBAR_HEIGHT:, :]

            confidence = 0.0
            num_hands = 0
            if self.camera_on:
                video_area, num_hands = self.tracker.find_hands(video_area, draw_landmarks=self.show_landmarks)
                landmarks = self.tracker.get_landmark_positions(video_area)

                if landmarks:
                    confidence = self.tracker.get_hand_confidence()
                    fingers = self.tracker.fingers_up(landmarks)
                    self._handle_gesture(fingers, landmarks)
                else:
                    self.current_action = "Idle"
                    self.canvas.end_stroke()
                    self.smoother.reset()

                video_area = self.canvas.overlay_on_frame(video_area)
            else:
                video_area = np.full_like(video_area, 20)
                cv2.putText(video_area, "Camera Off", (video_area.shape[1] // 2 - 100, video_area.shape[0] // 2),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (150, 150, 150), 2, cv2.LINE_AA)

            frame[TOOLBAR_HEIGHT:, :] = video_area
            self._draw_toolbar(frame)
            self._draw_hud(frame, num_hands, confidence)

            cv2.imshow(WINDOW_NAME, frame)
            self._handle_keyboard(cv2.waitKey(1) & 0xFF)
            if self._quit_requested:
                break

        self.cleanup()

    def _handle_keyboard(self, key):
        if key in (ord("q"), 27):
            self._quit_requested = True
        elif key == ord("c"):
            self.canvas.clear()
            self._set_status("Canvas cleared")
        elif key == ord("s"):
            self._save_drawing()
        elif key == ord("u"):
            self.canvas.undo()
        elif key == ord("r"):
            self.canvas.redo()
        elif key == ord("l"):
            self.show_landmarks = not self.show_landmarks
        elif key == ord("f"):
            self._toggle_fullscreen()
        elif key in (ord("+"), ord("=")):
            self.brush_size = min(MAX_BRUSH_SIZE, self.brush_size + 2)
        elif key == ord("-"):
            self.brush_size = max(MIN_BRUSH_SIZE, self.brush_size - 2)

    def _toggle_fullscreen(self):
        self.is_fullscreen = not self.is_fullscreen
        cv2.setWindowProperty(
            WINDOW_NAME, cv2.WND_PROP_FULLSCREEN,
            cv2.WINDOW_FULLSCREEN if self.is_fullscreen else cv2.WINDOW_NORMAL,
        )

    def cleanup(self):
        self.cap.release()
        self.tracker.close()
        cv2.destroyAllWindows()
        print("👋 AI Air Whiteboard closed.")


if __name__ == "__main__":
    try:
        app = AirWhiteboardApp()
        app.run()
    except KeyboardInterrupt:
        print("\n👋 Interrupted by user.")
    except Exception as exc:
        print(f"❌ Unexpected error: {exc}")
