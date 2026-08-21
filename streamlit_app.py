import os
import glob
import logging
import subprocess
import sys
import time

import streamlit as st
from streamlit_webrtc import webrtc_streamer, RTCConfiguration, WebRtcMode

from ai_explainer import DrawingExplainer
from webrtc_processor import WhiteboardProcessor
from utils import COLOR_PALETTE, MIN_BRUSH_SIZE, MAX_BRUSH_SIZE, DEFAULT_BRUSH_SIZE

# Streamlit Cloud blocks/proxies raw UDP, so STUN-only ICE negotiation
# fails there even though it works locally. A TURN relay is required
# for the video connection to actually establish once deployed.
# Open Relay Project is a free public TURN service, good enough for a
# portfolio/demo deployment. For production reliability, switch to a
# paid provider like Twilio's Network Traversal Service.
RTC_CONFIGURATION = RTCConfiguration({
    "iceServers": [
        {"urls": ["stun:stun.l.google.com:19302"]},
        {"urls": ["turn:openrelay.metered.ca:80"], "username": "openrelayproject", "credential": "openrelayproject"},
        {"urls": ["turn:openrelay.metered.ca:443"], "username": "openrelayproject", "credential": "openrelayproject"},
        {"urls": ["turn:openrelay.metered.ca:443?transport=tcp"], "username": "openrelayproject", "credential": "openrelayproject"},
    ]
})

# aioice/aiortc log a lot of retry noise while ICE negotiates; this just
# keeps the terminal/log panel readable, it doesn't affect connectivity.
logging.getLogger("aioice").setLevel(logging.WARNING)
logging.getLogger("aiortc").setLevel(logging.WARNING)

SAVED_DIR = "assets/saved"
COLOR_DOTS = {"White": "⚪", "Red": "🔴", "Green": "🟢", "Blue": "🔵", "Yellow": "🟡", "Purple": "🟣"}


def load_css():
    css_path = os.path.join("assets", "style.css")
    if os.path.exists(css_path):
        with open(css_path) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Caveat:wght@600;700&family=Manrope:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;700&display=swap');

        :root {
            --ink: #262322; --ink-soft: #6b665f;
            --paper: #FBF6EC; --paper-2: #FFFFFF; --line: rgba(38,35,34,0.10);
            --coral: #FF6A52; --sky: #2F8FE0; --sunshine: #F2A93C; --grass: #3FA772; --grape: #8B6BE8;
            --font-display: 'Caveat', cursive;
            --font-body: 'Manrope', -apple-system, sans-serif;
            --font-mono: 'JetBrains Mono', monospace;
        }

        #MainMenu, footer, header { visibility: hidden; }

        .stApp {
            background-color: var(--paper);
            background-image: radial-gradient(var(--line) 1.4px, transparent 1.4px);
            background-size: 24px 24px;
        }
        html, body, [class*="css"] { font-family: var(--font-body); color: var(--ink); }
        p, span, div, label { color: var(--ink); }

        .badge, .gesture-chip, .stat-card {
            border: 2px solid var(--ink);
            box-shadow: 4px 4px 0 var(--line-shadow, var(--coral));
        }

        .hero {
            padding: 52px 48px 44px; border-radius: 22px; margin-bottom: 26px;
            background: var(--paper-2); border: 2px solid var(--ink);
            box-shadow: 6px 6px 0 var(--line);
            text-align: center; display: flex; flex-direction: column; align-items: center;
            position: relative; overflow: hidden;
        }
        .hero-content { position: relative; z-index: 2; display: flex; flex-direction: column; align-items: center; }
        .critter { position: absolute; z-index: 1; }
        .critter-panda    { top: -14px; left: -18px; width: 150px; transform: rotate(-9deg); }
        .critter-elephant { top: -20px; right: -20px; width: 175px; transform: rotate(7deg); }
        .critter-bear     { bottom: -22px; left: -16px; width: 150px; transform: rotate(8deg); }
        .critter-giraffe  { bottom: -18px; right: -14px; width: 165px; transform: rotate(-7deg); }
        @media (max-width: 900px) { .critter { display: none; } }
        .hero-eyebrow {
            font-family: var(--font-mono); font-size: 11.5px; font-weight: 700;
            letter-spacing: 2px; text-transform: uppercase; color: var(--ink-soft);
            margin-bottom: 10px;
        }
        .hero-title {
            font-family: var(--font-display); font-size: 140px; line-height: 0.9;
            font-weight: 700; letter-spacing: 1px; margin: 0 0 6px 0;
            color: #000; -webkit-text-stroke: 1.5px #000;
        }
        .hero-squiggle { display: block; margin: 0 auto 18px auto; }
        .hero-sub { color: var(--ink-soft); font-size: 17px; max-width: 620px; line-height: 1.55; margin: 0 auto; }

        .badge-row { margin-top: 28px; display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; width: 100%; }
        .badge {
            padding: 12px 14px; border-radius: 12px; font-size: 13px; font-weight: 700;
            background: var(--paper-2); color: var(--ink);
            display: flex; align-items: center; justify-content: center; gap: 9px;
        }
        .badge::before {
            content: ""; width: 11px; height: 11px; border-radius: 50%;
            background: var(--line-shadow); border: 1.5px solid var(--ink); flex-shrink: 0;
        }
        .badge-row .badge:nth-child(1) { --line-shadow: var(--sky); }
        .badge-row .badge:nth-child(2) { --line-shadow: var(--coral); }
        .badge-row .badge:nth-child(3) { --line-shadow: var(--grape); }
        .badge-row .badge:nth-child(4) { --line-shadow: var(--grass); }

        .stat-card { padding: 16px 14px; border-radius: 14px; background: var(--paper-2); text-align: center; --line-shadow: var(--sunshine); }
        .stat-value { font-family: var(--font-mono); font-size: 26px; font-weight: 700; color: var(--ink); }
        .stat-label { font-size: 11.5px; color: var(--ink-soft); margin-top: 4px; text-transform: uppercase; letter-spacing: 0.8px; font-weight: 700; }

        .glass-card {
            padding: 26px 30px; margin-bottom: 24px; border-radius: 20px;
            background: var(--paper-2); box-shadow: 5px 5px 0 var(--line); border: 2px solid var(--ink);
        }

        .gesture-chip {
            display: inline-flex; align-items: center; gap: 8px; padding: 10px 16px;
            border-radius: 12px; margin: 6px 8px 6px 0; background: var(--paper-2);
            font-size: 13.5px; color: var(--ink); font-weight: 600;
        }
        .gesture-chip:nth-of-type(1) { --line-shadow: var(--coral); }
        .gesture-chip:nth-of-type(2) { --line-shadow: var(--sky); }
        .gesture-chip:nth-of-type(3) { --line-shadow: var(--ink-soft); }
        .gesture-chip:nth-of-type(4) { --line-shadow: var(--grass); }
        .gesture-chip:nth-of-type(5) { --line-shadow: var(--sunshine); }

        .empty-state {
            text-align: center; padding: 48px 20px; color: var(--ink-soft);
            border: 2px dashed var(--ink); border-radius: 16px; background: var(--paper); font-size: 15px;
        }
        .section-title {
            font-family: var(--font-mono); font-size: 12px; letter-spacing: 1.6px;
            text-transform: uppercase; color: var(--ink-soft); font-weight: 700; margin: 6px 0 12px 2px;
        }

        h1, h2, h3 { font-family: var(--font-body); font-weight: 800 !important; color: var(--ink); }

        .stButton > button {
            border-radius: 12px !important; border: 2px solid var(--ink) !important;
            background: var(--coral) !important; color: var(--ink) !important;
            font-weight: 700 !important; font-family: var(--font-body) !important;
            padding: 10px 20px !important; box-shadow: 3px 3px 0 var(--ink) !important;
            transition: transform 0.12s ease, box-shadow 0.12s ease !important;
        }
        .stButton > button:hover { transform: translate(-2px, -2px); box-shadow: 5px 5px 0 var(--ink) !important; }
        .stButton > button:active { transform: translate(1px, 1px); box-shadow: 1px 1px 0 var(--ink) !important; }

        .stDownloadButton > button {
            border-radius: 12px !important; background: var(--paper-2) !important;
            border: 2px solid var(--ink) !important; color: var(--ink) !important;
            font-weight: 700 !important; box-shadow: 3px 3px 0 var(--sky) !important;
        }

        .stTabs [data-baseweb="tab-list"] { gap: 6px; border-bottom: 2px solid var(--ink); }
        .stTabs [data-baseweb="tab"] {
            font-weight: 700; font-size: 14.5px; border-radius: 10px 10px 0 0; padding: 10px 18px;
            background: var(--paper); border: 2px solid var(--ink); border-bottom: none; color: var(--ink-soft);
        }
        .stTabs [aria-selected="true"] { background: var(--paper-2); color: var(--ink); }
        .stTabs [data-baseweb="tab-list"] button:nth-child(1)[aria-selected="true"] { border-top: 4px solid var(--coral); }
        .stTabs [data-baseweb="tab-list"] button:nth-child(2)[aria-selected="true"] { border-top: 4px solid var(--sky); }
        .stTabs [data-baseweb="tab-list"] button:nth-child(3)[aria-selected="true"] { border-top: 4px solid var(--grass); }
        .stTabs [data-baseweb="tab-list"] button:nth-child(4)[aria-selected="true"] { border-top: 4px solid var(--grape); }

        .stSlider [data-baseweb="slider"] > div > div { background: var(--coral) !important; }
        input[type="radio"] { accent-color: var(--coral); }
        .stCheckbox label p { font-weight: 600; }
        .stTextInput input { border-radius: 10px !important; border: 2px solid var(--ink) !important; font-family: var(--font-mono) !important; }
        div[data-testid="stImage"] img { border-radius: 12px !important; border: 2px solid var(--ink); }
        </style>
        """,
        unsafe_allow_html=True,
    )


CRITTER_PANDA = ""
<svg class="critter
