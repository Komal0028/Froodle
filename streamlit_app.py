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
RTC_CONFIGURATION = RTCConfiguration({"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]})
COLOR_DOTS = {"White": "⚪", "Red": "🔴", "Green": "🟢", "Blue": "🔵", "Yellow": "🟡", "Purple": "🟣"}


def load_css():
    css_path = os.path.join("assets", "style.css")
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
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


CRITTER_PANDA = """
<svg class="critter critter-panda" viewBox="0 0 160 160" xmlns="http://www.w3.org/2000/svg">
  <ellipse cx="80" cy="140" rx="46" ry="14" fill="#262322" opacity="0.08"/>
  <circle cx="80" cy="90" r="55" fill="#FFFFFF" stroke="#262322" stroke-width="4"/>
  <circle cx="34" cy="42" r="20" fill="#262322"/>
  <circle cx="126" cy="42" r="20" fill="#262322"/>
  <circle cx="34" cy="42" r="8" fill="#4A4642"/>
  <circle cx="126" cy="42" r="8" fill="#4A4642"/>
  <ellipse cx="55" cy="85" rx="16" ry="21" fill="#262322" transform="rotate(-12 55 85)"/>
  <ellipse cx="105" cy="85" rx="16" ry="21" fill="#262322" transform="rotate(12 105 85)"/>
  <circle cx="57" cy="90" r="5" fill="#FFFFFF"/>
  <circle cx="103" cy="90" r="5" fill="#FFFFFF"/>
  <circle cx="57" cy="91" r="2.5" fill="#262322"/>
  <circle cx="103" cy="91" r="2.5" fill="#262322"/>
  <ellipse cx="80" cy="112" rx="8" ry="5" fill="#262322"/>
  <path d="M72 122 Q80 128 88 122" stroke="#262322" stroke-width="3" fill="none" stroke-linecap="round"/>
  <circle cx="44" cy="108" r="7" fill="#FF6A52" opacity="0.35"/>
  <circle cx="116" cy="108" r="7" fill="#FF6A52" opacity="0.35"/>
</svg>
"""

CRITTER_ELEPHANT = """
<svg class="critter critter-elephant" viewBox="0 0 180 170" xmlns="http://www.w3.org/2000/svg">
  <ellipse cx="90" cy="150" rx="50" ry="14" fill="#262322" opacity="0.08"/>
  <ellipse cx="35" cy="85" rx="32" ry="38" fill="#C9D6E8" stroke="#262322" stroke-width="4"/>
  <ellipse cx="145" cy="85" rx="32" ry="38" fill="#C9D6E8" stroke="#262322" stroke-width="4"/>
  <circle cx="90" cy="88" r="58" fill="#DCE6F2" stroke="#262322" stroke-width="4"/>
  <path d="M72 128 Q64 158 78 168 Q86 172 88 160" fill="#DCE6F2" stroke="#262322" stroke-width="4" stroke-linecap="round"/>
  <circle cx="68" cy="82" r="6" fill="#262322"/>
  <circle cx="112" cy="82" r="6" fill="#262322"/>
  <circle cx="70" cy="80" r="2" fill="#FFFFFF"/>
  <circle cx="114" cy="80" r="2" fill="#FFFFFF"/>
  <circle cx="52" cy="104" r="7" fill="#FF6A52" opacity="0.3"/>
  <circle cx="128" cy="104" r="7" fill="#FF6A52" opacity="0.3"/>
  <path d="M66 108 Q90 122 114 108" stroke="#262322" stroke-width="3" fill="none" stroke-linecap="round"/>
</svg>
"""

CRITTER_BEAR = """
<svg class="critter critter-bear" viewBox="0 0 160 160" xmlns="http://www.w3.org/2000/svg">
  <ellipse cx="80" cy="140" rx="46" ry="14" fill="#262322" opacity="0.08"/>
  <circle cx="80" cy="90" r="55" fill="#D9A468" stroke="#262322" stroke-width="4"/>
  <circle cx="32" cy="40" r="21" fill="#D9A468" stroke="#262322" stroke-width="4"/>
  <circle cx="128" cy="40" r="21" fill="#D9A468" stroke="#262322" stroke-width="4"/>
  <circle cx="32" cy="40" r="9" fill="#F0C896"/>
  <circle cx="128" cy="40" r="9" fill="#F0C896"/>
  <ellipse cx="80" cy="102" rx="26" ry="20" fill="#F0C896" stroke="#262322" stroke-width="3.5"/>
  <circle cx="55" cy="85" r="6" fill="#262322"/>
  <circle cx="105" cy="85" r="6" fill="#262322"/>
  <circle cx="57" cy="83" r="2" fill="#FFFFFF"/>
  <circle cx="107" cy="83" r="2" fill="#FFFFFF"/>
  <ellipse cx="80" cy="98" rx="7" ry="5" fill="#262322"/>
  <path d="M80 103 L80 110" stroke="#262322" stroke-width="2.5"/>
  <path d="M70 112 Q80 118 90 112" stroke="#262322" stroke-width="3" fill="none" stroke-linecap="round"/>
  <circle cx="42" cy="106" r="7" fill="#FF6A52" opacity="0.3"/>
  <circle cx="118" cy="106" r="7" fill="#FF6A52" opacity="0.3"/>
</svg>
"""

CRITTER_GIRAFFE = """
<svg class="critter critter-giraffe" viewBox="0 0 160 170" xmlns="http://www.w3.org/2000/svg">
  <ellipse cx="80" cy="150" rx="44" ry="13" fill="#262322" opacity="0.08"/>
  <rect x="62" y="88" width="36" height="55" rx="16" fill="#F2C879" stroke="#262322" stroke-width="4"/>
  <circle cx="80" cy="75" r="48" fill="#F2C879" stroke="#262322" stroke-width="4"/>
  <path d="M62 40 L58 20" stroke="#262322" stroke-width="5" stroke-linecap="round"/>
  <path d="M98 40 L102 20" stroke="#262322" stroke-width="5" stroke-linecap="round"/>
  <circle cx="58" cy="18" r="7" fill="#D9A468" stroke="#262322" stroke-width="3.5"/>
  <circle cx="102" cy="18" r="7" fill="#D9A468" stroke="#262322" stroke-width="3.5"/>
  <ellipse cx="80" cy="98" rx="20" ry="16" fill="#FBEBD0" stroke="#262322" stroke-width="3"/>
  <circle cx="60" cy="72" r="6" fill="#262322"/>
  <circle cx="100" cy="72" r="6" fill="#262322"/>
  <circle cx="62" cy="70" r="2" fill="#FFFFFF"/>
  <circle cx="102" cy="70" r="2" fill="#FFFFFF"/>
  <ellipse cx="80" cy="102" rx="6" ry="4" fill="#262322"/>
  <ellipse cx="40" cy="55" rx="8" ry="6" fill="#B9793B" opacity="0.7"/>
  <ellipse cx="118" cy="60" rx="7" ry="9" fill="#B9793B" opacity="0.7"/>
  <ellipse cx="70" cy="120" rx="7" ry="9" fill="#B9793B" opacity="0.6"/>
  <ellipse cx="92" cy="130" rx="8" ry="6" fill="#B9793B" opacity="0.6"/>
</svg>
"""


def render_hero():
    st.markdown(
        f"""
        <div class="hero">
            {CRITTER_PANDA}{CRITTER_ELEPHANT}{CRITTER_BEAR}{CRITTER_GIRAFFE}
            <div class="hero-content">
                <div class="hero-eyebrow">Air-drawing, sketched in real time</div>
                <div class="hero-title">Froodle</div>
                <svg class="hero-squiggle" width="220" height="18" viewBox="0 0 220 18" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M3 12C20 3 35 3 52 10C69 17 84 5 101 6C118 7 130 15 148 9C166 3 180 12 198 8C207 6 213 9 217 12"
                          stroke="#FF6A52" stroke-width="4" stroke-linecap="round"/>
                </svg>
                <div class="hero-sub">i am still figuring out what to write here...</div>
                <div class="badge-row">
                    <span class="badge">🧠 MediaPipe Hand Tracking</span>
                    <span class="badge">🎨 OpenCV Rendering</span>
                    <span class="badge">🤖 GPT-4o Vision (under construction..)</span>
                    <span class="badge">⚡ Real-time, local, no cloud needed</span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_stats(num_drawings, ai_ready):
    cols = st.columns(4)
    stats = [("21", "Hand Landmarks"), (str(num_drawings), "Saved Drawings"),
             ("5", "Gestures Mapped"), ("On" if ai_ready else "Off", "AI Explain")]
    for col, (value, label) in zip(cols, stats):
        with col:
            st.markdown(
                f'<div class="stat-card"><div class="stat-value">{value}</div>'
                f'<div class="stat-label">{label}</div></div>',
                unsafe_allow_html=True,
            )


def render_draw_tab():
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader("happy drawing")
    st.write("Allow camera access below, then raise only your index finger and start drawing twin.")

    col_video, col_controls = st.columns([2, 1])

    with col_controls:
        st.markdown("**Color**")
        color_options = list(COLOR_PALETTE.keys())[:-1]
        color_name = st.radio(
            "Color", color_options,
            format_func=lambda c: f"{c}  {COLOR_DOTS.get(c, "🎨")}",
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
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader("💻 Launch Native Window (local only)")
    st.write(
        "If you're running this dashboard on your own computer (not a cloud deployment), "
        "you can alternatively launch the classic native OpenCV window — slightly lower "
        "latency than the browser version above."
    )
    if st.button("▶  Start Native Whiteboard", use_container_width=True):
        try:
            main_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
            if not os.path.isfile(main_path):
                st.error("main.py was not found in the project folder.")
            else:
                subprocess.Popen([sys.executable, main_path])
                st.success("Whiteboard launched — check for a new window!")
        except Exception as e:
            st.error(f"Could not launch whiteboard: {e}")
    st.caption(
        "⚠️ This button does nothing useful when the app is deployed to a server "
        "(e.g. Streamlit Community Cloud) — use the **Draw in Browser** tab instead."
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
            '<div class="empty-state">🖌️ No drawings yet.<br>'
            'Launch the whiteboard and press <b>👍</b> or the Save button to see it here.</div>',
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

    current_key_set = bool(st.session_state.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY"))
    st.caption(f"OpenAI API key status: **{'✅ Configured' if current_key_set else '⚪ Not set'}**")

    key_input = st.text_input("OpenAI API Key (optional — only needed for 'Explain My Drawing')",
                               type="password", placeholder="sk-...")
    if st.button("Save Key", type="primary"):
        if key_input:
            os.environ["OPENAI_API_KEY"] = key_input
            st.session_state["OPENAI_API_KEY"] = key_input
            st.success("API key set for this session.")
            time.sleep(0.6)
            st.rerun()
        else:
            st.warning("Paste a key first.")

    st.divider()
    st.caption(
        "The core whiteboard (drawing, erasing, saving) never requires an API key or "
        "internet connection — this only powers the optional AI description feature."
    )
    st.markdown("</div>", unsafe_allow_html=True)


def main():
    st.set_page_config(page_title="AI Air Whiteboard", page_icon="✋", layout="wide")
    load_css()
    render_hero()

    os.makedirs(SAVED_DIR, exist_ok=True)
    num_drawings = len(glob.glob(os.path.join(SAVED_DIR, "*.png")))
    ai_ready = bool(st.session_state.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY"))
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
