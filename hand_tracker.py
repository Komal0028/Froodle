"""
hand_tracker.py
----------------
WHY THIS FILE EXISTS:
This is the "AI" heart of the project. It wraps Google's MediaPipe Hands
solution, so the rest of the app never has to think about neural
networks directly — it just asks "where is the hand?" and "which
fingers are up?".

HOW THE AI WORKS:
MediaPipe Hands runs two ML models: a palm detector (CNN that finds a
bounding box around the hand) and a landmark regressor (a second CNN,
cropped to that box, predicting 21 precise (x, y, z) joint coordinates).
Both were trained on large labeled hand-image datasets.

21 landmarks:
    0     = Wrist
    1-4   = Thumb (CMC, MCP, IP, TIP)
    5-8   = Index finger (MCP, PIP, DIP, TIP)
    9-12  = Middle finger (MCP, PIP, DIP, TIP)
    13-16 = Ring finger (MCP, PIP, DIP, TIP)
    17-20 = Pinky finger (MCP, PIP, DIP, TIP)

Fingertip (landmark 8) is used for drawing because it's the point
furthest from the palm and most natural as "the pen".

GESTURE RECOGNITION: for each finger, compare the tip landmark's Y (or
X for the thumb) against its PIP joint. If the tip is above the joint,
the finger counts as "up" / extended.
"""

import cv2
import mediapipe as mp


class HandTracker:
    TIP_IDS = [4, 8, 12, 16, 20]
    PIP_IDS = [3, 6, 10, 14, 18]

    def __init__(self, max_hands=1, detection_confidence=0.75, tracking_confidence=0.7):
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=max_hands,
            min_detection_confidence=detection_confidence,
            min_tracking_confidence=tracking_confidence,
        )
        self.mp_draw = mp.solutions.drawing_utils
        self.mp_styles = mp.solutions.drawing_styles
        self.results = None

    def find_hands(self, frame, draw_landmarks=False):
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        self.results = self.hands.process(rgb_frame)

        num_hands = 0
        if self.results.multi_hand_landmarks:
            num_hands = len(self.results.multi_hand_landmarks)
            if draw_landmarks:
                for hand_landmarks in self.results.multi_hand_landmarks:
                    self.mp_draw.draw_landmarks(
                        frame,
                        hand_landmarks,
                        self.mp_hands.HAND_CONNECTIONS,
                        self.mp_styles.get_default_hand_landmarks_style(),
                        self.mp_styles.get_default_hand_connections_style(),
                    )
        return frame, num_hands

    def get_landmark_positions(self, frame, hand_index=0):
        landmark_list = []
        if self.results and self.results.multi_hand_landmarks:
            if hand_index >= len(self.results.multi_hand_landmarks):
                return landmark_list
            hand = self.results.multi_hand_landmarks[hand_index]
            height, width, _ = frame.shape
            for idx, lm in enumerate(hand.landmark):
                px, py = int(lm.x * width), int(lm.y * height)
                landmark_list.append([idx, px, py])
        return landmark_list

    def get_hand_confidence(self, hand_index=0):
        if self.results and self.results.multi_handedness:
            if hand_index < len(self.results.multi_handedness):
                return self.results.multi_handedness[hand_index].classification[0].score
        return 0.0

    def fingers_up(self, landmark_list):
        if not landmark_list or len(landmark_list) < 21:
            return [0, 0, 0, 0, 0]

        fingers = []

        thumb_tip_x = landmark_list[self.TIP_IDS[0]][1]
        thumb_ip_x = landmark_list[self.PIP_IDS[0]][1]
        wrist_x = landmark_list[0][1]
        if wrist_x < landmark_list[9][1]:
            fingers.append(1 if thumb_tip_x > thumb_ip_x else 0)
        else:
            fingers.append(1 if thumb_tip_x < thumb_ip_x else 0)

        for i in range(1, 5):
            tip_y = landmark_list[self.TIP_IDS[i]][2]
            pip_y = landmark_list[self.PIP_IDS[i]][2]
            fingers.append(1 if tip_y < pip_y else 0)

        return fingers

    def close(self):
        self.hands.close()
