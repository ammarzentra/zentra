# Zentra — AI Study Buddy (stable)
# - Always-visible sidebar (purpose, how tools work, evaluation, history)
# - Ask Zentra: floating chat panel on the right (input INSIDE panel)
# - No stray chat input at the bottom
# - No deprecated Streamlit APIs / yellow warnings
# - Hides Streamlit watermark/crown

import io, os, base64
from typing import List, Tuple

import streamlit as st
from openai import OpenAI

# -------------------- PAGE & GLOBAL CSS --------------------
st.set_page_config(
    page_title="Zentra — AI Study Buddy",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",   # <- force sidebar visible
)

st.markdown("""
<style>
/* Hide toolbar/footer/watermark */
[data-testid="stToolbar"], [data-testid="stDecoration"], header {visibility:hidden; height:0 !important;}
footer {visibility:hidden;}
a[class*="viewerBadge"], div[class*="viewerBadge"], #ViewerBadgeContainer {display:none !important;}
.block-container {padding-top:1.0rem; padding-bottom:3.5rem; max-width:1200px;}

/* Hero */
.hero {background:linear-gradient(90deg,#6a11cb 0%,#2575fc 100%); padding:22px; border-radius:16px; color:#fff;}
.hero h1{margin:0 0 6px 0; font-size:34px;}
.hero p{margin:0; opacity:.92}

/* Tool buttons */
.tool-btn{display:inline-block; padding:10px 16px; border-radius:12px; background:#0e1117; color:#fff;
          border:1px solid #333; margin:8px 10px 0 0;}
.tool-btn:hover{background:#171b22;}

/* Ask Zentra floating panel */
.ask-panel{position:fixed; right:22px; top:100px; width:min(420px,92vw); height:70vh; background:#0e1117;
           border:1px solid #2b2f36; border-radius:14px; z-index:9999; box-shadow:0 10px 28px rgba(0,0,0,.45);
           overflow:hidden;}
.ask-header{display:flex; justify-content:space-between; align-items:center; padding:10px 12px;
            border-bottom:1px solid #20242c; font-weight:600;}
.ask-body{padding:12px; height:calc(70vh - 126px); overflow:auto;}
.ask-input{padding:10px 12px; border-top:1px solid #20242c; background:#0e1117;}
.message-bubble{margin:6px 0;}
.me{color:#e6edf3;}
.ze{color:#a5d6ff;}
</style>
""", unsafe_allow_html=True)

# -------------------- STATE --------------------
if "show_chat" not in st.session_state: st.session_state.show_chat = False
if "chat" not in st.session_state: st.session_state.chat = []  # list[(role, text)]
if "notes_text" not in st.session_state: st.session_state.notes_text = ""
if "last_title" not in st.session_state: st.session_state.last_title = "Untitled notes"
if "history_quiz" not in st.session_state: st.session_state.history_quiz = []
if "history_mock" not in st.session_state: st.session_state.history_mock = []

# -------------------- OPENAI --------------------
def get_client() -> OpenAI:
    key = st.secrets.get("OPENAI_API_KEY")
    if not key:
        st.error("Add OPENAI_API_KEY in Streamlit secrets.")
        st.stop()
    os.environ["OPENAI_API_KEY"] = key
    return OpenAI()

MODEL_TEXT = "gpt-4o-mini"
MODEL_VISION = "gpt-4o-mini"

# -------------------- FILE READING --------------------
def read_file(uploaded) -> Tuple[str, List[Tuple[str, bytes]]]:
    """Return (plain_text, images[])  where images = [(filename, bytes)]"""
    if not uploaded: return "", []
    name = uploaded.name.lower()
    data = uploaded.read()
    text, images = "", []

    if name.endswith(".txt"):
        text = data.decode("utf-8", errors="ignore")
    elif name.endswith(".pdf"):
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data))
            pages = [(p.extract_text() or "") for p in reader.pages]
            text = "\n".join(pages)
        except Exception:
            text = ""
    elif name.endswith(".docx"):
        try:
            import docx2txt
            with io.BytesIO(data) as f:
                text = docx2txt.process(f)
        except Exception:
            text = ""
    elif name.endswith((".png",".jpg",".jpeg")):
        images.append((uploaded.name, data))
    else:
        text = data.decode("utf-8", errors="ignore")

    return text.strip(), images

def ensure_notes(pasted: str, uploaded):
    txt = pasted.strip()
    imgs: List[Tuple[str, bytes]] = []
    if uploaded:
        t, ii = read_file(uploaded)
        if t: txt = (txt + "\n" + t).strip() if txt else t
        imgs = ii
        st.session_state.last_title = uploaded.name
    if not txt and not imgs:
        st.warning("Upload a file or paste notes first.")
        st.stop()
    st.session_state.notes_text = txt
    return txt, imgs

# -------------------- OPENAI HELPERS --------------------
def ask_openai(user_prompt: str, system: str = "You are **Zentra**, a precise, friendly study tutor. Answer clearly and briefly."):
    client = get_client()
    resp = client.chat.completions.create(
        model=MODEL_TEXT,
        messages=[{"role":"system","content":system},{"role":"user","content":user_prompt}],
        temperature=0.4,
    )
    return resp.choices[0].message.content.strip()

def ask_openai_vision(question: str, images: List[Tuple[str, bytes]], text_hint: str):
    client = get_client()
    parts = [{"type":"text","text": f"Use the images + this text hint to answer.\n\nTEXT HINT:\n{text_hint}\n\nQUESTION:\n{question}"}]
    for fname, b in images[:2]:
        b64 = base64.b64encode(b).decode()
        mime = "image/png" if fname.lower().endswith(".png") else "image/jpeg"
        parts.append({"type":"image_url","image_url":{"url": f"data:{mime};base64,{b64}"}})
    resp = client.chat.completions.create(model=MODEL_VISION, messages=[{"role":"user","content":parts}], temperature=0.4)
    return resp.choices[0].message.content.strip()

def adaptive_quiz_count(text: str) -> int:
    return max(3, min(20, len(text.split()) // 180))

# -------------------- SIDEBAR (always visible) --------------------
with st.sidebar:
    st.markdown("### ℹ️ About Zentra")
    st.write("Zentra accelerates learning with clean **summaries**, active-recall **flashcards**, **adaptive quizzes**, and **mock exams** — plus an AI tutor. Consistency + feedback = progress.")

    st.markdown("### 🛠️ What each tool does")
    st.markdown(
        "- **Summaries** → exam-ready bullet points.\n"
        "- **Flashcards** → spaced-repetition Q/A.\n"
        "- **Quizzes** → MCQs with explanations (AI decides count to cover topics).\n"
        "- **Mock Exams** → multi-section exam (MCQ, short, long, fill-in) with marking guide.\n"
        "- **Ask Zentra** → chat tutor for any subject, line-by-line clarifications, study plans."
    )

    st.markdown("### 🧪 Mock exam evaluation")
    st.write("Length scales with note size; difficulty you pick (**Easy / Standard / Hard**). Scoring is criterion-based per section.")

    st.markdown("### 🗂️ Recent activity")
    st.caption("Quizzes")
    if st.session_state.history_quiz:
        for i, t in enumerate(st.session_state.history_quiz[-5:][::-1], 1):
            st.write(f"{i}. {t}")
    else:
        st.write("No quizzes yet.")
    st.caption("Mock exams")
    if st.session_state.history_mock:
        for i, t in enumerate(st.session_state.history_mock[-5:][::-1], 1):
            st.write(f"{i}. {t}")
    else:
        st.write("No mock exams yet.")

    st.markdown("---")
    st.caption("Disclaimer: Zentra is an AI assistant. Always verify before exams.")

# -------------------- HERO --------------------
st.markdown('<div class="hero"><h1>⚡ Zentra — AI Study Buddy</h1><p>Smarter notes → Better recall → Higher scores.</p></div>', unsafe_allow_html=True)
st.info("👋 Welcome to Zentra! Upload your notes and let AI transform them into study material.", icon="👋")

# -------------------- UPLOAD --------------------
st.markdown("### 📁 Upload your notes")
col_u, col_m = st.columns([3,2], vertical_alignment="bottom")

with col_u:
    uploaded = st.file_uploader(
        "Drag and drop file here",
        type=["pdf","docx","txt","png","jpg","jpeg"],
        help="Supports PDF, DOCX, TXT. Enable “Include images (Vision)” to use images.",
    )
    pasted = st.text_area("Or paste your notes here…", height=140, label_visibility="collapsed")
with col_m:
    st.write("**Analysis mode**")
    mode = st.radio("", ["Text only", "Include images (Vision)"], horizontal=True, label_visibility="collapsed")

include_images = (mode == "Include images (Vision)")

# -------------------- TOOLS + ASK ZENTRA LAUNCH --------------------
st.markdown("### ✨ Study Tools")
c1, c2, c3, c4, c5 = st.columns([1,1,1,1,1])

with c1:
    go_summary = st.button("📄 Summaries", help="Turn notes into clean exam-ready bullets.")
with c2:
    go_cards   = st.button("🧠 Flashcards", help="Create spaced-repetition Q↔A cards.")
with c3:
    go_quiz    = st.button("🎯 Quizzes", help="MCQs with explanations. Count adapts to content.")
with c4:
    go_mock    = st.button("📝 Mock Exams", help="Multi-section exam with marking rubric.")
with c5:
    open_chat  = st.button("💬 Ask Zentra", help="Tutor for any subject: explanations, study plans, clarifications.")

if open_chat:
    st.session_state.show_chat = True

# -------------------- ASK ZENTRA PANEL (with input INSIDE) --------------------
def render_chat_panel():
    st.markdown('<div class="ask-panel">', unsafe_allow_html=True)
    st.markdown('<div class="ask-header">💬 Ask Zentra (Tutor)<span></span></div>', unsafe_allow_html=True)

    # messages
    st.markdown('<div class="ask-body">', unsafe_allow_html=True)
    if not st.session_state.chat:
        st.caption("Try: *“Make a 7-day study plan from my notes”*, *“Explain supply vs demand”*, *“Test me on Chapter 3.”*")
    for role, msg in st.session_state.chat:
        who = "You" if role == "user" else "Zentra"
        css = "me" if role == "user" else "ze"
        st.markdown(f'<div class="message-bubble {css}"><b>{who}:</b> {msg}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # input
    with st.container():
        st.markdown('<div class="ask-input">', unsafe_allow_html=True)
        q = st.text_input("Type your question…", key="ask_q", label_visibility="collapsed")
        cols = st.columns([1,1])
        send = cols[0].button("Send", use_container_width=True)
        close = cols[1].button("Close", use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    if close:
        st.session_state.show_chat = False
        st.rerun()

    if send and q.strip():
        st.session_state.chat.append(("user", q.strip()))
        try:
            hint = st.session_state.notes_text
            ans = ask_openai(
                f"You are **Zentra**, a rigorous, kind study tutor. Use the notes if provided.\n\nNotes (may be empty):\n{hint}\n\nUser question: {q.strip()}"
            )
        except Exception as e:
            ans = f"Sorry, an error occurred: {e}"
        st.session_state.chat.append(("assistant", ans))
        st.rerun()

if st.session_state.show_chat:
    render_chat_panel()  # no bottom input anywhere

# -------------------- ACTION HANDLERS --------------------
def handle_summary(text):
    out = ask_openai(
        f"""Summarize the notes into clear, exam-ready bullet points.
Focus on definitions, laws, steps, formulas, diagrams-in-words, and must-know facts.
Avoid fluff. Keep bullets short and organized.

NOTES:
{text}"""
    )
    st.markdown("#### ✅ Summary")
    st.markdown(out)

def handle_flashcards(text):
    out = ask_openai(
        f"""Create comprehensive flashcards that fully cover the content.
Return as bullet points in this format:

**Q:** ...
**A:** ...

One concept per card, crisp wording.

NOTES:
{text}"""
    )
    st.markdown("#### 🧠 Flashcards")
    st.markdown(out)

def adaptive_count(text: str) -> int:
    return max(3, min(20, len(text.split()) // 180))

def handle_quiz(text, include_img, images):
    n = adaptive_count(text)
    base = f"""Create {n} multiple-choice questions (A–D) from the notes.
Vary difficulty; cover all key areas. After each question, state the **correct answer** and a short **explanation**.
Return in clean Markdown."""
    out = ask_openai_vision(base, images, text) if (include_img and images) else ask_openai(base + "\n\nNOTES:\n" + text)
    st.session_state.history_quiz.append(st.session_state.last_title)
    st.markdown("#### 🎯 Quiz")
    st.markdown(out)

def handle_mock(text, difficulty, include_img, images):
    base = f"""Create a **{difficulty}** mock exam from the notes with these sections:
1) MCQs (A–D),
2) Short-answer,
3) Long-answer (essay),
4) Fill-in.
Scale the exam length to the amount of content. Provide a marking scheme/rubric per section.
Return in well-structured Markdown."""
    out = ask_openai_vision(base, images, text) if (include_img and images) else ask_openai(base + "\n\nNOTES:\n" + text)
    st.session_state.history_mock.append(st.session_state.last_title)
    st.markdown("#### 📝 Mock Exam")
    st.markdown(out)
    st.success("Mock exam generated. See sidebar → **Recent activity**.")

# Gate for clicks
if go_summary or go_cards or go_quiz or go_mock:
    text, images = ensure_notes(pasted, uploaded)

if go_summary:
    handle_summary(text)

if go_cards:
    handle_flashcards(text)

if go_quiz:
    handle_quiz(text, include_images, images)

if go_mock:
    st.markdown("#### Select difficulty")
    diff = st.segmented_control("Difficulty", options=["Easy","Standard","Hard"], default="Standard", key="mock_diff")
    if st.button("Generate mock", type="primary"):
        handle_mock(text, diff, include_images, images)

st.caption("Tip: hover each tool to see what it does. Ask Zentra can help with **every subject** — explanations, study plans, and line-by-line clarifications.")
