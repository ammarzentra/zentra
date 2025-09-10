# Zentra — AI Study Buddy (stable: working buttons + real sidebar)
# NOTE: set OPENAI_API_KEY in Secrets before deploying.

import os, io, base64, tempfile
from typing import List, Tuple
import streamlit as st
from openai import OpenAI

# ---------- PAGE + CSS ----------
st.set_page_config(
    page_title="Zentra — AI Study Buddy",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Keep header visible so the sidebar toggle/arrow works.
st.markdown("""
<style>
/* Hide watermark + footer only */
a[class*="viewerBadge"], div[class*="viewerBadge"], #ViewerBadgeContainer{display:none!important;}
footer{visibility:hidden;height:0}
/* Tighter layout */
.block-container{padding-top:1rem;padding-bottom:3rem;max-width:1200px;}
/* Hero */
.hero{background:linear-gradient(90deg,#6a11cb 0%,#2575fc 100%);padding:22px;border-radius:16px;color:#fff;margin-bottom:10px;}
.hero h1{margin:0;font-size:34px}
.hero p{margin:6px 0 0;opacity:.92}
</style>
""", unsafe_allow_html=True)

# ---------- STATE ----------
if "chat_open" not in st.session_state: st.session_state.chat_open = False
if "messages"  not in st.session_state: st.session_state.messages = []
if "history_quiz" not in st.session_state: st.session_state.history_quiz = []
if "history_mock" not in st.session_state: st.session_state.history_mock = []
if "notes_text"   not in st.session_state: st.session_state.notes_text = ""
if "last_title"   not in st.session_state: st.session_state.last_title = "Untitled notes"
if "pending_mock" not in st.session_state: st.session_state.pending_mock = False

# ---------- OPENAI ----------
def _client() -> OpenAI:
    key = st.secrets.get("OPENAI_API_KEY")
    if not key:
        st.error("Missing OPENAI_API_KEY in Streamlit Secrets."); st.stop()
    os.environ["OPENAI_API_KEY"] = key
    return OpenAI()

MODEL_TEXT  = "gpt-4o-mini"
MODEL_VISON = "gpt-4o-mini"

def ask_llm(prompt: str, system="You are Zentra, a precise, friendly study buddy. Be concise and clear."):
    r = _client().chat.completions.create(
        model=MODEL_TEXT,
        messages=[{"role":"system","content":system},{"role":"user","content":prompt}],
        temperature=0.4,
    )
    return r.choices[0].message.content.strip()

def ask_vision(prompt: str, images: List[Tuple[str, bytes]], text_hint: str):
    parts = [{"type":"text","text": f"Use the images + text to answer.\n\nTEXT:\n{text_hint}\n\nPROMPT:\n{prompt}"}]
    for name,b in images[:2]:
        b64 = base64.b64encode(b).decode()
        mime = "image/png" if name.lower().endswith(".png") else "image/jpeg"
        parts.append({"type":"image_url","image_url":{"url": f"data:{mime};base64,{b64}"}})
    r = _client().chat.completions.create(model=MODEL_VISON, messages=[{"role":"user","content":parts}], temperature=0.4)
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
    elif name.endswith((".png",".jpg",".jpeg")):
        images.append((uploaded.name, data))
    else:
        text = data.decode("utf-8","ignore")
    return (text or "").strip(), images

def ensure_notes(pasted, uploaded):
    txt = (pasted or "").strip()
    imgs: List[Tuple[str, bytes]] = []
    if uploaded:
        t, ii = read_file(uploaded)
        if t: txt = (txt + "\n" + t).strip() if txt else t
        if ii: imgs = ii
        st.session_state.last_title = uploaded.name
    if len(txt) < 5 and not imgs:
        st.warning("Your notes look empty. Paste text or upload a readable PDF/DOCX (image-only PDFs need the Vision option).")
        st.stop()
    st.session_state.notes_text = txt
    return txt, imgs

def adaptive_quiz_count(txt: str) -> int:
    return max(3, min(20, len(txt.split()) // 180))

# ---------- REAL SIDEBAR ----------
with st.sidebar:
    st.markdown("### 📊 Toolbox")
    st.write("**Zentra** turns notes into **summaries**, **flashcards**, **quizzes**, and **mock exams** — plus an **AI tutor**.")
    st.markdown("**What each tool does**  \n• Summaries → exam bullets  \n• Flashcards → Q/A recall  \n• Quizzes → MCQs + explanations (AI decides count)  \n• Mock Exams → multi-section + rubric  \n• Ask Zentra → tutor/chat")
    st.markdown("**Mock evaluation**  \nMCQ, short, long, fill-in. Difficulty: *Easy / Standard / Hard*. Scales with content.")
    st.markdown("**History**")
    st.caption("Quizzes:"); st.write(st.session_state.history_quiz or "—")
    st.caption("Mocks:");   st.write(st.session_state.history_mock or "—")
    st.markdown("---")
    st.caption("Disclaimer: AI-generated content — verify before exams.")

# ---------- HERO ----------
st.markdown('<div class="hero"><h1>⚡ Zentra — AI Study Buddy</h1><p>Smarter notes → Better recall → Higher scores.</p></div>', unsafe_allow_html=True)
st.info("Welcome to Zentra! Upload your notes and let AI transform them into study material.")

# ---------- LAYOUT ----------
if st.session_state.chat_open:
    col_main, col_chat = st.columns([3, 1.4], gap="large")
else:
    col_main = st.container()
    col_chat = None

with col_main:
    # Upload
    st.markdown("### 📁 Upload your notes")
    cu, cm = st.columns([3,2], vertical_alignment="bottom")
    with cu:
        uploaded = st.file_uploader("Drag and drop file here", type=["pdf","docx","txt","png","jpg","jpeg"], label_visibility="collapsed")
        pasted = st.text_area("Or paste your notes here…", height=150, label_visibility="collapsed")
    with cm:
        st.write("**Analysis mode**")
        mode = st.radio("", ["Text only", "Include images (Vision)"], horizontal=True, label_visibility="collapsed")
    include_images = (mode == "Include images (Vision)")

    # Tools
    st.markdown("### ✨ Study Tools")
    c1,c2,c3,c4,c5 = st.columns(5)
    go_summary = c1.button("📄 Summaries", key="btn_sum")
    go_cards   = c2.button("🧠 Flashcards", key="btn_card")
    go_quiz    = c3.button("🎯 Quizzes",    key="btn_quiz")
    go_mock    = c4.button("📝 Mock Exams", key="btn_mock")
    open_chat  = c5.button("💬 Ask Zentra", key="btn_chat")
    if open_chat:
        st.session_state.chat_open = True
        st.rerun()

    # Handlers (each writes into its own placeholder so you *see* output)
    out_area = st.container()

    def do_summary(txt):
        with st.spinner("Generating summary…"):
            prompt = f"""Summarize the notes into sharp, exam-style bullet points.
Focus on definitions, laws, steps, formulas, and must-know facts. No fluff.

NOTES:
{txt}"""
            out = ask_llm(prompt)
        out_area.subheader("✅ Summary")
        out_area.markdown(out or "_(no content)_")

    def do_cards(txt):
        with st.spinner("Generating flashcards…"):
            prompt = f"""Create comprehensive flashcards. Return as:

**Q:** ...
**A:** ...

One concept per card. Be concise and complete.

NOTES:
{txt}"""
            out = ask_llm(prompt)
        out_area.subheader("🧠 Flashcards")
        out_area.markdown(out or "_(no content)_")

    def do_quiz(txt, inc, imgs):
        with st.spinner("Building quiz…"):
            n = adaptive_quiz_count(txt)
            base = f"""Create {n} multiple-choice questions (A–D) with the **correct answer** and a brief **explanation** after each.
Vary difficulty and cover all key areas.

NOTES:
{txt}"""
            out = ask_vision(base, imgs, txt) if (inc and imgs) else ask_llm(base)
        st.session_state.history_quiz.append(st.session_state.last_title)
        out_area.subheader("🎯 Quiz")
        out_area.markdown(out or "_(no content)_")

    def do_mock(txt, diff, inc, imgs):
        with st.spinner("Composing mock exam…"):
            base = f"""Create a **{diff}** mock exam with sections:
1) MCQs (A–D)
2) Short-answer
3) Long-answer (essay)
4) Fill-in

Scale length to content. Provide a marking rubric per section.

NOTES:
{txt}"""
            out = ask_vision(base, imgs, txt) if (inc and imgs) else ask_llm(base)
        st.session_state.history_mock.append(st.session_state.last_title)
        out_area.subheader("📝 Mock Exam")
        out_area.markdown(out or "_(no content)_")

    # Orchestration
    if go_summary or go_cards or go_quiz or go_mock:
        text, images = ensure_notes(pasted, uploaded)

    if go_summary:
        do_summary(text)

    if go_cards:
        do_cards(text)

    if go_quiz:
        do_quiz(text, include_images, images)

    if go_mock:
        st.session_state.pending_mock = True

    if st.session_state.pending_mock:
        st.markdown("#### Select difficulty")
        diff = st.radio("", ["Easy","Standard","Hard"], horizontal=True, key="mock_diff")
        if st.button("Generate Mock", type="primary", key="mock_go"):
            do_mock(st.session_state.notes_text, diff, include_images, images if 'images' in locals() else [])
            st.session_state.pending_mock = False

# ---------- CHAT (unchanged – your favorite) ----------
if st.session_state.chat_open and col_chat is not None:
    with col_chat:
        st.markdown("### 💬 Ask Zentra")
        c1,c2 = st.columns(2)
        if c1.button("Clear", use_container_width=True):
            st.session_state.messages = []; st.rerun()
        if c2.button("Close", use_container_width=True):
            st.session_state.chat_open = False; st.rerun()

        if not st.session_state.messages:
            st.caption("Try: *Explain this line*, *Make a 7-day plan*, *Test me on chapter X*")

        for m in st.session_state.messages:
            with st.chat_message(m["role"]): st.markdown(m["content"])

        user_msg = st.chat_input("Ask anything about your notes or subject…")
        if user_msg:
            st.session_state.messages.append({"role":"user","content":user_msg})
            with st.chat_message("user"): st.markdown(user_msg)
            try:
                reply = ask_llm(
                    f"You are **Zentra**. Use notes if helpful.\n\n"
                    f"NOTES (may be empty):\n{st.session_state.notes_text}\n\n"
                    f"USER: {user_msg}"
                )
            except Exception as e:
                reply = f"Sorry, an error occurred: {e}"
            st.session_state.messages.append({"role":"assistant","content":reply})
            with st.chat_message("assistant"): st.markdown(reply)
            st.rerun()

