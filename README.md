# ☆ Froodle

Draw in the air with your bare hand. Your webcam + an AI hand-tracking
model turn your index fingertip into a pen, and your movements appear as
smooth ink on a virtual whiteboard overlaid on the live video.

## Features
- Draw, Erase, Clear, Undo, Redo, 6 colors, adjustable brush size
- Save as PNG, gallery of saved drawings, download button
- Toggle camera, fullscreen mode, live FPS counter
- Real-time hand tracking, hand-confidence score, landmark toggle
- Gestures: Index=draw, Index+Middle=move, Fist=erase, Thumb up=save, Open palm(hold)=clear
- Optional "Explain My Drawing" via GPT-4o Vision
- Dark glassmorphism dashboard (Streamlit) with hero section, stat cards, tabs

## Technologies
Python · OpenCV · MediaPipe · NumPy · Streamlit · OpenAI API (GPT-4o)

## Installation
```bash
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
```
Optional, for "Explain My Drawing":
```bash
export OPENAI_API_KEY=sk-...   # Windows: set OPENAI_API_KEY=sk-...
```

## Run

**Locally (native window, lowest latency):**
```bash
python main.py
```
Quit the whiteboard window with `q` or `Esc`.

**Locally or deployed (browser-based, works from any device):**
```bash
streamlit run streamlit_app.py
```
Open the **🎥 Draw in Browser** tab, click START, allow camera access.
This uses WebRTC so it also works once deployed to Streamlit Community
Cloud — the video streams through the *visitor's own browser and
webcam*, not the server's.


## Folder Structure
```
AI-Air-Whiteboard/
├── main.py            
├── hand_tracker.py    
├── drawing.py        
├── ai_explainer.py    
├── streamlit_app.py  
├── utils.py           
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
└── assets/
    ├── style.css
    └── saved/
```



## Future Improvements
Two-hand drawing, shape tools, voice commands, auto-save, PDF export,
virtual laser pointer, cloud sync of saved drawings.
