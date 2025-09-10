# app.py  —  Zentra: AI Study Buddy (polished, fixed PDF + persistent chat)

import os, io, re, time
from dataclasses import dataclass
import streamlit as st

# ---------- LLM ----------
from openai import OpenAI
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
MODEL = "gpt-4o-mini"  # cheap + capable

# ---------- Optional parsers ----------
# PDFs
try:
    import pdfplumber
except Exception:
    pdfplumber = None
# DOCX
try:
    import docx
except Exception:
    docx = None


# ---------- Helpers ----------
def _clean(s: str) -> str:
    # tame length & whitespace
    s = re.sub(r'\s+', ' ', s).strip()
    MAX = 18000  # ~12k tokens-ish cap
    return s[:MAX]

def text_from_pdf(file: io.BytesIO) -> str:
    if not pdfplumber:
        return ""
    text = []
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            try:
                text.append(page.extract_text() or "")
            except Exception:
                continue
    return "\n".join(text)

def text_from_docx(file: io.BytesIO) -> str:
    if not docx:
        return ""
    d = docx.Document(file)
    return "\n".join(p.text for p in d.paragraphs)

def extract_text(uploaded_file) -> str:
    if not uploaded_file:
        return ""
    name = (uploaded_file.name or "").lower()
    data = uploaded_file.read()
    buf = io.BytesIO(data)
    if name.endswith(".pdf"):
        return text_from_pdf(buf)
    if name.endswith(".docx") or name.endswith(".doc"):
        return text_from_docx(buf)
    # txt or unknown → treat as text
    try:
        return data.decode("utf-8", errors="ignore")
    except Exception:
        return ""

def ensure_notes():
    """Return the canonical notes text from session (pdf or paste)."""
    notes = st.session_state.get("note_text", "").strip()
    if not notes:
        st.warning("Upload a file or paste some notes first.")
        st.stop()
    return notes

def call_llm(system, user, temperature=0.2):
    resp = client.chat.completions.create(
        model=MODEL,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user}
        ],
    )
    return resp.choices[0].message.content.strip()

# ---------- Feature builders ----------
def make_summary(notes: str) -> str:
    sys = "You are Zentra, an exam-focused tutor. Be concise and precise."
    usr = f"""Create an exam-ready summary of the notes below.
- Use short bullets with bolded keywords.
- Cover ALL key ideas (no fluff).
- Include formulas, definitions, dates, and cause→effect if relevant.
- Finish with 5 'check-your-understanding' quick questions.

NOTES:
{notes}"""
    return call_llm(sys, _clean(usr))

def estimate_quiz_sizes(notes: str):
    wc = len(notes.split())
    if wc < 500:      return [3, 5, 10], 5
    if wc < 2000:     return [10, 15], 12
    if wc < 6000:     return [15, 20], 18
    return [20, 25], 20

def make_flashcards(notes: str) -> str:
    sys = "You are Zentra, an active-recall coach."
    usr = f"""Generate high-yield flashcards from the notes.
- Use 'Q:' / 'A:' pairs.
- 1 concept per card.
- Cover *all* subtopics;  crisp wording.
- 20–40 cards if content is long, fewer if short.

NOTES:
{notes}"""
    return call_llm(sys, _clean(usr))

def make_quiz(notes: str, count: int) -> str:
    sys = "You are Zentra, a strict exam setter."
    usr = f"""Create {count} multiple-choice questions from the notes.
- 4 options (A–D) each, only one correct.
- Mix easy/medium/hard.
- After listing all questions, provide an **Answer Key** with one-line explanations.

NOTES:
{notes}"""
    return call_llm(sys, _clean(usr))

def make_mock_exam(notes: str, difficulty: str) -> str:
    sys = "You are Zentra, an assessment designer."
    usr = f"""Design a full mock exam ({difficulty} level) from the notes:
Sections:
1) Multiple choice (8–12)
2) Short answer (5–8)
3) Long answer/essay (1–2)
4) Problem/Calculation (if relevant)

Rules:
- Cover the *entire* syllabus implied by the notes.
- Label marks per question; total 100 marks.
- After paper, add **Marking Scheme** (concise criteria & model answers).

NOTES:
{notes}"""
    return call_llm(sys, _clean(usr))

# ---------- UI: page ----------
st.set_page_config(
    page_title="Zentra — AI Study Buddy",
    page_icon="⚡",
    layout="centered"
)

# CSS polish + hide streamlit chrome
st.markdown("""
<style>
/* Hide default Streamlit header/footer */
header[data-testid="stHeader"] {visibility: hidden;}
footer {visibility: hidden;}
/* Hero card */
.hero {
  background: linear-gradient(135deg,#6e2bff 0%,#7a37ff 30%,#7d4fff 60%,#18b3ff 100%);
  color: #fff; border-radius: 16px; padding: 22px 20px; margin-top: -32px; margin-bottom: 18px;
  box-shadow: 0 8px 24px rgba(18,18,18,.25);
}
.hero h1 {font-size: 1.7rem; margin: 0 0 8px 0; font-weight: 800;}
.hero p {opacity:.95; margin: 0 0 10px 0;}
.chips {display:flex; gap:10px; flex-wrap: wrap;}
.chips .chip {
  background: rgba(255,255,255,.12); color:#fff; padding:8px 14px; border-radius:999px; cursor:pointer;
  border:1px solid rgba(255,255,255,.25); font-weight:600; transition:all .15s ease;
}
.chips .chip:hover {transform: translateY(-2px); background: rgba(255,255,255,.2);}
.chips .ask {background:#ffe26b; color:#1a1a1a; border-color:#ffd84d; box-shadow:0 4px 16px rgba(255,228,89,.35);}
.section-title{font-weight:800; font-size:1.05rem; margin:6px 0 4px;}
.small-muted{font-size:.9rem; opacity:.8}
.round {border-radius: 12px !important;}
/* Ask Zentra popup */
.zchat {
  position: fixed; right: 18px; bottom: 18px; width: min(420px, 95vw);
  background: #0f1116; border: 1px solid #2b2f3a; border-radius: 14px; box-shadow: 0 12px 36px rgba(0,0,0,.45); z-index: 999;
  overflow:hidden;
}
.zchat-header {display:flex; justify-content:space-between; align-items:center; padding:10px 12px; background:#171a22;}
.zchat-title {font-weight:700;}
.zchat-body {padding: 8px 12px 12px;}
.ask-fab {position: fixed; right: 18px; bottom: 18px; z-index: 998;}
.ask-fab button {box-shadow: 0 10px 24px rgba(255,228,89,.35);}
</style>
""", unsafe_allow_html=True)

# ---------- session ----------
for k, v in {
    "note_text": "",
    "summary": "",
    "flashcards": "",
    "quiz": "",
    "mock": "",
    "chat_open": False,
    "chat": [],
}.items():
    st.session_state.setdefault(k, v)

# ---------- HERO ----------
with st.container():
    st.markdown(
        """
<div class="hero">
  <h1>⚡ Zentra — AI Study Buddy</h1>
  <p>Smarter notes → better recall → higher scores. Upload or paste your notes; Zentra builds summaries, flashcards, quizzes & mock exams — plus a tutor you can chat with.</p>
  <div class="chips">
    <span class="chip" id="chip-sum">Summaries</span>
    <span class="chip" id="chip-fc">Flashcards</span>
    <span class="chip" id="chip-quiz">Quizzes</span>
    <span class="chip" id="chip-mock">Mock Exams</span>
    <span class="chip ask" id="chip-ask">Ask Zentra</span>
  </div>
</div>
        """,
        unsafe_allow_html=True
    )

# ---------- INPUT AREA ----------
st.subheader("📥 Upload your notes (PDF / DOCX / TXT) or paste below", anchor=False)
col_u, col_name = st.columns([3,2])
with col_u:
    up = st.file_uploader("Drag and drop files here", type=["pdf", "docx", "txt"], label_visibility="collapsed")
with col_name:
    shortname = st.text_input("Give this note a short name (optional)", placeholder="e.g., Cell Biology Ch. 5")

mode = st.radio("Analysis mode", ["Text only", "Include images (beta)"], horizontal=True)
text_paste = st.text_area("Or paste notes here…", height=160, label_visibility="visible", placeholder="Paste textbook/class notes if you aren’t uploading a file.")

# If file uploaded, extract once and cache in session
if up is not None:
    extracted = extract_text(up)
    if extracted:
        st.session_state.note_text = extracted
else:
    # fall back to paste
    if text_paste.strip():
        st.session_state.note_text = text_paste.strip()

notes_present = bool(st.session_state.note_text.strip())

# ---------- ACTION BAR ----------
st.markdown('<div class="section-title">Actions</div>', unsafe_allow_html=True)
ab = st.container()
with ab:
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if st.button("✨ Generate Summary", use_container_width=True, disabled=not notes_present):
            notes = ensure_notes()
            with st.spinner("Summarizing…"):
                st.session_state.summary = make_summary(notes)
                st.toast("Summary ready!", icon="✨")
    with c2:
        if st.button("🔑 Make Flashcards", use_container_width=True, disabled=not notes_present):
            notes = ensure_notes()
            with st.spinner("Creating flashcards…"):
                st.session_state.flashcards = make_flashcards(notes)
                st.toast("Flashcards ready!", icon="🗂️")
    with c3:
        if st.button("🎯 Generate Quiz", use_container_width=True, disabled=not notes_present):
            notes = ensure_notes()
            opts, rec = estimate_quiz_sizes(notes)
            # Let AI choose, but still align to suggested sizes
            count = rec
            with st.spinner(f"Building a {count}-question quiz…"):
                st.session_state.quiz = make_quiz(notes, count)
                st.toast("Quiz ready!", icon="🎯")
    with c4:
        diff = st.selectbox("Difficulty", ["Easy", "Standard", "Difficult"], index=1, label_visibility="collapsed")
        if st.button("📝 Mock Exam", use_container_width=True, disabled=not notes_present):
            notes = ensure_notes()
            with st.spinner(f"Designing a {diff.lower()} mock exam…"):
                st.session_state.mock = make_mock_exam(notes, diff)
                st.toast("Mock exam ready!", icon="📝")

st.caption("Tip: Buttons stay enabled once notes are present from either upload or paste.")

# ---------- OUTPUT ----------
st.divider()
tab1, tab2, tab3, tab4 = st.tabs(["📝 Summary", "🗂️ Flashcards", "🎯 Quiz", "📝 Mock Exam"])

with tab1:
    if st.session_state.summary:
        st.markdown(st.session_state.summary)
        st.download_button("Download summary (.txt)", st.session_state.summary.encode("utf-8"),
                           file_name=f"{shortname or 'summary'}.txt")
    else:
        st.info("No summary yet. Click **Generate Summary** above.")

with tab2:
    if st.session_state.flashcards:
        st.markdown(st.session_state.flashcards)
        st.download_button("Download flashcards (.txt)", st.session_state.flashcards.encode("utf-8"),
                           file_name=f"{shortname or 'flashcards'}.txt")
    else:
        st.info("No flashcards yet. Click **Make Flashcards** above.")

with tab3:
    if st.session_state.quiz:
        st.markdown(st.session_state.quiz)
        st.download_button("Download quiz (.txt)", st.session_state.quiz.encode("utf-8"),
                           file_name=f"{shortname or 'quiz'}.txt")
    else:
        st.info("No quiz yet. Click **Generate Quiz** above.")

with tab4:
    if st.session_state.mock:
        st.markdown(st.session_state.mock)
        st.download_button("Download mock exam (.txt)", st.session_state.mock.encode("utf-8"),
                           file_name=f"{shortname or 'mock_exam'}.txt")
    else:
        st.info("No mock exam yet. Choose difficulty and click **Mock Exam**.")

st.write("")  # spacer

# ---------- ASK ZENTRA POPUP ----------
def render_chat():
    st.markdown('<div class="zchat">', unsafe_allow_html=True)
    # header
    h1, h2 = st.columns([8,1])
    with h1:
        st.markdown('<div class="zchat-header"><span class="zchat-title">🤖 Ask Zentra</span></div>', unsafe_allow_html=True)
    with h2:
        if st.button("✖", key="close_chat"):
            st.session_state.chat_open = False
            st.stop()

    st.markdown('<div class="zchat-body">', unsafe_allow_html=True)
    # sample prompts row
    st.caption("Try: “Make a study plan for 7 days”, “Explain this paragraph”, “Test me on this section”.")
    # chat history
    for role, msg in st.session_state.chat:
        with st.chat_message(role):
            st.markdown(msg)

    user_msg = st.chat_input("Ask about your uploaded/pasted notes, or anything related.")
    if user_msg:
        st.session_state.chat.append(("user", user_msg))
        with st.chat_message("user"):
            st.markdown(user_msg)

        context = st.session_state.note_text if st.session_state.note_text else ""
        sys = "You are Zentra, a patient, precise study tutor. Use the provided context if relevant."
        usr = f"Context (may be empty):\n{_clean(context)}\n\nQuestion:\n{user_msg}"
        with st.chat_message("assistant"):
            with st.spinner("Zentra is thinking…"):
                reply = call_llm(sys, usr, temperature=0.3)
                st.markdown(reply)
        st.session_state.chat.append(("assistant", reply))
    st.markdown('</div></div>', unsafe_allow_html=True)

# Ask chip / FAB
ask_col = st.columns([8,1])[1]
with ask_col:
    if st.button("💬 Ask Zentra", key="ask_fab"):
        st.session_state.chat_open = True

if st.session_state.chat_open:
    render_chat()

# ---------- Hero chip JS wiring (cosmetic only) ----------
st.markdown("""
<script>
const sum = window.parent.document.getElementById("chip-sum");
const fc  = window.parent.document.getElementById("chip-fc");
const qz  = window.parent.document.getElementById("chip-quiz");
const mk  = window.parent.document.getElementById("chip-mock");
const ask = window.parent.document.getElementById("chip-ask");
if (sum){sum.onclick = ()=>window.parent.location.hash="#📝 Summary";}
if (fc){fc.onclick  = ()=>window.parent.location.hash="#🗂️ Flashcards";}
if (qz){qz.onclick  = ()=>window.parent.location.hash="#🎯 Quiz";}
if (mk){mk.onclick  = ()=>window.parent.location.hash="#📝 Mock Exam";}
if (ask){ask.onclick= ()=>window.parent.document.querySelector('button[k="ask_fab"]').click();}
</script>
""", unsafe_allow_html=True)
