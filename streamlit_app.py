"""
streamlit_app.py
-----------------
WHY THIS FILE EXISTS:
Real-time hand-tracking needs a tight webcam-read -> AI-inference ->
draw loop, running dozens of times per second. Streamlit's execution
model (re-running the whole script on every interaction) isn't built
for that kind of continuous native-webcam loop, so the actual drawing
experience lives in main.py using a normal OpenCV window (this is the
same architecture real "AI Virtual Painter" apps use).

This file is the *dashboard*: a premium-looking control center where the
user launches the whiteboard, browses saved drawings, and runs the
"Explain My Drawing" generative-AI feature on any saved PNG.

RUN WITH:
    streamlit run streamlit_app.py
"""

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
    """Loads the shared glassmorphism theme, then layers page-specific
    rules on top (hero banner, gesture chips, stat cards, empty state)
    so the whole dashboard shares one visual language."""
    css_path = os.path.join("assets", "style.css")
    if os.path.exists(css_path):
        with open(css_path) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

    st.markdown(
        """
        <style>
        #MainMenu, footer, header {visibility: hidden;}

        .hero {
            padding: 46px 40px;
            border-radius: 24px;
            margin-bottom: 22px;
            background: linear-gradient(135deg, rgba(99,102,241,0.20), rgba(236,72,153,0.14) 60%, rgba(14,165,233,0.16));
            border: 1px solid rgba(255,255,255,0.08);
            box-shadow: 0 10px 40px rgba(0,0,0,0.35);
            position: relative;
            overflow: hidden;
        }
        .hero::after {
            content: "";
            position: absolute; inset: 0;
            background: radial-gradient(circle at 85% 20%, rgba(167,139,250,0.25), transparent 55%);
            pointer-events: none;
        }
        .hero-title {
            font-size: 42px;
            font-weight: 800;
            letter-spacing: -1px;
            margin: 0 0 6px 0;
            background: linear-gradient(90deg, #a5b4fc, #f0abfc, #7dd3fc);
            -webkit-background-clip: text; background-clip: text; color: transparent;
        }
        .hero-sub { color: #b7bcd0; font-size: 16px; max-width: 640px; }
        .badge-row { margin-top: 18px; display: flex; gap: 10px; flex-wrap: wrap; }
        .badge {
            padding: 6px 14px; border-radius: 999px; font-size: 12.5px; font-weight: 600;
            background: rgba(255,255,255,0.07); border: 1px solid rgba(255,255,255,0.12); color: #d8dbea;
        }

        .stat-card {
            padding: 18px 20px; border-radius: 16px;
            background: rgba(255,255,255,0.045);
            border: 1px solid rgba(255,255,255,0.08);
            text-align: center;
            transition: transform 0.15s ease;
        }
        .stat-card:hover { transform: translateY(-3px); }
        .stat-value { font-size: 26px; font-weight: 800; color: #e6e8f5; }
        .stat-label { font-size: 12.5px; color: #9aa0b4; margin-top: 2px; text-transform: uppercase; letter-spacing: 0.5px; }

        .gesture-chip {
            display: inline-flex; align-items: center; gap: 8px;
            padding: 10px 14px; border-radius: 14px; margin: 5px 6px 5px 0;
            background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.08);
            font-size: 13.5px; color: #dfe1ee;
        }
        .gesture-chip b { color: #c4b5fd; }

        .empty-state {
            text-align: center; padding: 46px 20px; color: #9aa0b4;
            border: 1px dashed rgba(255,255,255,0.15); border-radius: 16px;
        }

        .section-title {
            font-size: 13px; letter-spacing: 1.2px; text-transform: uppercase;
            color: #8f94ab; font-weight: 700; margin: 4px 0 10px 2px;
        }

        div[data-testid="stImage"] img {
            border-radius: 14px;
            border: 1px solid rgba(255,255,255,0.08);
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
        <div class="hero">
            <div class="hero-title">Froodle</div>
            <div class="hero-sub">
                Turn your webcam into a pen. Real-time hand tracking with
                MediaPipe + OpenCV lets you draw in the air — no mouse,
                no touchscreen, just your index finger.
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
