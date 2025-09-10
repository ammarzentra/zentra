# app.py — Zentra Stable International Build

import os, io, base64, tempfile
from typing import List, Tuple
import streamlit as st
from openai import OpenAI

# ---------- PAGE CONFIG ----------
st.set_page_config(
    page_title="Zentra — AI Study Buddy",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------- CSS ----------
st.markdown("""
<style>
a[class*="viewerBadge"], div[class*="viewerBadge"], #ViewerBadgeContainer{display:none!important;}
footer{visibility:hidden;height:0}
.block-container{padding-top:1rem;padding-bottom:3rem;max-width:1200px;}
.hero{background:linear-gradient(90deg,#6a11cb 0%,#2575fc 100%);padding:22px;border-radius:16px;color:#fff;margin-bottom:10px;}
.hero h1{margin:0;font-size:34px}
.hero p{margin:6px 0 0;opacity:.92}
.ask-panel{position:fixed;right:26px;top:100px;width:min(420px,90vw);height:70vh;background:#0e1117;border:1px solid #333;
           border-radius:12px;box-shadow:0 10px 30px rgba(0,0,0,.45);padding:10px;z-index:9999;}
.ask-header{display:flex;justify-content:space-between;align-items:center;padding:6px 10px;border-bottom:1px solid #222;}
.ask-body{padding:8px;height:calc(70vh - 130px);overflow-y:auto;}
</style>
""", unsafe_allow_html=True)

# ---------- STATE ----------
if "chat_open" not in st.session_state: st.session_state.chat_open = False
if "messages" not in st.session_state: st.session_state.messages = []
if "history_quiz" not in st.session_state: st.session_state.history_quiz = []
if "history_mock" not in st.session_state: st.session_state.history_mock = []
if "notes_text" not in st.session_state: st.session_state.notes_text = ""
if "last_title" not in st.session_state: st.session_state.last_title = "Untitled notes"
if "pending_mock" not in st.session_state: st.session_state.pending_mock = False

# ---------- OPENAI ----------
def _client() -> OpenAI:
    key = st.secrets.get("OPENAI_API_KEY")
    if not key:
        st.error("Missing OPENAI_API_KEY in Streamlit Secrets."); st.stop()
    os.environ["OPENAI_API_KEY"] = key
    return OpenAI()

MODEL = "gpt-4o-mini"

def ask_llm(prompt: str, system="You are Zentra, a precise, supportive study buddy. Be concise and clear."):
    r = _client().chat.completions.create(
        model=MODEL,
        messages=[{"role":"system","content":system},{"role":"user","content":prompt}],
        temperature=0.4,
    )
    return r.choices[0].message.content.strip()

# ---------- FILE PARSE ----------
def read_file(uploaded) -> Tuple[str, List[Tuple[str, bytes]]]:
    if not uploaded: return "", []
    name = uploaded.name.lower(); data = uploaded.read()
    text, images = "", []
    if name.endswith(".txt"):
        text = data.decode("utf-8","ignore")
    elif name.endswith(".pdf"):
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data))
            text = "\n".join([(p.extract_text() or "") for p in reader.pages])
        except Exception: text = ""
    elif name.endswith(".docx"):
        try:
            import docx2txt
            with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
                tmp.write(data); tmp.flush()
                text = docx2txt.process(tmp.name)
        except Exception: text = ""
    else:
        text = data.decode("utf-8","ignore")
    return (text or "").strip(), images

def ensure_notes(pasted, uploaded):
    txt = (pasted or "").strip()
    if uploaded:
        t, _ = read_file(uploaded)
        if t: txt = (txt + "\n" + t).strip() if txt else t
        st.session_state.last_title = uploaded.name
    if len(txt) < 5:
        st.warning("Your notes look empty. Paste text or upload a readable PDF/DOCX.")
        st.stop()
    st.session_state.notes_text = txt
    return txt

def adaptive_quiz_count(txt: str) -> int:
    return max(3, min(20, len(txt.split()) // 180))

# ---------- SIDEBAR ----------
with st.sidebar:
    st.markdown("## 📊 Toolbox")
    st.write("**How Zentra Works**: Turns notes into smart tools for learning. Smarter notes → better recall → higher scores.")
    st.markdown("### 🎯 What Zentra Offers")
    st.markdown("- **Summaries** → exam-ready bullets\n- **Flashcards** → active recall Q/A\n- **Quizzes** → MCQs + explanations\n- **Mock Exams** → graded, multi-section with evaluation\n- **Ask Zentra** → personal AI tutor")
    st.markdown("### 🧪 Mock Evaluation")
    st.write("Includes MCQs, short, long, fill-in. Difficulty: *Easy / Standard / Hard*. Zentra grades and gives feedback.")
    st.markdown("### 📜 History")
    st.caption("Quizzes:"); st.write(st.session_state.history_quiz or "—")
    st.caption("Mocks:");   st.write(st.session_state.history_mock or "—")
    st.markdown("---")
    st.caption("Disclaimer: Always verify AI-generated content before exams.")

# ---------- HERO ----------
st.markdown('<div class="hero"><h1>⚡ Zentra — AI Study Buddy</h1><p>Smarter notes → Better recall → Higher scores.</p></div>', unsafe_allow_html=True)
st.info("👋 Welcome to Zentra! Upload your notes and let AI transform them into study material.")

# ---------- MAIN ----------
uploaded = st.file_uploader("📁 Upload notes", type=["pdf","docx","txt"])
pasted = st.text_area("Or paste your notes here…", height=150)
mode = st.radio("Analysis mode", ["Text only","Include images (Vision)"], horizontal=True)
include_images = (mode == "Include images (Vision)")

st.markdown("### ✨ Study Tools")
c1,c2,c3,c4,c5 = st.columns(5)
go_summary = c1.button("📄 Summaries")
go_cards   = c2.button("🧠 Flashcards")
go_quiz    = c3.button("🎯 Quizzes")
go_mock    = c4.button("📝 Mock Exams")
open_chat  = c5.button("💬 Ask Zentra")

if open_chat: st.session_state.chat_open = True

# ---------- ASK ZENTRA ----------
if st.session_state.chat_open:
    st.markdown('<div class="ask-panel">', unsafe_allow_html=True)
    st.markdown('<div class="ask-header"><b>💬 Ask Zentra</b></div>', unsafe_allow_html=True)
    if not st.session_state.messages:
        st.caption("Try: *Explain this formula*, *Make a 7-day plan*, *Test me on topic X*.")
    for m in st.session_state.messages:
        st.markdown(f"**{'You' if m['role']=='user' else 'Zentra'}:** {m['content']}")
    q = st.text_input("Type here...", key="chat_input", label_visibility="collapsed")
    col1,col2,col3 = st.columns(3)
    if col1.button("Send") or (q and st.session_state.get("enter_pressed")):
        if q.strip():
            st.session_state.messages.append({"role":"user","content":q.strip()})
            reply = ask_llm(f"NOTES:\n{st.session_state.notes_text}\n\nUSER: {q}")
            st.session_state.messages.append({"role":"assistant","content":reply})
            st.session_state.chat_input = ""
            st.rerun()
    if col2.button("Clear"):
        st.session_state.messages.clear(); st.rerun()
    if col3.button("Close"):
        st.session_state.chat_open = False; st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# ---------- HANDLERS ----------
def do_summary(txt):
    st.subheader("✅ Summary")
    out = ask_llm(f"Summarize into exam-style bullets:\n\n{txt}")
    st.markdown(out)

def do_cards(txt):
    st.subheader("🧠 Flashcards")
    out = ask_llm(f"Make Q/A flashcards:\n\n{txt}")
    st.markdown(out)

def do_quiz(txt):
    st.subheader("🎯 Quiz")
    n = adaptive_quiz_count(txt)
    out = ask_llm(f"Create {n} MCQs with answers and explanations:\n\n{txt}")
    st.session_state.history_quiz.append(st.session_state.last_title)
    st.markdown(out)

def do_mock(txt):
    st.subheader("📝 Mock Exam")
    diff = st.radio("Difficulty", ["Easy","Standard","Hard"], horizontal=True)
    if st.button("Start Mock"):
        # Generate mock with placeholders for answers
        exam = ask_llm(f"Create a {diff} mock exam with MCQs, short, long, fill-in. Provide marking scheme:\n\n{txt}")
        st.session_state.history_mock.append(st.session_state.last_title)
        st.markdown(exam)
        st.text_area("✍️ Short Answer", key="mock_short")
        st.text_area("📝 Long Answer", key="mock_long")
        if st.button("Submit Mock"):
            ans = ask_llm(
                f"Grade this mock exam based on rubric:\n\n{exam}\n\n"
                f"User Short Answer:\n{st.session_state.mock_short}\n\n"
                f"User Long Answer:\n{st.session_state.mock_long}"
            )
            st.subheader("📊 Zentra’s Evaluation")
            st.markdown(ans)

if go_summary or go_cards or go_quiz or go_mock:
    text = ensure_notes(pasted, uploaded)
    if go_summary: do_summary(text)
    if go_cards: do_cards(text)
    if go_quiz: do_quiz(text)
    if go_mock: do_mock(text)
