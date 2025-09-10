# app.py — Zentra Final Polished

import io
import os
import base64
import streamlit as st
from openai import OpenAI
from typing import List, Tuple

# ---------- PAGE CONFIG ----------
st.set_page_config(page_title="Zentra — AI Study Buddy", page_icon="⚡", layout="wide")

# ---------- HIDE STREAMLIT DEFAULT UI ----------
st.markdown("""
<style>
[data-testid="stToolbar"], [data-testid="stDecoration"], header {visibility: hidden;}
footer {visibility: hidden;}
a[class*="viewerBadge"], div[class*="viewerBadge"], #ViewerBadgeContainer {display:none !important;}
.block-container {padding-top: 1.2rem; padding-bottom: 4rem; max-width: 1200px;}
.hero {background: linear-gradient(90deg,#6a11cb 0%,#2575fc 100%); padding: 22px; border-radius: 14px; color: #fff;}
.hero h1 {font-size: 34px; margin: 0;}
.hero p {margin: 0; opacity: .9;}
.ask-panel {position: fixed; right: 26px; top: 100px; width: min(400px, 90vw); height: 70vh; background:#0e1117; border:1px solid #333; border-radius:12px; box-shadow:0 10px 30px rgba(0,0,0,.45); padding:10px; z-index:9999;}
.ask-header {display:flex; justify-content:space-between; align-items:center; padding:6px 10px; border-bottom:1px solid #222;}
.ask-body {padding:8px; height: calc(70vh - 130px); overflow-y:auto;}
</style>
""", unsafe_allow_html=True)

# ---------- STATE ----------
if "history_quiz" not in st.session_state: st.session_state.history_quiz = []
if "history_mock" not in st.session_state: st.session_state.history_mock = []
if "show_chat" not in st.session_state: st.session_state.show_chat = False
if "chat" not in st.session_state: st.session_state.chat = []
if "notes_text" not in st.session_state: st.session_state.notes_text = ""
if "last_title" not in st.session_state: st.session_state.last_title = "Untitled notes"

# ---------- OPENAI ----------
def get_client() -> OpenAI:
    key = st.secrets.get("OPENAI_API_KEY", None)
    if not key:
        st.error("Missing OPENAI_API_KEY in Secrets")
        st.stop()
    os.environ["OPENAI_API_KEY"] = key
    return OpenAI()

MODEL_TEXT = "gpt-4o-mini"

def ask_openai(prompt: str):
    client = get_client()
    resp = client.chat.completions.create(
        model=MODEL_TEXT,
        messages=[{"role":"system","content":"You are Zentra, an AI tutor. Be clear, concise, and supportive."},
                  {"role":"user","content":prompt}],
        temperature=0.4,
    )
    return resp.choices[0].message.content.strip()

# ---------- FILE HANDLER ----------
def read_file(uploaded) -> str:
    if not uploaded: return ""
    name = uploaded.name.lower()
    data = uploaded.read()
    text = ""
    if name.endswith(".txt"):
        text = data.decode("utf-8", errors="ignore")
    elif name.endswith(".pdf"):
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data))
            pages = [p.extract_text() or "" for p in reader.pages]
            text = "\n".join(pages)
        except: text = ""
    elif name.endswith(".docx"):
        try:
            import docx2txt
            text = docx2txt.process(io.BytesIO(data))
        except: text = ""
    return text.strip()

def ensure_notes(text_area, upload) -> str:
    txt = text_area.strip()
    if upload:
        up_text = read_file(upload)
        if up_text:
            txt = (txt + "\n" + up_text).strip() if txt else up_text
        st.session_state.last_title = upload.name
    if not txt:
        st.warning("Upload a file or paste notes first.")
        st.stop()
    st.session_state.notes_text = txt
    return txt

# ---------- SIDEBAR ----------
with st.sidebar:
    st.markdown("## 📊 Toolbox")
    st.write("**How Zentra Works**: Smarter notes → better recall → higher scores. Upload notes, and Zentra transforms them into learning tools.")
    st.markdown("### 🎯 What Zentra Offers")
    st.markdown("- **Summaries** → exam-ready bullets\n- **Flashcards** → Q/A recall\n- **Quizzes** → MCQs + explanations\n- **Mock Exams** → multi-section + rubric\n- **Ask Zentra** → interactive tutor")
    st.markdown("### 🧪 Mock Evaluation")
    st.write("Includes MCQs, short, long, fill-in. Difficulty: *Easy / Standard / Hard*. Scales with content. Graded with feedback.")
    st.markdown("### 📜 History")
    st.caption("Quizzes")
    st.write(st.session_state.history_quiz if st.session_state.history_quiz else "—")
    st.caption("Mocks")
    st.write(st.session_state.history_mock if st.session_state.history_mock else "—")
    st.markdown("---")
    st.caption("Disclaimer: AI-generated — verify before exams.")

# ---------- HERO ----------
st.markdown('<div class="hero"><h1>⚡ Zentra — AI Study Buddy</h1><p>Smarter notes → Better recall → Higher scores.</p></div>', unsafe_allow_html=True)
st.info("👋 Welcome to Zentra! Upload your notes and let AI transform them into study material.")

# ---------- UPLOAD ----------
st.markdown("### 📁 Upload your notes")
col_up, col_mode = st.columns([3,2])
with col_up:
    uploaded = st.file_uploader("Drag and drop here", type=["pdf","docx","txt"], help="Supports PDF, DOCX, TXT.")
    pasted = st.text_area("Or paste notes…", height=120)
with col_mode:
    st.write("**Analysis mode**")
    mode = st.radio("", ["Text only","Include images (Vision)"], horizontal=True, label_visibility="collapsed")

# ---------- STUDY TOOLS ----------
st.markdown("### ✨ Study Tools")
c1,c2,c3,c4,c5 = st.columns([1,1,1,1,1])
go_summary = c1.button("📄 Summaries")
go_cards = c2.button("🧠 Flashcards")
go_quiz = c3.button("🎯 Quizzes")
go_mock = c4.button("📝 Mock Exams")
ask_click = c5.button("💬 Ask Zentra")

# ---------- ASK ZENTRA POPUP ----------
def render_chat():
    st.markdown('<div class="ask-panel">', unsafe_allow_html=True)
    st.markdown('<div class="ask-header"><b>💬 Ask Zentra</b></div>', unsafe_allow_html=True)
    st.markdown('<div class="ask-body">', unsafe_allow_html=True)
    if not st.session_state.chat:
        st.caption("Try: *Explain this formula*, *Make a study plan*, *Test me on chapter X*.")
    for role, msg in st.session_state.chat:
        st.markdown(f"**{'You' if role=='user' else 'Zentra'}:** {msg}")
    st.markdown('</div>', unsafe_allow_html=True)

    q = st.text_input("Type here...", key="chat_input", label_visibility="collapsed")
    col1, col2, col3 = st.columns([1,1,1])
    if col1.button("Send") or (q and st.session_state.get("enter_pressed")):
        if q.strip():
            st.session_state.chat.append(("user", q.strip()))
            ans = ask_openai(f"Notes:\n{st.session_state.notes_text}\n\nUser: {q.strip()}")
            st.session_state.chat.append(("assistant", ans))
            st.session_state.chat_input = ""
            st.rerun()
    if col2.button("Clear"):
        st.session_state.chat.clear(); st.rerun()
    if col3.button("Close"):
        st.session_state.show_chat = False; st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

if ask_click: st.session_state.show_chat = True
if st.session_state.show_chat: render_chat()

# ---------- HANDLERS ----------
def handle_summary(text):
    st.subheader("✅ Summary")
    out = ask_openai(f"Summarize into exam-style bullet points:\n\n{text}")
    st.markdown(out)

def handle_flashcards(text):
    st.subheader("🧠 Flashcards")
    out = ask_openai(f"Make Q/A flashcards:\n\n{text}")
    st.markdown(out)

def handle_quiz(text):
    st.subheader("🎯 Quiz")
    out = ask_openai(f"Create 8 MCQs with explanations from:\n\n{text}")
    st.session_state.history_quiz.append(st.session_state.last_title)
    st.markdown(out)

def handle_mock(text):
    st.subheader("📝 Mock Exam")
    diff = st.radio("Select difficulty", ["Easy","Standard","Hard"], horizontal=True)
    if st.button("Generate Mock"):
        out = ask_openai(f"Create a {diff} mock exam (MCQs, short, long, fill-in) with marking guide:\n\n{text}")
        st.session_state.history_mock.append(st.session_state.last_title)
        st.markdown(out)

# ---------- EXECUTION ----------
if go_summary or go_cards or go_quiz or go_mock:
    text = ensure_notes(pasted, uploaded)
    if go_summary: handle_summary(text)
    if go_cards: handle_flashcards(text)
    if go_quiz: handle_quiz(text)
    if go_mock: handle_mock(text)
