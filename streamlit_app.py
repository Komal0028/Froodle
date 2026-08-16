

import os
import glob
import subprocess
import sys
import time

import streamlit as st
from streamlit_webrtc import webrtc_streamer, RTCConfiguration, WebRtcMode

from ai_explainer import DrawingExplainer
from webrtc_processor import WhiteboardProcessor
from utils import COLOR_PALETTE, MIN_BRUSH_SIZE, MAX_BRUSH_SIZE, DEFAULT_BRUSH_SIZE

SAVED_DIR = "assets/saved"

# Public STUN server so WebRTC can establish a peer connection through
# NATs/firewalls once this app is deployed to a real server (Streamlit
# Community Cloud, etc). Without this, the browser<->server video
# connection often fails to negotiate outside of localhost.
RTC_CONFIGURATION = RTCConfiguration(
    {"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]}
)


# =====================================================================
# STYLING
# =====================================================================
def load_css():
    """Loads the shared theme, then layers page-specific rules on top
    (hero banner, gesture chips, stat strip, empty state) so the whole
    dashboard shares one visual language: a hand-drawn marker/notebook
    aesthetic, since this is literally an app for drawing with your
    finger — the chrome should feel sketched, not shipped as a generic
    dark-mode admin panel."""
    css_path = os.path.join("assets", "style.css")
    if os.path.exists(css_path):
        with open(css_path) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Caveat:wght@600;700&family=Manrope:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;700&display=swap');

        :root {
            --ink:      #262322;
            --ink-soft: #6b665f;
            --paper:    #FBF6EC;
            --paper-2:  #FFFFFF;
            --line:     rgba(38,35,34,0.10);
            --coral:    #FF6A52;
            --sky:      #2F8FE0;
            --sunshine: #F2A93C;
            --grass:    #3FA772;
            --grape:    #8B6BE8;

            --font-display: 'Caveat', cursive;
            --font-body: 'Manrope', -apple-system, sans-serif;
            --font-mono: 'JetBrains Mono', monospace;
        }

        #MainMenu, footer, header {visibility: hidden;}

        .stApp {
            background-color: var(--paper);
            background-image: radial-gradient(var(--line) 1.4px, transparent 1.4px);
            background-size: 24px 24px;
        }
        html, body, [class*="css"] { font-family: var(--font-body); color: var(--ink); }
        p, span, div, label { color: var(--ink); }

        /* ---------- signature: sketchy double-outline ----------
           An ink border plus an offset flat shadow, like a shape
           drawn twice by hand with a marker slightly out of register.
           Used consistently on cards, chips, badges and buttons so it
           reads as one deliberate motif rather than decoration. */
        .note-card, .badge, .gesture-chip, .stat-card {
            border: 2px solid var(--ink);
            box-shadow: 4px 4px 0 var(--line-shadow, var(--coral));
        }

        /* ---------- hero ---------- */
        .hero {
            padding: 44px 40px 38px;
            border-radius: 22px;
            margin-bottom: 26px;
            background: var(--paper-2);
            border: 2px solid var(--ink);
            box-shadow: 6px 6px 0 var(--line);
            position: relative;
        }
        .hero-eyebrow {
            font-family: var(--font-mono);
            font-size: 11.5px; font-weight: 700; letter-spacing: 2px;
            text-transform: uppercase; color: var(--ink-soft);
            margin-bottom: 6px;
        }
        .hero-title {
            font-family: var(--font-display);
            font-size: 76px;
            line-height: 0.95;
            font-weight: 700;
            letter-spacing: 0.5px;
            margin: 0 0 4px 0;
            color: var(--ink);
            display: inline-block;
        }
        .hero-squiggle { display: block; margin: 2px 0 14px -4px; }
        .hero-sub { color: var(--ink-soft); font-size: 17px; max-width: 620px; line-height: 1.55; }

        .badge-row { margin-top: 22px; display: flex; gap: 12px; flex-wrap: wrap; }
        .badge {
            padding: 7px 16px; border-radius: 999px; font-size: 13px; font-weight: 700;
            background: var(--paper-2); color: var(--ink);
        }
        .badge-row .badge:nth-child(1) { --line-shadow: var(--sky); }
        .badge-row .badge:nth-child(2) { --line-shadow: var(--coral); }
        .badge-row .badge:nth-child(3) { --line-shadow: var(--grape); }
        .badge-row .badge:nth-child(4) { --line-shadow: var(--grass); }

        /* ---------- stat strip ---------- */
        .stat-card {
            padding: 16px 14px; border-radius: 14px;
            background: var(--paper-2);
            text-align: center;
            --line-shadow: var(--sunshine);
        }
        .stat-value {
            font-family: var(--font-mono); font-size: 26px; font-weight: 700; color: var(--ink);
        }
        .stat-label {
            font-family: var(--font-body); font-size: 11.5px; color: var(--ink-soft);
            margin-top: 4px; text-transform: uppercase; letter-spacing: 0.8px; font-weight: 700;
        }

        /* ---------- generic content card ---------- */
        .glass-card {
            padding: 26px 30px;
            margin-bottom: 24px;
            border-radius: 20px;
            background: var(--paper-2);
            box-shadow: 5px 5px 0 var(--line);
            border: 2px solid var(--ink);
        }

        /* ---------- gesture chips ---------- */
        .gesture-chip {
            display: inline-flex; align-items: center; gap: 8px;
            padding: 10px 16px; border-radius: 12px; margin: 6px 8px 6px 0;
            background: var(--paper-2); font-size: 13.5px; color: var(--ink); font-weight: 600;
        }
        .gesture-chip b { color: var(--ink); }
        .gesture-chip:nth-of-type(1) { --line-shadow: var(--coral); }
        .gesture-chip:nth-of-type(2) { --line-shadow: var(--sky); }
        .gesture-chip:nth-of-type(3) { --line-shadow: var(--ink-soft); }
        .gesture-chip:nth-of-type(4) { --line-shadow: var(--grass); }
        .gesture-chip:nth-of-type(5) { --line-shadow: var(--sunshine); }

        .empty-state {
            text-align: center; padding: 48px 20px; color: var(--ink-soft);
            border: 2px dashed var(--ink); border-radius: 16px; background: var(--paper);
            font-size: 15px;
        }

        .section-title {
            font-family: var(--font-mono);
            font-size: 12px; letter-spacing: 1.6px; text-transform: uppercase;
            color: var(--ink-soft); font-weight: 700; margin: 6px 0 12px 2px;
        }

        /* ---------- headings ---------- */
        h1, h2, h3 { font-family: var(--font-body); font-weight: 800 !important; color: var(--ink); }

        /* ---------- buttons ---------- */
        .stButton > button {
            border-radius: 12px !important;
            border: 2px solid var(--ink) !important;
            background: var(--coral) !important;
            color: var(--ink) !important;
            font-weight: 700 !important;
            font-family: var(--font-body) !important;
            padding: 10px 20px !important;
            box-shadow: 3px 3px 0 var(--ink) !important;
            transition: transform 0.12s ease, box-shadow 0.12s ease !important;
        }
        .stButton > button:hover {
            transform: translate(-2px, -2px);
            box-shadow: 5px 5px 0 var(--ink) !important;
        }
        .stButton > button:active {
            transform: translate(1px, 1px);
            box-shadow: 1px 1px 0 var(--ink) !important;
        }

        .stDownloadButton > button {
            border-radius: 12px !important;
            background: var(--paper-2) !important;
            border: 2px solid var(--ink) !important;
            color: var(--ink) !important;
            font-weight: 700 !important;
            box-shadow: 3px 3px 0 var(--sky) !important;
        }

        /* ---------- tabs, styled as notebook index tabs ---------- */
        .stTabs [data-baseweb="tab-list"] { gap: 6px; border-bottom: 2px solid var(--ink); }
        .stTabs [data-baseweb="tab"] {
            font-family: var(--font-body); font-weight: 700; font-size: 14.5px;
            border-radius: 10px 10px 0 0;
            padding: 10px 18px;
            background: var(--paper);
            border: 2px solid var(--ink); border-bottom: none;
            color: var(--ink-soft);
        }
        .stTabs [aria-selected="true"] { background: var(--paper-2); color: var(--ink); }
        .stTabs [data-baseweb="tab-list"] button:nth-child(1)[aria-selected="true"] { border-top: 4px solid var(--coral); }
        .stTabs [data-baseweb="tab-list"] button:nth-child(2)[aria-selected="true"] { border-top: 4px solid var(--sky); }
        .stTabs [data-baseweb="tab-list"] button:nth-child(3)[aria-selected="true"] { border-top: 4px solid var(--grass); }
        .stTabs [data-baseweb="tab-list"] button:nth-child(4)[aria-selected="true"] { border-top: 4px solid var(--grape); }

        /* ---------- form controls ---------- */
        .stSlider [data-baseweb="slider"] > div > div { background: var(--coral) !important; }
        input[type="radio"] { accent-color: var(--coral); }
        .stCheckbox label p { font-weight: 600; }
        .stTextInput input {
            border-radius: 10px !important; border: 2px solid var(--ink) !important;
            font-family: var(--font-mono) !important;
        }

        div[data-testid="stImage"] img {
            border-radius: 12px !important;
            border: 2px solid var(--ink);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# =====================================================================
# LAYOUT PIECES
# =====================================================================
def render_hero():
    st.markdown(
        """
        <div class="hero" style="text-align: center;">
            <div class="hero-eyebrow">Air-drawing, sketched in real time</div>
            <div class="hero-title">Froodle</div>
            <svg class="hero-squiggle" width="220" height="18" viewBox="0 0 220 18" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M3 12C20 3 35 3 52 10C69 17 84 5 101 6C118 7 130 15 148 9C166 3 180 12 198 8C207 6 213 9 217 12"
                      stroke="#FF6A52" stroke-width="4" stroke-linecap="round"/>
            </svg>
            <div class="hero-sub" style="text-align: center;">
                i am still figuring out what to write here...
            </div>
            <div class="badge-row">
                <span class="badge">🧠 MediaPipe Hand Tracking</span>
                <span class="badge">🎨 OpenCV Rendering</span>
                <span class="badge">🤖 GPT-4o Vision (under construction..)</span>
                <span class="badge">⚡ Real-time, local, no cloud needed</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_stats(num_drawings: int, ai_ready: bool):
    col1, col2, col3, col4 = st.columns(4)
    stats = [
        (col1, "21", "Hand Landmarks"),
        (col2, str(num_drawings), "Saved Drawings"),
        (col3, "5", "Gestures Mapped"),
        (col4, "On" if ai_ready else "Off", "AI Explain"),
    ]
    for col, value, label in stats:
        with col:
            st.markdown(
                f"""<div class="stat-card">
                        <div class="stat-value">{value}</div>
                        <div class="stat-label">{label}</div>
                    </div>""",
                unsafe_allow_html=True,
            )


def render_draw_tab():
    """
    The browser-based whiteboard. Works both locally AND once deployed —
    the webcam feed streams from the visitor's own browser via WebRTC,
    gets processed frame-by-frame on the server (hand tracking + drawing),
    and streams back. No native window, no local-only subprocess.
    """
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader("happy drawing")
    st.write(
        "Allow camera access below, then raise only your index finger "
        "and start drawing twin."

    )

    col_video, col_controls = st.columns([2, 1])

    with col_controls:
        st.markdown("**Color**")
        color_name = st.radio(
            "Color", list(COLOR_PALETTE.keys())[:-1],  # exclude "Eraser" from the picker
            horizontal=True, label_visibility="collapsed",
        )
        brush_size = st.slider("Brush size", MIN_BRUSH_SIZE, MAX_BRUSH_SIZE, DEFAULT_BRUSH_SIZE)
        show_landmarks = st.checkbox("Show hand landmarks", value=False)

        st.markdown("**Actions**")
        btn_col1, btn_col2 = st.columns(2)
        clear_clicked = btn_col1.button("🧹 Clear", use_container_width=True)
        undo_clicked = btn_col2.button("↩️ Undo", use_container_width=True)
        btn_col3, btn_col4 = st.columns(2)
        redo_clicked = btn_col3.button("↪️ Redo", use_container_width=True)
        save_clicked = btn_col4.button("💾 Save", use_container_width=True)

    with col_video:
        ctx = webrtc_streamer(
            key="ai-air-whiteboard",
            mode=WebRtcMode.SENDRECV,
            rtc_configuration=RTC_CONFIGURATION,
            video_processor_factory=WhiteboardProcessor,
            media_stream_constraints={"video": True, "audio": False},
            async_processing=True,
        )

    # Push the sidebar's current settings into the live processor instance.
    # video_processor is only available once the stream has actually started.
    if ctx.video_processor:
        ctx.video_processor.current_color_name = color_name
        ctx.video_processor.brush_size = brush_size
        ctx.video_processor.show_landmarks = show_landmarks

        if clear_clicked:
            ctx.video_processor.request_clear()
        if undo_clicked:
            ctx.video_processor.request_undo()
        if redo_clicked:
            ctx.video_processor.request_redo()
        if save_clicked:
            ctx.video_processor.request_save()
            st.toast("Saved!", icon="💾")
    else:
        st.info("Click **START** above and allow camera access to begin.")

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="section-title">Gesture Guide</div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div>
            <span class="gesture-chip">☝️ <b>Index only</b> — Draw</span>
            <span class="gesture-chip">✌️ <b>Index + Middle</b> — Move (no draw)</span>
            <span class="gesture-chip">✊ <b>Closed fist</b> — Erase</span>
            <span class="gesture-chip">👍 <b>Thumb up</b> — Save</span>
            <span class="gesture-chip">🖐️ <b>Open palm (hold)</b> — Clear canvas</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_local_launch_tab():
    """Kept for people running this dashboard on their own laptop who
    prefer the lower-latency native OpenCV window instead."""
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader("💻 Launch Native Window (local only)")
    st.write(
        "If you're running this dashboard on your own computer (not a "
        "cloud deployment), you can alternatively launch the classic "
        "native OpenCV window — slightly lower latency than the browser "
        "version above."
    )
    if st.button("▶  Start Native Whiteboard", use_container_width=True):
        try:
            subprocess.Popen([sys.executable, "main.py"])
            st.success("Whiteboard launched — check for a new window!")
        except Exception as e:
            st.error(f"Could not launch whiteboard: {e}")
    st.caption(
        "⚠️ This button does nothing useful when the app is deployed to a "
        "server (e.g. Streamlit Community Cloud) — use the **Draw in "
        "Browser** tab instead in that case."
    )
    st.markdown("</div>", unsafe_allow_html=True)


def render_gallery_tab():
    os.makedirs(SAVED_DIR, exist_ok=True)
    images = sorted(glob.glob(os.path.join(SAVED_DIR, "*.png")), reverse=True)

    explainer = DrawingExplainer()

    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    header_col1, header_col2 = st.columns([3, 1])
    with header_col1:
        st.subheader("🖼️ Saved Drawings")
    with header_col2:
        if images:
            st.caption(f"{len(images)} saved")

    if not explainer.is_configured():
        st.caption("ℹ️ Set an OpenAI API key in **Settings** to enable 'Explain My Drawing'.")

    if not images:
        st.markdown(
            """<div class="empty-state">
                    🖌️ No drawings yet.<br>
                    Launch the whiteboard and press <b>👍</b> or the Save button to see it here.
                </div>""",
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)
        return

    cols = st.columns(3)
    for i, image_path in enumerate(images):
        with cols[i % 3]:
            st.image(image_path, caption=os.path.basename(image_path))
            btn_col1, btn_col2 = st.columns(2)
            with btn_col1:
                if st.button("🤖 Explain", key=f"explain_{i}", use_container_width=True):
                    with st.spinner("Looking at your drawing..."):
                        explanation = explainer.explain(image_path)
                    st.info(explanation)
            with btn_col2:
                with open(image_path, "rb") as f:
                    st.download_button(
                        "⬇ Download", f, file_name=os.path.basename(image_path),
                        mime="image/png", key=f"dl_{i}", use_container_width=True,
                    )
            st.write("")

    st.markdown("</div>", unsafe_allow_html=True)


def render_settings_tab():
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader("⚙️ Settings")

    current_key_set = bool(os.environ.get("OPENAI_API_KEY"))
    status_label = "✅ Configured" if current_key_set else "⚪ Not set"
    st.caption(f"OpenAI API key status: **{status_label}**")

    key_input = st.text_input(
        "OpenAI API Key (optional — only needed for 'Explain My Drawing')",
        type="password",
        placeholder="sk-...",
    )
    if st.button("Save Key", type="primary"):
        if key_input:
            os.environ["OPENAI_API_KEY"] = key_input
            st.success("API key set for this session.")
            time.sleep(0.6)
            st.rerun()
        else:
            st.warning("Paste a key first.")

    st.divider()
    st.caption(
        "The core whiteboard (drawing, erasing, saving) never requires an "
        "API key or internet connection — this only powers the optional "
        "AI description feature."
    )
    st.markdown("</div>", unsafe_allow_html=True)


# =====================================================================
# MAIN
# =====================================================================
def main():
    st.set_page_config(page_title="AI Air Whiteboard", page_icon="✋", layout="wide")
    load_css()
    render_hero()

    os.makedirs(SAVED_DIR, exist_ok=True)
    num_drawings = len(glob.glob(os.path.join(SAVED_DIR, "*.png")))
    ai_ready = bool(os.environ.get("OPENAI_API_KEY"))
    render_stats(num_drawings, ai_ready)

    st.write("")
    tab_draw, tab_local, tab_gallery, tab_settings = st.tabs(
        ["🎥 Draw in Browser", "💻 Local Launch", "🖼️ Gallery", "⚙️ Settings"]
    )
    with tab_draw:
        render_draw_tab()
    with tab_local:
        render_local_launch_tab()
    with tab_gallery:
        render_gallery_tab()
    with tab_settings:
        render_settings_tab()


if __name__ == "__main__":
    main()
