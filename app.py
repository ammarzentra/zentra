# Zentra — AI Study Buddy (stable: working buttons + real sidebar + fixed Ask Zentra popup)

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
/* Ask panel */
.ask-panel{position:fixed;right:25px;top:90px;width:360px;height:70vh;background:#0e1117;border:1px solid #333;
           border-radius:12px;box-shadow:0 8px 28px rgba(0,0,0,.45);padding:10px;z-index:9999;overflow:hidden;}
.ask-header{font-weight:600;margin-bottom:8px;}
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
    st.write("**How Zentra Works:** Turns notes into smart tools for learning. Smarter notes → better recall → higher scores.")
    st.markdown("### 🎯 What Zentra Offers")
    st.markdown("- **Summaries** → exam-ready bullets\n- **Flashcards** → active recall Q/A\n- **Quizzes** → MCQs + explanations\n- **Mock Exams** → graded, multi-section with evaluation\n- **Ask Zentra** → personal AI tutor")
    st.markdown("### 📝 Mock Evaluation")
    st.write("Includes MCQs, short, long, fill-in. Difficulty: *Easy / Standard / Hard*. Zentra grades and gives feedback.")
    st.markdown("### 📂 History")
    st.caption("Quizzes:"); st.write(st.session_state.history_quiz or "—")
    st.caption("Mocks:");   st.write(st.session_state.history_mock or "—")
    st.markdown("---")
    st.caption("Disclaimer: AI-generated content — verify before exams.")

# ---------- HERO ----------
st.markdown('<div class="hero"><h1>⚡ Zentra — AI Study Buddy</h1><p>Smarter notes → Better recall → Higher scores.</p></div>', unsafe_allow_html=True)
st.info("Welcome to Zentra! Upload your notes and let AI transform them into study material.")

# ---------- LAYOUT ----------
col_main = st.container()

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

    out_area = st.container()

    def do_summary(txt):
        with st.spinner("Generating summary…"):
            out = ask_llm(f"Summarize into sharp exam bullets.\n\nNOTES:\n{txt}")
        out_area.subheader("✅ Summary")
        out_area.markdown(out or "_(no content)_")

    def do_cards(txt):
        with st.spinner("Generating flashcards…"):
            out = ask_llm(f"Create flashcards as **Q:** … **A:** … covering all key points.\n\nNOTES:\n{txt}")
        out_area.subheader("🧠 Flashcards")
        out_area.markdown(out or "_(no content)_")

    def do_quiz(txt, inc, imgs):
        with st.spinner("Building quiz…"):
            n = adaptive_quiz_count(txt)
            base = f"Create {n} MCQs (A–D) with correct answer + brief explanation.\n\nNOTES:\n{txt}"
            out = ask_vision(base, imgs, txt) if (inc and imgs) else ask_llm(base)
        st.session_state.history_quiz.append(st.session_state.last_title)
        out_area.subheader("🎯 Quiz")
        out_area.markdown(out or "_(no content)_")

    def do_mock(txt, diff, inc, imgs):
        with st.spinner("Composing mock exam…"):
            base = f"""Create a **{diff}** mock exam:
1) MCQs (A–D)
2) Short-answer
3) Long-answer
4) Fill-in
Include marking rubric.

NOTES:
{txt}"""
            out = ask_vision(base, imgs, txt) if (inc and imgs) else ask_llm(base)
        st.session_state.history_mock.append(st.session_state.last_title)
        out_area.subheader("📝 Mock Exam")
        out_area.markdown(out or "_(no content)_")

    if go_summary or go_cards or go_quiz or go_mock:
        text, images = ensure_notes(pasted, uploaded)

    if go_summary: do_summary(text)
    if go_cards:   do_cards(text)
    if go_quiz:    do_quiz(text, include_images, images)
    if go_mock:
        st.session_state.pending_mock = True

    if st.session_state.pending_mock:
        st.markdown("#### Select difficulty")
        diff = st.radio("", ["Easy","Standard","Hard"], horizontal=True, key="mock_diff")
        if st.button("Generate Mock", type="primary", key="mock_go"):
            do_mock(st.session_state.notes_text, diff, include_images, images if 'images' in locals() else [])
            st.session_state.pending_mock = False

# ---------- ASK ZENTRA (popup fixed) ----------
if st.session_state.chat_open:
    st.markdown('<div class="ask-panel">', unsafe_allow_html=True)
    st.markdown('<div class="ask-header">💬 Ask Zentra</div>', unsafe_allow_html=True)

    if not st.session_state.messages:
        st.caption("Try: *Explain this formula*, *Make a 7-day plan*, *Test me on topic X*")

    for m in st.session_state.messages:
        with st.chat_message(m["role"]): st.markdown(m["content"])

    user_msg = st.chat_input("Type your question…")
    col1, col2, col3 = st.columns([1,1,1])
    if col1.button("Send") or user_msg:
        if user_msg:
            st.session_state.messages.append({"role":"user","content":user_msg})
            with st.chat_message("user"): st.markdown(user_msg)
            try:
                reply = ask_llm(
                    f"You are Zentra, the AI tutor. Use notes if needed.\n\n"
                    f"NOTES:\n{st.session_state.notes_text}\n\n"
                    f"USER: {user_msg}"
                )
            except Exception as e:
                reply = f"Sorry, error: {e}"
            st.session_state.messages.append({"role":"assistant","content":reply})
            with st.chat_message("assistant"): st.markdown(reply)
            st.rerun()
    if col2.button("Clear"):
        st.session_state.messages.clear(); st.rerun()
    if col3.button("Close"):
        st.session_state.chat_open = False; st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)
