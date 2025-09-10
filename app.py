# app.py — Zentra (final polish)

import io
import os
import base64
import streamlit as st
from openai import OpenAI

# ---------- CONFIG ----------
st.set_page_config(page_title="Zentra — AI Study Buddy", page_icon="⚡", layout="wide")

# Hide Streamlit UI
st.markdown("""
<style>
[data-testid="stToolbar"], [data-testid="stDecoration"], header {visibility: hidden; height: 0;}
footer {visibility: hidden;}
a[class*="viewerBadge"], div[class*="viewerBadge"], #ViewerBadgeContainer {display:none !important;}
.block-container {padding-top: 1.2rem; padding-bottom: 4rem; max-width: 1200px;}
.hero {background: linear-gradient(90deg,#6a11cb 0%,#2575fc 100%); padding: 24px; border-radius: 18px; color: #fff;}
.hero h1 {font-size: 36px; margin: 0 0 6px 0;}
.hero p {opacity: .92; margin: 0;}
.tool-btn {display:inline-block; padding:10px 16px; border-radius:12px; background:#111; color:#fff; margin:10px 10px 0 0;}
.tool-btn:hover {background:#1b1b1b;}
#ask-bubble {position: fixed; right: 26px; top: 26px; z-index: 999;}
.ask-panel {position: fixed; right: 26px; top: 86px; width: min(420px, 92vw); height: 70vh;
            background:#0e1117; border:1px solid #333; border-radius:14px; box-shadow:0 10px 30px rgba(0,0,0,.45);}
.ask-header {display:flex; justify-content:space-between; align-items:center; padding:12px 14px; border-bottom:1px solid #222;}
.ask-body {padding:12px; height: calc(70vh - 130px); overflow:auto;}
.ask-input {position:absolute; bottom:12px; left:12px; right:12px;}
</style>
""", unsafe_allow_html=True)

# ---------- STATE ----------
if "show_chat" not in st.session_state: st.session_state.show_chat = False
if "chat" not in st.session_state: st.session_state.chat = []

# ---------- CLIENT ----------
def get_client() -> OpenAI:
    key = st.secrets.get("OPENAI_API_KEY", None)
    if not key:
        st.error("Missing OPENAI_API_KEY in Streamlit Secrets.")
        st.stop()
    os.environ["OPENAI_API_KEY"] = key
    return OpenAI()

MODEL = "gpt-4o-mini"

def ask_openai(prompt: str):
    client = get_client()
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role":"system","content":"You are a helpful study assistant."},
                  {"role":"user","content":prompt}],
        temperature=0.4,
    )
    return resp.choices[0].message.content.strip()

# ---------- SIDEBAR ----------
with st.sidebar:
    st.markdown("### ℹ️ About Zentra")
    st.write("Zentra accelerates learning with clean summaries, flashcards, adaptive quizzes, and mock exams — plus an AI tutor.")

    st.markdown("### 🛠️ Tools")
    st.markdown("- **Summaries** → exam-ready notes\n- **Flashcards** → spaced-repetition\n- **Quizzes** → adaptive MCQs\n- **Mock Exams** → full exam with rubric\n- **Ask Zentra** → your study tutor")

    st.markdown("### 🧪 Mock Evaluation")
    st.write("Sections: MCQs, short/long answer, fill-ins. Marking scales with note length. Difficulty: Easy / Standard / Hard.")

    st.markdown("---")
    st.caption("Disclaimer: Zentra is an AI assistant. Always verify before exams.")

# ---------- HERO ----------
st.markdown(
    """
<div class="hero">
  <h1>⚡ Zentra — AI Study Buddy</h1>
  <p>Smarter notes → Better recall → Higher scores.</p>
</div>
""",
    unsafe_allow_html=True,
)

st.info("👋 Welcome to Zentra! Upload your notes and let AI transform them into study material.", icon="👋")

# ---------- UPLOAD ----------
st.markdown("### 📁 Upload your notes")
uploaded = st.file_uploader("Drag and drop files here", type=["pdf","docx","txt","png","jpg","jpeg"])
pasted = st.text_area("Or paste your notes here…", height=120, label_visibility="collapsed")
mode = st.radio("Analysis mode", ["Text only","Include images (Vision)"], horizontal=True)

# ---------- TOOLS ----------
st.markdown("### ✨ Study Tools")
c1,c2,c3,c4,c5 = st.columns(5)
with c1: st.button("📄 Summaries", help="Turn notes into clean exam-style summaries.")
with c2: st.button("🧠 Flashcards", help="Generate spaced-repetition flashcards.")
with c3: st.button("🎯 Quizzes", help="Adaptive MCQs with explanations.")
with c4: st.button("📝 Mock Exams", help="Multi-section exam with marking rubric.")
with c5:
    if st.button("💬 Ask Zentra", help="Ask about any subject or concept."):
        st.session_state.show_chat = True

# ---------- CHAT ----------
if st.session_state.show_chat:
    st.markdown('<div class="ask-panel">', unsafe_allow_html=True)
    st.markdown('<div class="ask-header"><b>💬 Ask Zentra</b> <span style="cursor:pointer;" onclick="window.parent.postMessage({type:\'closeChat\'}, \'*\')">✖</span></div>', unsafe_allow_html=True)
    st.markdown('<div class="ask-body">', unsafe_allow_html=True)

    for role,msg in st.session_state.chat:
        st.markdown(f"**{'You' if role=='user' else 'Zentra'}:** {msg}")

    st.markdown('</div>', unsafe_allow_html=True)

    q = st.text_input("Type your question", key="ask_input")
    if st.button("Send", key="ask_send"):
        if q.strip():
            st.session_state.chat.append(("user", q))
            ans = ask_openai(q)
            st.session_state.chat.append(("assistant", ans))
            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)
