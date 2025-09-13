# app.py — Zentra Final (Tools Fixed)

import os, io, tempfile
import streamlit as st
from openai import OpenAI
from typing import List, Tuple

# ---------- PAGE CONFIG ----------
st.set_page_config(
    page_title="Zentra — Your Study Buddy",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------- GLOBAL STYLES ----------
st.markdown("""
<style>
a[class*="viewerBadge"], div[class*="viewerBadge"], #ViewerBadgeContainer{display:none!important;}
footer{visibility:hidden;height:0}
.block-container{padding-top:0.75rem; padding-bottom:3rem; max-width:1200px;}
.hero{background:linear-gradient(90deg,#6a11cb 0%,#2575fc 100%);
  padding:22px; border-radius:16px; color:#fff; margin-bottom:10px; text-align:center;}
.hero h1{margin:0;font-size:34px;font-weight:800;}
.hero p{margin:6px 0 0;opacity:.92}
.section-title{font-weight:800;font-size:22px;margin:10px 0 14px;}
.tool-row .stButton>button{
  width:100%; border-radius:12px; border:1px solid #2b2f3a;
  padding:10px; background:#10141e; color:#e8ecf7; font-weight:700;
}
.tool-row .stButton>button:hover{background:#141a27; border-color:#3a4252;}
.results-box{
  border:1px solid #232b3a; border-radius:14px; background:#0e1117;
  padding:15px; min-height:200px; margin-top:14px;
}
</style>
""", unsafe_allow_html=True)

# ---------- STATE ----------
if "notes_text" not in st.session_state: st.session_state.notes_text = ""
if "last_title" not in st.session_state: st.session_state.last_title = "Untitled notes"
if "results" not in st.session_state: st.session_state.results = ""
if "flashcards" not in st.session_state: st.session_state.flashcards = []
if "quiz_data" not in st.session_state: st.session_state.quiz_data = []
if "mock_data" not in st.session_state: st.session_state.mock_data = []

# ---------- OPENAI ----------
def _client() -> OpenAI:
    key = st.secrets.get("OPENAI_API_KEY")
    if not key:
        st.error("Missing OPENAI_API_KEY in Streamlit Secrets."); st.stop()
    os.environ["OPENAI_API_KEY"] = key
    return OpenAI()

MODEL = "gpt-4o-mini"

def ask_llm(prompt: str, system="You are Zentra, a supportive AI study buddy. Be concise, exam-focused."):
    r=_client().chat.completions.create(
        model=MODEL,
        messages=[{"role":"system","content":system},{"role":"user","content":prompt}],
        temperature=0.4
    )
    return r.choices[0].message.content.strip()

# ---------- FILE HANDLING ----------
def read_file(uploaded) -> str:
    if not uploaded: return ""
    name=uploaded.name.lower(); data=uploaded.read()
    text=""
    if name.endswith(".txt"): text=data.decode("utf-8","ignore")
    elif name.endswith(".pdf"):
        try:
            from pypdf import PdfReader
            reader=PdfReader(io.BytesIO(data))
            text="\n".join([(p.extract_text() or "") for p in reader.pages])
        except: text=""
    elif name.endswith(".docx"):
        try:
            import docx2txt
            with tempfile.NamedTemporaryFile(delete=False,suffix=".docx") as tmp:
                tmp.write(data); tmp.flush()
                text=docx2txt.process(tmp.name)
        except: text=""
    else:
        try: text=data.decode("utf-8","ignore")
        except: text=""
    return (text or "").strip()

# ---------- HERO ----------
st.markdown('<div class="hero"><h1>⚡ Zentra — Your Study Buddy</h1><p>Smarter notes → Better recall → Higher scores.</p></div>', unsafe_allow_html=True)

# ---------- MAIN ----------
uploaded=st.file_uploader("Upload file",type=["pdf","docx","txt"],label_visibility="collapsed")
pasted=st.text_area("Paste your notes here…",height=150)

if uploaded:
    st.session_state.notes_text = read_file(uploaded)
    st.session_state.last_title = uploaded.name
elif pasted.strip():
    st.session_state.notes_text = pasted.strip()

st.markdown('<div class="section-title">✨ Study Tools</div>', unsafe_allow_html=True)
st.markdown('<div class="tool-row">',unsafe_allow_html=True)
c1,c2,c3,c4,c5=st.columns(5)
go_summary=c1.button("📄 Summaries")
go_cards=c2.button("🧠 Flashcards")
go_quiz=c3.button("🎯 Quizzes")
go_mock=c4.button("📝 Mock Exams")
go_chat=c5.button("💬 Ask Zentra")
st.markdown('</div>',unsafe_allow_html=True)

# ---------- RESULTS BOX ----------
results_area = st.container()
with results_area:
    st.markdown('<div class="results-box">', unsafe_allow_html=True)
    if st.session_state.results:
        st.markdown(st.session_state.results, unsafe_allow_html=True)
    else:
        st.caption("Results will appear here.")
    st.markdown('</div>', unsafe_allow_html=True)

# ---------- TOOLS ----------
if go_summary and st.session_state.notes_text:
    with st.spinner("Generating summary..."):
        out=ask_llm(f"Summarize these notes into exam-ready bullet points:\n\n{st.session_state.notes_text}")
    st.session_state.results=f"### ✅ Summary\n\n{out}"

if go_cards and st.session_state.notes_text:
    with st.spinner("Generating flashcards..."):
        raw=ask_llm(f"Create 5 flashcards (Q then A). Use clear formatting.\n\n{st.session_state.notes_text}")
    cards = [c.strip() for c in raw.split("\n") if c.strip()]
    st.session_state.flashcards = cards
    st.session_state.results="### 🧠 Flashcards\n\n"
    for i,c in enumerate(cards,1):
        st.session_state.results += f"**Q{i}:** {c}\n\n<details><summary>Reveal Answer</summary>Answer here</details>\n\n"

if go_quiz and st.session_state.notes_text:
    with st.spinner("Generating quiz..."):
        out=ask_llm(f"Create 5 MCQs (A–D) with correct answer indicated. Include explanations.\n\n{st.session_state.notes_text}")
    st.session_state.results=f"### 🎯 Quiz\n\n{out}"

if go_mock and st.session_state.notes_text:
    diff=st.radio("Select difficulty",["Easy","Standard","Hard"],horizontal=True)
    if st.button("Start Mock"):
        with st.spinner("Preparing mock exam..."):
            mock=ask_llm(f"Create a {diff} mock exam with: 5 MCQs, 2 short Qs, 1 long Q, 2 fill-in Qs. Provide clear spaces for answers. Grade it out of a multiple of 10 (≤100).\n\n{st.session_state.notes_text}")
        st.session_state.results=f"### 📝 Mock Exam ({diff})\n\n{mock}"
