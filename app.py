# app.py — Zentra (final polished version)

import io, os, base64
from typing import List, Tuple
import streamlit as st
from openai import OpenAI

# ------------------ PAGE CONFIG ------------------
st.set_page_config(page_title="Zentra — AI Study Buddy", page_icon="⚡", layout="wide")

# ------------------ CUSTOM CSS -------------------
st.markdown("""
<style>
/* Hide Streamlit UI junk */
[data-testid="stToolbar"], [data-testid="stDecoration"], header {visibility: hidden; height: 0;}
footer {visibility: hidden;}
a[class*="viewerBadge"], div[class*="viewerBadge"], #ViewerBadgeContainer {display:none !important;}

/* Page container */
.block-container {padding-top: 1rem; max-width: 1200px;}

/* Hero */
.hero {background: linear-gradient(90deg,#6a11cb 0%,#2575fc 100%); 
       padding: 24px; border-radius: 16px; color: #fff; margin-bottom: 1rem;}
.hero h1 {font-size: 38px; margin: 0;}
.hero p {opacity: .92; margin: 0; font-size: 18px;}

/* Buttons */
.tool-btn {padding:10px 16px; border-radius:12px; background:#111; color:#fff; 
           border:1px solid #333; font-weight:500;}
.tool-btn:hover {background:#1b1b1b; border-color:#555;}

/* Floating chat panel */
.ask-panel {position: fixed; right: 24px; top: 90px; width: 380px; height: 70vh; 
            background:#0e1117; border:1px solid #333; border-radius:14px;
            z-index: 9999; box-shadow: 0 10px 30px rgba(0,0,0,.45); 
            display:flex; flex-direction:column;}
.ask-header {padding:10px 14px; border-bottom:1px solid #222; 
             display:flex; justify-content:space-between; align-items:center;}
.ask-body {flex:1; padding:12px; overflow-y:auto; font-size:15px;}
.ask-input input {width:100%; padding:8px; border-radius:8px; border:1px solid #333; background:#111; color:#fff;}
</style>
""", unsafe_allow_html=True)

# ------------------ STATE ------------------------
if "show_chat" not in st.session_state: st.session_state.show_chat = False
if "chat" not in st.session_state: st.session_state.chat = []
if "history_quiz" not in st.session_state: st.session_state.history_quiz = []
if "history_mock" not in st.session_state: st.session_state.history_mock = []
if "notes_text" not in st.session_state: st.session_state.notes_text = ""

# ------------------ OPENAI -----------------------
def get_client():
    key = st.secrets.get("OPENAI_API_KEY", None)
    if not key:
        st.error("Missing OPENAI_API_KEY in Streamlit secrets")
        st.stop()
    os.environ["OPENAI_API_KEY"] = key
    return OpenAI()

MODEL = "gpt-4o-mini"

def ask_openai(prompt: str):
    client = get_client()
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role":"system","content":"You are Zentra, a professional AI study buddy. Be concise and clear."},
                  {"role":"user","content":prompt}],
        temperature=0.4,
    )
    return resp.choices[0].message.content.strip()

# ------------------ FILE READING -----------------
def read_file(uploaded) -> str:
    if not uploaded: return ""
    name = uploaded.name.lower()
    data = uploaded.read()
    if name.endswith(".txt"):
        return data.decode("utf-8", errors="ignore")
    elif name.endswith(".pdf"):
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        return "\n".join([p.extract_text() or "" for p in reader.pages])
    elif name.endswith(".docx"):
        import docx2txt
        return docx2txt.process(io.BytesIO(data))
    else:
        return ""

# ------------------ SIDEBAR ----------------------
with st.sidebar:
    st.markdown("### ℹ️ About Zentra")
    st.write("Zentra accelerates learning with summaries, flashcards, quizzes, and mock exams — plus a smart tutor.")
    st.markdown("### 🛠️ What each tool does")
    st.markdown("""
- **Summaries** → exam-ready bullet points.  
- **Flashcards** → spaced-repetition Q/A.  
- **Quizzes** → MCQs with explanations (AI chooses number).  
- **Mock Exams** → multi-section exam with marking guide.  
- **Ask Zentra** → AI tutor for clarifications and study plans.  
    """)
    st.markdown("### 🧪 Mock exam evaluation")
    st.write("Scales with notes length. Includes MCQs, short, long, fill-in. Marked with rubric. Difficulty: Easy / Standard / Hard.")
    st.markdown("### 🗂️ History")
    st.caption("Recent quizzes:")
    st.write(st.session_state.history_quiz[-5:] or "None yet.")
    st.caption("Recent mock exams:")
    st.write(st.session_state.history_mock[-5:] or "None yet.")
    st.markdown("---")
    st.caption("⚠️ Zentra is an AI assistant. Verify content before exams.")

# ------------------ HERO -------------------------
st.markdown("""
<div class="hero">
  <h1>⚡ Zentra — AI Study Buddy</h1>
  <p>Smarter notes → Better recall → Higher scores.</p>
</div>
""", unsafe_allow_html=True)

st.info("👋 Welcome to Zentra! Upload your notes and let AI transform them into study material.")

# ------------------ UPLOAD -----------------------
st.markdown("### 📁 Upload your notes")
col1, col2 = st.columns([3,2])
with col1:
    uploaded = st.file_uploader("Drag and drop files", type=["pdf","docx","txt"], label_visibility="collapsed")
    pasted = st.text_area("Or paste your notes here…", height=120, label_visibility="collapsed")
with col2:
    st.write("**Analysis mode**")
    mode = st.radio("", ["Text only","Include images (Vision)"], horizontal=True, label_visibility="collapsed")

# ------------------ STUDY TOOLS -----------------
st.markdown("### ✨ Study Tools")
c1,c2,c3,c4,c5 = st.columns(5)
go_summary = c1.button("📄 Summaries", help="Turn your notes into bullet-point exam notes.")
go_cards   = c2.button("🧠 Flashcards", help="Q/A pairs for active recall.")
go_quiz    = c3.button("🎯 Quizzes", help="MCQs with explanations (AI chooses count).")
go_mock    = c4.button("📝 Mock Exams", help="Multi-section exam with marking guide.")
ask_click  = c5.button("💬 Ask Zentra", help="Ask about any subject — concepts, plans, clarifications.")

if ask_click: st.session_state.show_chat = True

# ------------------ CHATBOX ----------------------
if st.session_state.show_chat:
    st.markdown('<div class="ask-panel">', unsafe_allow_html=True)
    st.markdown('<div class="ask-header"><b>💬 Ask Zentra</b><span style="cursor:pointer;" onclick="window.parent.postMessage({type:\'closeChat\'}, \'*\')">✖</span></div>', unsafe_allow_html=True)
    st.markdown('<div class="ask-body">', unsafe_allow_html=True)
    for role, msg in st.session_state.chat:
        st.markdown(f"**{'You' if role=='user' else 'Zentra'}:** {msg}")
    st.markdown('</div>', unsafe_allow_html=True)
    q = st.text_input("Type your question…", key="ask_input", label_visibility="collapsed")
    if q:
        st.session_state.chat.append(("user", q))
        ans = ask_openai(q)
        st.session_state.chat.append(("assistant", ans))
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# ------------------ HANDLERS ---------------------
text = pasted.strip()
if uploaded:
    text += "\n" + read_file(uploaded)
st.session_state.notes_text = text.strip()

if go_summary and text:
    out = ask_openai("Summarize into exam-ready bullet points:\n" + text)
    st.subheader("✅ Summary")
    st.markdown(out)

if go_cards and text:
    out = ask_openai("Make flashcards in Q/A format:\n" + text)
    st.subheader("🧠 Flashcards")
    st.markdown(out)

if go_quiz and text:
    out = ask_openai("Create adaptive MCQs with answers and explanations:\n" + text)
    st.session_state.history_quiz.append(uploaded.name if uploaded else "Pasted notes")
    st.subheader("🎯 Quiz")
    st.markdown(out)

if go_mock and text:
    diff = st.radio("Select difficulty", ["Easy","Standard","Hard"], horizontal=True)
    if st.button("Generate Mock"):
        out = ask_openai(f"Create a {diff} mock exam with MCQ, short, long, fill-in + marking scheme:\n{text}")
        st.session_state.history_mock.append(uploaded.name if uploaded else "Pasted notes")
        st.subheader("📝 Mock Exam")
        st.markdown(out)
