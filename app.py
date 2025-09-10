# app.py — Zentra (Final Polished Version)

import io
import os
import base64
import streamlit as st
from openai import OpenAI

# ---------- PAGE SETUP ----------
st.set_page_config(page_title="Zentra — AI Study Buddy", page_icon="⚡", layout="wide")

# Hide Streamlit chrome (toolbar, footer, watermark)
st.markdown("""
<style>
[data-testid="stToolbar"], [data-testid="stDecoration"], header {visibility: hidden; height:0;}
footer {visibility:hidden;}
a[class*="viewerBadge"], div[class*="viewerBadge"], #ViewerBadgeContainer {display:none !important;}

.block-container {padding-top:1rem; max-width:1200px;}
.hero {background:linear-gradient(90deg,#6a11cb 0%,#2575fc 100%); padding:22px; border-radius:14px; color:#fff;}
.hero h1 {margin:0; font-size:34px;}
.hero p {margin:0; opacity:.9;}

.tool-btn {display:inline-block; padding:10px 16px; margin:10px 10px 0 0;
           border-radius:12px; background:#111; color:#fff; border:1px solid #333;}
.tool-btn:hover {background:#1b1b1b;}

#ask-bubble {position:fixed; right:26px; top:26px; z-index:999;}
.ask-panel {position:fixed; right:26px; top:86px; width:min(420px,92vw); height:70vh;
            background:#0e1117; border:1px solid #333; border-radius:14px; 
            box-shadow:0 10px 30px rgba(0,0,0,.45); z-index:9999;}
.ask-header {display:flex; justify-content:space-between; align-items:center; 
             padding:10px 14px; border-bottom:1px solid #222;}
.ask-body {padding:12px; height:calc(70vh - 120px); overflow-y:auto;}
.ask-input {position:absolute; bottom:12px; left:12px; right:12px;}
</style>
""", unsafe_allow_html=True)

# ---------- STATE ----------
if "history_quiz" not in st.session_state: st.session_state.history_quiz = []
if "history_mock" not in st.session_state: st.session_state.history_mock = []
if "show_chat" not in st.session_state: st.session_state.show_chat = False
if "chat" not in st.session_state: st.session_state.chat = []
if "notes_text" not in st.session_state: st.session_state.notes_text = ""

# ---------- OPENAI CLIENT ----------
def get_client() -> OpenAI:
    key = st.secrets.get("OPENAI_API_KEY")
    if not key: st.stop()
    os.environ["OPENAI_API_KEY"] = key
    return OpenAI()

MODEL_TEXT = "gpt-4o-mini"

def ask_openai(prompt: str, system="You are Zentra, an academic study tutor."):
    client = get_client()
    resp = client.chat.completions.create(
        model=MODEL_TEXT,
        messages=[{"role":"system","content":system},{"role":"user","content":prompt}],
        temperature=0.4,
    )
    return resp.choices[0].message.content.strip()

# ---------- SIDEBAR ----------
with st.sidebar:
    st.markdown("## 📘 How Zentra Works")
    st.write("Zentra transforms notes into smarter study tools — summaries, flashcards, quizzes, and mock exams with grading. Consistency + feedback = progress.")

    st.markdown("## 🎯 What Zentra Offers")
    st.markdown("- **Summaries** → clear exam-ready notes\n"
                "- **Flashcards** → spaced repetition Q/A\n"
                "- **Quizzes** → adaptive MCQs w/ explanations\n"
                "- **Mock Exams** → full exam + grading rubric\n"
                "- **Ask Zentra** → your 24/7 tutor")

    st.markdown("## 📂 History")
    st.caption("Recent Quizzes")
    if st.session_state.history_quiz:
        for i, q in enumerate(st.session_state.history_quiz[-5:][::-1], 1):
            st.write(f"{i}. {q}")
    else:
        st.write("No quizzes yet.")

    st.caption("Recent Mock Exams")
    if st.session_state.history_mock:
        for i, m in enumerate(st.session_state.history_mock[-5:][::-1], 1):
            st.write(f"{i}. {m}")
    else:
        st.write("No mocks yet.")

    st.markdown("---")
    st.caption("Disclaimer: Zentra is an AI assistant. Always double-check before exams.")

# ---------- HERO ----------
st.markdown("""
<div class="hero">
  <h1>⚡ Zentra — AI Study Buddy</h1>
  <p>Smarter notes → Better recall → Higher scores.</p>
</div>
""", unsafe_allow_html=True)

st.info("👋 Welcome to Zentra! Upload your notes and let AI generate study tools.", icon="📘")

# ---------- UPLOAD ----------
uploaded = st.file_uploader("Upload Notes (PDF/DOCX/TXT)", type=["pdf","docx","txt"])
pasted = st.text_area("Or paste your notes here…", height=120, label_visibility="collapsed")

def ensure_notes():
    txt = pasted.strip()
    if uploaded:
        txt = (txt + "\n" + uploaded.read().decode("utf-8","ignore")).strip()
    if not txt:
        st.warning("Upload or paste notes first.")
        st.stop()
    st.session_state.notes_text = txt
    return txt

# ---------- STUDY TOOLS ----------
st.markdown("### ✨ Study Tools")
c1,c2,c3,c4,c5 = st.columns(5)

go_summary = c1.button("📄 Summaries")
go_cards   = c2.button("🧠 Flashcards")
go_quiz    = c3.button("🎯 Quizzes")
go_mock    = c4.button("📝 Mock Exams")
ask_click  = c5.button("💬 Ask Zentra")

if ask_click: st.session_state.show_chat = True

# ---------- ASK ZENTRA ----------
def render_chat():
    st.markdown('<div class="ask-panel">', unsafe_allow_html=True)
    st.markdown('<div class="ask-header"><b>💬 Ask Zentra</b></div>', unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="ask-body">', unsafe_allow_html=True)
        for role, msg in st.session_state.chat:
            st.markdown(f"**{'You' if role=='user' else 'Zentra'}:** {msg}")
        st.markdown('</div>', unsafe_allow_html=True)

    q = st.text_input("Type here...", key="chat_input", on_change=lambda: None)
    col1, col2, col3 = st.columns([1,1,1])
    if col1.button("Send") or (q and st.session_state.get("enter_pressed")):
        st.session_state.chat.append(("user", q))
        ans = ask_openai(f"User asked: {q}\nNotes:\n{st.session_state.notes_text}")
        st.session_state.chat.append(("assistant", ans))
        st.session_state.chat_input = ""
        st.rerun()
    if col2.button("Clear"): st.session_state.chat.clear(); st.rerun()
    if col3.button("Close"): st.session_state.show_chat = False; st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

if st.session_state.show_chat: render_chat()

# ---------- TOOL HANDLERS ----------
if go_summary:
    text = ensure_notes()
    st.subheader("✅ Summary")
    st.markdown(ask_openai(f"Summarize clearly into exam bullets:\n{text}"))

if go_cards:
    text = ensure_notes()
    st.subheader("🧠 Flashcards")
    st.markdown(ask_openai(f"Make flashcards Q/A covering all content:\n{text}"))

if go_quiz:
    text = ensure_notes()
    st.subheader("🎯 Quiz")
    out = ask_openai(f"Make adaptive MCQs with answers & explanations:\n{text}")
    st.markdown(out)
    st.session_state.history_quiz.append("Quiz Attempt")

if go_mock:
    text = ensure_notes()
    st.subheader("📝 Mock Exam")
    diff = st.radio("Select difficulty", ["Easy","Standard","Hard"], horizontal=True)
    if st.button("Start Mock"):
        st.write("Answer the mock below then submit for grading.")
        q_short = st.text_area("✍️ Short Answer")
        q_long  = st.text_area("📝 Long Answer (Essay)")
        if st.button("Submit Mock"):
            result = ask_openai(f"Grade this mock (difficulty={diff}). Notes:\n{text}\n\nShort:{q_short}\nLong:{q_long}")
            st.success("📊 Zentra Evaluation")
            st.markdown(result)
            st.session_state.history_mock.append(f"Mock ({diff})")
