# app.py  — Zentra (polished)

import io
import os
import time
import base64
from typing import List, Tuple

import streamlit as st
from openai import OpenAI

# ---------- SETUP ----------
st.set_page_config(page_title="Zentra — AI Study Buddy", page_icon="⚡", layout="wide")

# Hide Streamlit chrome (toolbar, footer, watermark)
st.markdown("""
<style>
/* hide top toolbar + hamburger */
[data-testid="stToolbar"], [data-testid="stDecoration"], header {visibility: hidden; height: 0 !important;}
/* hide footer */
footer {visibility: hidden;}
/* hide viewer watermark/crown on mobile */
a[class*="viewerBadge"], div[class*="viewerBadge"], #ViewerBadgeContainer {display:none !important;}
/* tidy containers */
.block-container {padding-top: 1.2rem; padding-bottom: 4rem; max-width: 1200px;}
/* gradient hero */
.hero {background: linear-gradient(90deg,#6a11cb 0%,#2575fc 100%); padding: 24px; border-radius: 18px; color: #fff; }
.hero h1 {font-size: 36px; margin: 0 0 6px 0;}
.hero p {opacity: .92; margin: 0;}
/* tool buttons */
.tool-btn {display:inline-block; padding:10px 16px; border-radius:12px; background:#111; color:#fff; margin:10px 10px 0 0; border:1px solid #333;}
.tool-btn:hover {background:#1b1b1b; border-color:#444;}
/* floating Ask panel */
#ask-bubble {position: fixed; right: 26px; top: 26px; z-index: 999;}
.ask-panel {position: fixed; right: 26px; top: 86px; width: min(420px, 92vw); height: 70vh; background:#0e1117; border:1px solid #333; border-radius:14px; z-index: 9999; box-shadow: 0 10px 30px rgba(0,0,0,.45); overflow: hidden;}
.ask-header {display:flex; justify-content:space-between; align-items:center; padding:12px 14px; border-bottom:1px solid #222;}
.ask-body {padding:12px; height: calc(70vh - 130px); overflow:auto;}
.ask-input {position:absolute; bottom:12px; left:12px; right:12px;}
/* section titles */
.section-title {font-size: 24px; font-weight: 700; margin: 8px 0 8px;}
/* tidy radio */
[data-testid="stRadio"] > label {margin-bottom: 6px;}
/* small helper text */
.helper {font-size:.88rem; opacity:.8; margin-top: -6px;}
</style>
""", unsafe_allow_html=True)

# ---------- STATE ----------
if "history_quiz" not in st.session_state: st.session_state.history_quiz = []
if "history_mock" not in st.session_state: st.session_state.history_mock = []
if "show_chat" not in st.session_state: st.session_state.show_chat = False
if "chat" not in st.session_state: st.session_state.chat = []  # list of (role, text)
if "notes_text" not in st.session_state: st.session_state.notes_text = ""
if "last_title" not in st.session_state: st.session_state.last_title = "Untitled notes"

# ---------- OPENAI CLIENT ----------
def get_client() -> OpenAI:
    key = st.secrets.get("OPENAI_API_KEY", None)
    if not key:
        st.error("Missing OPENAI_API_KEY in Streamlit Secrets.")
        st.stop()
    os.environ["OPENAI_API_KEY"] = key
    return OpenAI()

MODEL_TEXT = "gpt-4o-mini"     # cost-efficient
MODEL_VISION = "gpt-4o-mini"   # vision for images (beta toggle)

# ---------- HELPERS ----------
def read_file(uploaded) -> Tuple[str, List[Tuple[str, bytes]]]:
    """
    Returns: (plain_text, images[]) where images = [(filename, bytes)]
    """
    if not uploaded:
        return "", []
    name = uploaded.name.lower()
    data = uploaded.read()
    text = ""
    images = []

    if name.endswith(".txt"):
        text = data.decode("utf-8", errors="ignore")
    elif name.endswith(".pdf"):
        # lightweight text extraction using pypdf
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data))
            pages = []
            for p in reader.pages:
                pages.append(p.extract_text() or "")
            text = "\n".join(pages)
        except Exception:
            text = ""
        # keep images for optional vision (png/jpg)
        # (simple pass-through; we won’t rasterize pages here)
    elif name.endswith(".docx"):
        try:
            import docx2txt
            with io.BytesIO(data) as f:
                text = docx2txt.process(f)
        except Exception:
            text = ""
    elif any(name.endswith(ext) for ext in [".png", ".jpg", ".jpeg"]):
        images.append((uploaded.name, data))
    else:
        text = data.decode("utf-8", errors="ignore")

    return text.strip(), images

def ensure_notes(text_area: str, upload) -> Tuple[str, List[Tuple[str, bytes]]]:
    txt = text_area.strip()
    imgs: List[Tuple[str, bytes]] = []
    if upload:
        up_text, up_imgs = read_file(upload)
        if up_text:
            txt = (txt + "\n" + up_text).strip() if txt else up_text
        imgs = up_imgs
        st.session_state.last_title = upload.name
    if not txt and not imgs:
        st.warning("Upload a file or paste notes first.")
        st.stop()
    st.session_state.notes_text = txt
    return txt, imgs

def ask_openai(prompt: str, system: str = "You are a helpful study assistant. Be concise and clear."):
    client = get_client()
    resp = client.chat.completions.create(
        model=MODEL_TEXT,
        messages=[{"role":"system","content":system},{"role":"user","content":prompt}],
        temperature=0.4,
    )
    return resp.choices[0].message.content.strip()

def ask_openai_vision(question: str, images: List[Tuple[str, bytes]], text_hint: str):
    """
    Sends up to 2 images with a text hint to vision model.
    """
    client = get_client()
    parts = [{"type":"text","text": f"Use the images and this text hint to answer:\n\n{text_hint}\n\n{question}"}]
    for i,(fname, b) in enumerate(images[:2]):
        b64 = base64.b64encode(b).decode()
        mime = "image/png" if fname.lower().endswith(".png") else "image/jpeg"
        parts.append({"type":"image_url","image_url":{"url": f"data:{mime};base64,{b64}"}})
    resp = client.chat.completions.create(
        model=MODEL_VISION,
        messages=[{"role":"user","content":parts}],
        temperature=0.4,
    )
    return resp.choices[0].message.content.strip()

def adaptive_quiz_count(text: str) -> int:
    # very light heuristic; model ultimately decides content
    n = max(3, min(20, len(text.split()) // 180))
    return n

# ---------- SIDEBAR ----------
with st.sidebar:
    st.markdown("### ℹ️ About Zentra")
    st.write("Zentra accelerates learning with clean summaries, active-recall flashcards, adaptive quizzes, and mock exams — plus an AI tutor. Consistency + feedback = progress.")

    st.markdown("### 🛠️ What each tool does")
    st.markdown("- **Summaries** → exam-ready bullet points.\n- **Flashcards** → spaced-repetition Q/A.\n- **Quizzes** → MCQs with explanations (AI chooses count).\n- **Mock Exams** → multi-section exam with marking guide.\n- **Ask Zentra** → your study tutor/chat.")

    st.markdown("### 🧪 Mock exam evaluation")
    st.write("We generate sections (MCQ, short, long, fill-in). Marking is criterion-based; length scales with your notes. Difficulty: **Easy / Standard / Hard**.")

    st.markdown("### 🗂️ History")
    st.caption("Recent quizzes")
    if st.session_state.history_quiz:
        for i,q in enumerate(st.session_state.history_quiz[-5:][::-1],1):
            st.write(f"{i}. {q}")
    else:
        st.write("No quizzes yet.")
    st.caption("Recent mock exams")
    if st.session_state.history_mock:
        for i,m in enumerate(st.session_state.history_mock[-5:][::-1],1):
            st.write(f"{i}. {m}")
    else:
        st.write("No mock exams yet.")

    st.markdown("---")
    st.markdown("**Disclaimer**: Zentra is an AI assistant. Always verify before exams.")

# ---------- HERO ----------
st.markdown(
    f"""
<div class="hero">
  <h1>⚡ Zentra — AI Study Buddy</h1>
  <p>Smarter notes → Better recall → Higher scores.</p>
</div>
""",
    unsafe_allow_html=True,
)

st.info("👋 Welcome to Zentra! Upload your notes and let AI transform them into study material.", icon="🖐️")

# ---------- UPLOAD ----------
st.markdown("### 📁 Upload your notes")
col_up, col_mode = st.columns([3,2], vertical_alignment="bottom")

with col_up:
    uploaded = st.file_uploader(
        "Drag and drop files here",
        type=["pdf","docx","txt","png","jpg","jpeg"],
        help="Supports PDF, DOCX, TXT — and images if you enable Vision.",
    )
    pasted = st.text_area("Or paste your notes here…", height=150, label_visibility="collapsed")

with col_mode:
    st.write("**Analysis mode**")
    mode = st.radio("", ["Text only","Include images (Vision)"], horizontal=True, label_visibility="collapsed")

# ---------- STUDY TOOLS (row with tooltips + Ask Zentra) ----------
st.markdown("### ✨ Study Tools")
c1,c2,c3,c4,c5 = st.columns([1,1,1,1,1])

with c1:
    go_summary = st.button("📄 Summaries", key="btn_summ", help="Turn your notes into clean exam-ready bullet points.")
with c2:
    go_cards = st.button("🧠 Flashcards", key="btn_cards", help="Create spaced-repetition Q→A pairs.")
with c3:
    go_quiz = st.button("🎯 Quizzes", key="btn_quiz", help="MCQs with explanations — count adapts to content.")
with c4:
    go_mock = st.button("📝 Mock Exams", key="btn_mock", help="Multi-section exam with marking rubric.")
with c5:
    ask_click = st.button("💬 Ask Zentra", key="btn_ask", help="Ask about any subject, explain concepts, build study plans.")

if ask_click:
    st.session_state.show_chat = True

# ---------- ASK ZENTRA FLOATING PANEL ----------
st.markdown('<div id="ask-bubble"></div>', unsafe_allow_html=True)

def render_chat():
    with st.container():
        st.markdown('<div class="ask-panel">', unsafe_allow_html=True)
        st.markdown('<div class="ask-header"><b>💬 Ask Zentra (Tutor)</b><span style="cursor:pointer;" onclick="window.parent.postMessage({type:\'closeChat\'}, \'*\')">✖</span></div>', unsafe_allow_html=True)
        st.markdown('<div class="ask-body">', unsafe_allow_html=True)
        if not st.session_state.chat:
            st.caption("Start by asking: *“Make a 7-day study plan for these notes”*, *“Explain this formula”*, or *“Test me on topic X.”*")
        for role, msg in st.session_state.chat:
            st.markdown(f"**{'You' if role=='user' else 'Zentra'}:** {msg}")
        st.markdown('</div>', unsafe_allow_html=True)

        q = st.text_input("", key="ask_input", placeholder="Ask anything…", label_visibility="collapsed")
        send = st.button("Send", key="ask_send")
        st.markdown('</div>', unsafe_allow_html=True)

        if send and q.strip():
            st.session_state.chat.append(("user", q.strip()))
            try:
                text_hint = st.session_state.notes_text
                ans = ask_openai(f"You are Zentra. Answer briefly and clearly.\n\nNotes (if any):\n{text_hint}\n\nUser: {q}")
            except Exception as e:
                ans = f"Sorry, I hit an error: {e}"
            st.session_state.chat.append(("assistant", ans))
            st.rerun()

# small JS to close the chat panel
st.components.v1.html("""
<script>
window.addEventListener("message", (e)=>{
  if(e.data && e.data.type==="closeChat"){
    const btn = window.parent.document.querySelector('button[kind="secondary"]');
  }
});
</script>
""", height=0)

if st.session_state.show_chat:
    render_chat()

# ---------- HANDLERS ----------
def handle_summary(text):
    with st.spinner("Generating summary…"):
        prompt = f"""Summarize the following notes into clear, exam-ready bullet points.
Focus on definitions, laws, steps, formulas, and must-know facts.
Avoid fluff. Keep structure tight with short bullets.

Notes:
{text}
"""
        out = ask_openai(prompt)
        st.markdown("#### ✅ Summary")
        st.markdown(out)

def handle_flashcards(text):
    with st.spinner("Generating flashcards…"):
        prompt = f"""Create high-quality flashcards from these notes.
Return as bullet points in the format **Q:** …  **A:** …
Cards should fully cover the content with 1 concept per card.

Notes:
{text}"""
        out = ask_openai(prompt)
        st.markdown("#### 🧠 Flashcards")
        st.markdown(out)

def handle_quiz(text, include_images, images):
    n = adaptive_quiz_count(text)
    with st.spinner("Building quiz…"):
        base = f"""Create {n} multiple-choice questions (4 options each) from the notes.
Label answers A–D and provide a brief explanation for each correct answer.
Vary difficulty and cover all key areas. Return in Markdown."""
        if include_images and images:
            out = ask_openai_vision(base, images, text)
        else:
            out = ask_openai(base + "\n\nNotes:\n" + text)
        st.session_state.history_quiz.append(st.session_state.last_title)
        st.markdown("#### 🎯 Quiz")
        st.markdown(out)

def handle_mock(text, difficulty, include_images, images):
    with st.spinner("Composing mock exam…"):
        base = f"""Create a **{difficulty}** mock exam from the notes.
Include sections:
1) MCQs (4 options),
2) Short-answer,
3) Long-answer (essay),
4) Fill-in.
Scale the exam length to the amount of content. Provide a marking scheme/rubric.
Return well-structured Markdown."""
        if include_images and images:
            out = ask_openai_vision(base, images, text)
        else:
            out = ask_openai(base + "\n\nNotes:\n" + text)
        st.session_state.history_mock.append(st.session_state.last_title)
        st.markdown("#### 📝 Mock Exam")
        st.markdown(out)

# Click actions
include_images = (mode == "Include images (Vision)")

if go_summary or go_cards or go_quiz or go_mock:
    text, images = ensure_notes(pasted, uploaded)

if go_summary:
    handle_summary(text)

if go_cards:
    handle_flashcards(text)

if go_quiz:
    handle_quiz(text, include_images, images)

if go_mock:
    # show difficulty AFTER click
    st.markdown("#### Select difficulty")
    diff = st.segmented_control("Difficulty", options=["Easy","Standard","Hard"], default="Standard", key="mock_diff")
    if st.button("Generate Mock", type="primary"):
        handle_mock(text, diff, include_images, images)

# ---------- Small hover helper under tools ----------
st.caption("Tip: hover each tool button to see what it does. Ask Zentra can help with every subject — explanations, study plans, and line-by-line clarifications.")
