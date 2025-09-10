# Zentra — AI Study Buddy (final polished, stable)
# - Left "Toolbox" column (always visible on mobile) + real Streamlit sidebar for desktop
# - Study tools row: Summaries, Flashcards, Quizzes, Mock Exams, Ask Zentra
# - Ask Zentra opens a right chat panel (Close / Clear / Send). Submit on Enter.
# - Vision toggle supported (Text only / Include images)
# - Mock difficulty shown only after clicking Mock Exams
# - No duplicate chat inputs, no deprecation warnings, watermark hidden

import os, io, base64, tempfile
from typing import List, Tuple
import streamlit as st
from openai import OpenAI

# -------------------- PAGE & CSS --------------------
st.set_page_config(
    page_title="Zentra — AI Study Buddy",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
/* Hide Streamlit chrome + watermark */
[data-testid="stToolbar"], [data-testid="stDecoration"], header {visibility:hidden;height:0;}
footer {visibility:hidden;}
a[class*="viewerBadge"], div[class*="viewerBadge"], #ViewerBadgeContainer{display:none!important;}

/* Layout polish */
.block-container{padding-top:1rem; padding-bottom:3rem; max-width:1200px;}

/* Hero */
.hero{background:linear-gradient(90deg,#6a11cb 0%,#2575fc 100%);padding:22px;border-radius:16px;color:#fff;margin-bottom:10px;}
.hero h1{margin:0;font-size:34px}
.hero p{margin:4px 0 0;opacity:.92}

/* Buttons */
.tool-btn{padding:10px 16px;border-radius:12px;background:#0e1117;color:#fff;border:1px solid #2e2e2e;font-weight:500}
.tool-btn:hover{background:#171b22;border-color:#3d3d3d}

/* Ask Zentra floating panel */
.ask-panel{position:fixed; right:22px; top:96px; width:min(420px,92vw); height:70vh; background:#0e1117;
           border:1px solid #2b2f36; border-radius:14px; z-index:9999; box-shadow:0 10px 28px rgba(0,0,0,.45);
           display:flex; flex-direction:column;}
.ask-header{display:flex;justify-content:space-between;align-items:center;padding:10px 12px;border-bottom:1px solid #20242c}
.ask-title{font-weight:700}
.ask-controls button{margin-left:6px}
.ask-body{flex:1;padding:12px;overflow-y:auto}
.msg{margin:6px 0}
.me b{color:#e6edf3}
.ze b{color:#a5d6ff}

/* Left toolbox column card style */
.toolbox{background:#0f1116;border:1px solid #262a33;border-radius:12px;padding:12px}
.toolbox h4{margin:4px 0 8px 0}
.toolbox small{opacity:.85}
</style>
""", unsafe_allow_html=True)

# -------------------- STATE --------------------
defaults = {
    "show_chat": False,
    "chat": [],                         # list of (role, text)
    "history_quiz": [],
    "history_mock": [],
    "notes_text": "",
    "last_title": "Untitled notes",
    "pending_mock": False,              # show difficulty only after click
}
for k,v in defaults.items():
    if k not in st.session_state: st.session_state[k] = v

# -------------------- OPENAI --------------------
def _client() -> OpenAI:
    key = st.secrets.get("OPENAI_API_KEY")
    if not key:
        st.error("Add OPENAI_API_KEY to Streamlit secrets.")
        st.stop()
    os.environ["OPENAI_API_KEY"] = key
    return OpenAI()

MODEL_TEXT  = "gpt-4o-mini"
MODEL_VISON = "gpt-4o-mini"

def ask_llm(prompt: str, system: str = "You are **Zentra**, a precise, friendly AI study buddy. Be concise and clear."):
    c = _client()
    r = c.chat.completions.create(
        model=MODEL_TEXT,
        messages=[{"role":"system","content":system},{"role":"user","content":prompt}],
        temperature=0.4,
    )
    return r.choices[0].message.content.strip()

def ask_vision(prompt: str, images: List[Tuple[str, bytes]], text_hint: str):
    c = _client()
    parts = [{"type":"text","text": f"Use the images + text to answer.\n\nTEXT:\n{text_hint}\n\nPROMPT:\n{prompt}"}]
    for name, b in images[:2]:
        b64 = base64.b64encode(b).decode()
        mime = "image/png" if name.lower().endswith(".png") else "image/jpeg"
        parts.append({"type":"image_url","image_url":{"url": f"data:{mime};base64,{b64}"}})
    r = c.chat.completions.create(model=MODEL_VISON, messages=[{"role":"user","content":parts}], temperature=0.4)
    return r.choices[0].message.content.strip()

# -------------------- FILE PARSE --------------------
def read_file(uploaded) -> Tuple[str, List[Tuple[str, bytes]]]:
    if not uploaded: return "", []
    name = uploaded.name.lower(); data = uploaded.read()
    text, images = "", []
    if name.endswith(".txt"):
        text = data.decode("utf-8", "ignore")
    elif name.endswith(".pdf"):
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data))
            text = "\n".join([(p.extract_text() or "") for p in reader.pages])
        except Exception:
            text = ""
    elif name.endswith(".docx"):
        try:
            import docx2txt
            with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
                tmp.write(data); tmp.flush()
                text = docx2txt.process(tmp.name)
        except Exception:
            text = ""
    elif name.endswith((".png",".jpg",".jpeg")):
        images.append((uploaded.name, data))
    else:
        text = data.decode("utf-8", "ignore")
    return text.strip(), images

def ensure_notes(pasted, uploaded):
    txt = (pasted or "").strip()
    imgs: List[Tuple[str, bytes]] = []
    if uploaded:
        t, ii = read_file(uploaded)
        if t: txt = (txt + "\n" + t).strip() if txt else t
        if ii: imgs = ii
        st.session_state.last_title = uploaded.name
    if not txt and not imgs:
        st.warning("Upload a file or paste notes first.")
        st.stop()
    st.session_state.notes_text = txt
    return txt, imgs

def adaptive_quiz_count(txt: str) -> int:
    # ~1 MCQ per ~180 words, capped 3–20
    return max(3, min(20, len(txt.split()) // 180))

# -------------------- REAL SIDEBAR (desktop) --------------------
with st.sidebar:
    st.markdown("### 📊 Toolbox")
    st.markdown("**ℹ️ About Zentra**  \nZentra turns your notes into summaries, flashcards, quizzes, and mock exams — plus an AI tutor.")
    st.markdown("**🛠️ Tools**  \n• Summaries → exam bullets  \n• Flashcards → Q/A recall  \n• Quizzes → MCQs + explanations  \n• Mock Exams → multi-section + rubric  \n• Ask Zentra → tutor/chat")
    st.markdown("**🧪 Mock evaluation**  \nSections: MCQ, short, long, fill-in. Difficulty: Easy / Standard / Hard. Scales with content.")
    st.markdown("**🗂️ History**")
    st.caption("Quizzes:")
    st.write(st.session_state.history_quiz or "—")
    st.caption("Mock exams:")
    st.write(st.session_state.history_mock or "—")
    st.markdown("---")
    st.caption("Disclaimer: AI-generated content — verify before exams.")

# -------------------- HERO --------------------
st.markdown('<div class="hero"><h1>⚡ Zentra — AI Study Buddy</h1><p>Smarter notes → Better recall → Higher scores.</p></div>', unsafe_allow_html=True)
st.info("👋 Welcome to Zentra! Upload your notes and let AI transform them into study material.")

# -------------------- LAYOUT: TOOLBOX (always visible) + MAIN --------------------
left, main = st.columns([1.1, 3.0])  # left column acts like a guaranteed-visible sidebar

with left:
    st.markdown('<div class="toolbox">', unsafe_allow_html=True)
    st.markdown("#### 📊 Toolbox")
    st.markdown("**About**  \nZentra = summaries, flashcards, quizzes, mock exams, tutor.")
    st.markdown("**Tools**  \n• Summaries  \n• Flashcards  \n• Quizzes  \n• Mock Exams  \n• Ask Zentra")
    st.markdown("**Evaluation**  \nMCQ/short/long/fill-in, difficulty scales.")
    st.markdown("**History**")
    st.caption("Quizzes:")
    st.write(st.session_state.history_quiz or "—")
    st.caption("Mocks:")
    st.write(st.session_state.history_mock or "—")
    st.markdown('</div>', unsafe_allow_html=True)

with main:
    # ---------- UPLOAD ----------
    st.markdown("### 📁 Upload your notes")
    col_u, col_m = st.columns([3,2], vertical_alignment="bottom")
    with col_u:
        uploaded = st.file_uploader("Drop files", type=["pdf","docx","txt","png","jpg","jpeg"], help="PDF, DOCX, TXT; images used only if Vision is enabled", label_visibility="collapsed")
        pasted = st.text_area("Or paste your notes here…", height=150, label_visibility="collapsed")
    with col_m:
        st.write("**Analysis mode**")
        mode = st.radio("", ["Text only", "Include images (Vision)"], horizontal=True, label_visibility="collapsed")
    include_images = (mode == "Include images (Vision)")

    # ---------- TOOLS ----------
    st.markdown("### ✨ Study Tools")
    c1,c2,c3,c4,c5 = st.columns(5)
    go_summary = c1.button("📄 Summaries", help="Turn notes into exam-ready bullets.")
    go_cards   = c2.button("🧠 Flashcards", help="Active recall Q↔A.")
    go_quiz    = c3.button("🎯 Quizzes", help="Adaptive MCQs with explanations.")
    go_mock    = c4.button("📝 Mock Exams", help="Multi-section exam with marking.")
    open_chat  = c5.button("💬 Ask Zentra", help="Tutor for any subject, study plans, and clarifications.")

    if open_chat:
        st.session_state.show_chat = True

    # ---------- CHAT PANEL (opens on click, can close/clear) ----------
    def render_chat():
        st.markdown('<div class="ask-panel">', unsafe_allow_html=True)
        # header with controls
        colh1, colh2, colh3, colh4 = st.columns([2,1,1,1])
        with colh1:
            st.markdown('<div class="ask-header"><span class="ask-title">💬 Ask Zentra</span></div>', unsafe_allow_html=True)
        with colh2:
            if st.button("Clear 🗑️"):
                st.session_state.chat = []
                st.rerun()
        with colh3:
            if st.button("Close ❌"):
                st.session_state.show_chat = False
                st.rerun()
        with colh4:
            st.markdown("&nbsp;")

        # messages
        st.markdown('<div class="ask-body">', unsafe_allow_html=True)
        if not st.session_state.chat:
            st.caption("Examples: *Explain this line*, *Make a 7-day plan*, *Test me on chapter X*")
        for role, msg in st.session_state.chat:
            cls = "me" if role=="user" else "ze"
            who = "You" if role=="user" else "Zentra"
            st.markdown(f'<div class="msg {cls}"><b>{who}:</b> {msg}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # input (submit on Enter)
        q = st.text_input("Type your question…", key="zentra_q", label_visibility="collapsed", placeholder="Ask anything…")
        if q:  # pressing Enter submits
            st.session_state.chat.append(("user", q.strip()))
            try:
                ans = ask_llm(f"You are **Zentra**. Use notes if helpful.\n\nNotes (may be empty):\n{st.session_state.notes_text}\n\nUser: {q.strip()}")
            except Exception as e:
                ans = f"Sorry, an error occurred: {e}"
            st.session_state.chat.append(("assistant", ans))
            st.session_state.zentra_q = ""  # clear input
            st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

    if st.session_state.show_chat:
        render_chat()

    # ---------- ACTION HANDLERS ----------
    def do_summary(txt):
        st.subheader("✅ Summary")
        prompt = f"""Summarize the notes into sharp, exam-style bullet points.
Focus on definitions, laws, steps, formulas, and must-know facts. No fluff.

NOTES:
{txt}"""
        st.markdown(ask_llm(prompt))

    def do_cards(txt):
        st.subheader("🧠 Flashcards")
        prompt = f"""Create comprehensive flashcards. Return as:

**Q:** ...
**A:** ...

One concept per card. Be concise and complete.

NOTES:
{txt}"""
        st.markdown(ask_llm(prompt))

    def do_quiz(txt, inc, imgs):
        st.subheader("🎯 Quiz")
        n = adaptive_quiz_count(txt)
        base = f"""Create {n} multiple-choice questions (A–D) with the **correct answer** and a brief **explanation** after each.
Vary difficulty and cover all key areas.

NOTES:
{txt}"""
        out = ask_vision(base, imgs, txt) if (inc and imgs) else ask_llm(base)
        st.session_state.history_quiz.append(st.session_state.last_title)
        st.markdown(out)

    def do_mock(txt, diff, inc, imgs):
        st.subheader("📝 Mock Exam")
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
        st.markdown(out)

    # Orchestrate clicks
    if go_summary or go_cards or go_quiz or go_mock:
        text, images = ensure_notes(pasted, uploaded)

    if go_summary:
        do_summary(text)

    if go_cards:
        do_cards(text)

    if go_quiz:
        do_quiz(text, include_images, images)

    if go_mock:
        # show difficulty ONLY after click
        st.session_state.pending_mock = True

    if st.session_state.pending_mock:
        st.markdown("#### Select difficulty")
        diff = st.radio("", ["Easy","Standard","Hard"], horizontal=True, key="diff_radio")
        if st.button("Generate Mock", type="primary"):
            do_mock(st.session_state.notes_text, diff, include_images, images if 'images' in locals() else [])
            st.session_state.pending_mock = False
