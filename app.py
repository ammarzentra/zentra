import os
import re
import io
import time
from typing import List, Dict
import streamlit as st

# ──────────────────────────────────────────────────────────────────────────────
#  OPENAI CLIENT (SDK v1.x)
# ──────────────────────────────────────────────────────────────────────────────
from openai import OpenAI

def make_client() -> OpenAI:
    # Prefer Streamlit secrets in prod; fall back to env for local dev
    api_key = st.secrets.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        st.error("No OpenAI API key found. Add it in Streamlit Secrets or env.")
        st.stop()
    return OpenAI(api_key=api_key)

MODEL = "gpt-4o-mini"

# ──────────────────────────────────────────────────────────────────────────────
#  FILE PARSERS
# ──────────────────────────────────────────────────────────────────────────────
from pypdf import PdfReader
from docx import Document

def read_pdf_bytes(data: bytes) -> str:
    text = []
    try:
        reader = PdfReader(io.BytesIO(data))
        for page in reader.pages:
            t = page.extract_text() or ""
            text.append(t)
    except Exception as e:
        text.append(f"\n[PDF read error: {e}]\n")
    return "\n".join(text)

def read_docx_bytes(data: bytes) -> str:
    try:
        doc = Document(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs)
    except Exception as e:
        return f"[DOCX read error: {e}]"

def normalize_notes(raw: str) -> str:
    s = raw.replace("\r", "\n")
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()

# ──────────────────────────────────────────────────────────────────────────────
#  LLM HELPERS
# ──────────────────────────────────────────────────────────────────────────────
def call_llm(client: OpenAI, system_prompt: str, user_prompt: str, temperature=0.2, max_tokens=1500) -> str:
    resp = client.chat.completions.create(
        model=MODEL,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return resp.choices[0].message.content.strip()

def estimate_complexity(tokens: int) -> Dict[str, int]:
    """
    Decide how many items to generate based on note length.
    tokens ~ rough word count.
    """
    # Soft caps that scale with content
    if tokens < 300:
        return {"flashcards": 10, "mcq": 8, "fib": 4, "short": 2, "essay": 1, "summary_words": 180}
    if tokens < 1200:
        return {"flashcards": 20, "mcq": 16, "fib": 8, "short": 4, "essay": 1, "summary_words": 280}
    if tokens < 3000:
        return {"flashcards": 30, "mcq": 25, "fib": 12, "short": 6, "essay": 2, "summary_words": 400}
    # Large docs
    return {"flashcards": 40, "mcq": 40, "fib": 18, "short": 8, "essay": 3, "summary_words": 650}

# ──────────────────────────────────────────────────────────────────────────────
#  PDF EXPORT (lightweight)
# ──────────────────────────────────────────────────────────────────────────────
from fpdf import FPDF

def to_pdf_bytes(title: str, content_md: str) -> bytes:
    # Simple markdown-to-text (no layout engine) to keep things dependency-light
    text = re.sub(r"[#*_>`-]{1,3}", "", content_md)
    text = text.replace("•", "-")
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.multi_cell(0, 10, title)
    pdf.ln(4)
    pdf.set_font("Arial", "", 11)
    for para in text.split("\n"):
        pdf.multi_cell(0, 7, para)
    out = io.BytesIO()
    pdf.output(out)
    return out.getvalue()

# ──────────────────────────────────────────────────────────────────────────────
#  UI THEME + BRANDING HIDE
# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Zentra — AI Study Buddy", page_icon="⚡", layout="wide")

HIDE_STREAMLIT = """
<style>
/* Hide Streamlit chrome */
#MainMenu {visibility:hidden;}
header {visibility:hidden;}
footer {visibility:hidden;}
/* Tighter mobile paddings */
.block-container {padding-top: 1.2rem; padding-bottom: 2rem;}
/* Pretty hero card */
.hero {
  background: linear-gradient(135deg, #251d49 0%, #4b2a84 100%);
  border-radius: 18px; padding: 22px 22px; color: #fff; border: 1px solid rgba(255,255,255,0.08);
}
.hero h1 {margin: 0 0 8px 0; font-weight: 800;}
.hero p {opacity: .92; font-size: 1.05rem; margin: 0;}
.pill {display:inline-block; padding:6px 10px; margin:8px 8px 0 0; border-radius: 999px; font-size:.85rem;
       background:rgba(255,255,255,.08); border:1px solid rgba(255,255,255,.12)}
/* Buttons */
.stButton>button {
  width: 100%; border-radius: 12px; padding: 12px 16px; font-weight: 700;
  background: linear-gradient(90deg,#7a2bf5,#ff2bb3); border: 0;
}
.stDownloadButton>button {
  width: 100%; border-radius: 10px; padding: 9px 14px; font-weight: 700;
}
/* Cards */
.card {
  border:1px solid rgba(200,200,200,.12); border-radius:12px; padding:16px; background:rgba(255,255,255,.02);
}
.small {font-size:.9rem; opacity:.85}
.kpi {background:#0d0f14;border:1px solid #222531;border-radius:12px;padding:16px;text-align:center}
.kpi h3 {margin:0;font-size:1.6rem}
.kpi p {margin:6px 0 0 0;opacity:.8}
</style>
"""
st.markdown(HIDE_STREAMLIT, unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────
#  SESSION STATE
# ──────────────────────────────────────────────────────────────────────────────
if "history_quizzes" not in st.session_state:
    st.session_state.history_quizzes = []   # list of dicts
if "history_exams" not in st.session_state:
    st.session_state.history_exams = []     # list of dicts
if "chat" not in st.session_state:
    st.session_state.chat = []              # [{"role":"user"/"assistant","content":...}]

client = make_client()

# ──────────────────────────────────────────────────────────────────────────────
#  HERO
# ──────────────────────────────────────────────────────────────────────────────
st.markdown(
    """
<div class="hero">
  <h1>⚡ Zentra – AI Study Buddy</h1>
  <p>Smarter notes → faster recall → higher scores. Upload your notes and let Zentra build <b>summaries</b>, <b>flashcards</b>, <b>quizzes</b>, and <b>mock exams</b> — plus a tutor you can chat with.</p>
  <div>
    <span class="pill">PDF/DOCX/TXT</span>
    <span class="pill">Summaries</span>
    <span class="pill">Flashcards</span>
    <span class="pill">Quizzes</span>
    <span class="pill">Mock Exams</span>
    <span class="pill">Ask Zentra</span>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

# ──────────────────────────────────────────────────────────────────────────────
#  INPUT AREA (UPLOAD or PASTE)
# ──────────────────────────────────────────────────────────────────────────────
st.subheader("Upload notes (PDF / DOCX / TXT) or paste below")
col_u1, col_u2 = st.columns([1.2, 1])
with col_u1:
    up = st.file_uploader("Drag-and-drop or browse files", type=["pdf","docx","txt"], accept_multiple_files=False, label_visibility="collapsed")
with col_u2:
    note_title = st.text_input("Give this note a short name (optional)", placeholder="e.g., Cell Biology Ch. 5")

raw_text = ""
if up is not None:
    data = up.read()
    if up.type == "application/pdf" or (up.name.lower().endswith(".pdf")):
        raw_text = read_pdf_bytes(data)
    elif up.name.lower().endswith(".docx"):
        raw_text = read_docx_bytes(data)
    else:
        try:
            raw_text = data.decode("utf-8", errors="ignore")
        except Exception:
            raw_text = ""

paste_text = st.text_area("Or paste notes here…", placeholder="Paste textbook or class notes if you aren't uploading a file.", height=180)
source_text = normalize_notes(raw_text or paste_text)

if not source_text:
    st.info("Upload a file or paste some notes to get started.")

word_count = len(source_text.split())
complexity = estimate_complexity(word_count)

tabs = st.tabs(["📄 Summaries", "🔑 Flashcards", "🎯 Quiz", "📝 Mock Exam", "💬 Ask Zentra", "📊 Progress"])

# ──────────────────────────────────────────────────────────────────────────────
#  SUMMARIES
# ──────────────────────────────────────────────────────────────────────────────
with tabs[0]:
    st.caption("Zentra writes focused, exam-ready summaries (not fluffy).")
    if st.button("✨ Generate Summary", key="sum_btn", disabled=not source_text):
        with st.spinner("Summarizing…"):
            sys = "You are an expert study coach. Produce compact, accurate study summaries."
            user = f"""Summarize the following notes in ~{complexity['summary_words']} words.
- Use clear headings and bullet points.
- Include key definitions, formulas, dates, and cause→effect chains.
- Be faithful to the source; don't invent facts.

NOTES:
{source_text}
"""
            summary = call_llm(client, sys, user, temperature=0.2, max_tokens=1800)
        st.markdown(summary)

        # Downloads
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            st.download_button("⬇️ Download .txt", data=summary, file_name=f"{note_title or 'notes'}_summary.txt")
        with col_d2:
            st.download_button("⬇️ Download .pdf", data=to_pdf_bytes("Summary", summary), file_name=f"{note_title or 'notes'}_summary.pdf", mime="application/pdf")

# ──────────────────────────────────────────────────────────────────────────────
#  FLASHCARDS
# ──────────────────────────────────────────────────────────────────────────────
with tabs[1]:
    st.caption("Active recall cards — sized to your note length.")
    wanted = st.slider("How many flashcards?", 6, complexity["flashcards"], complexity["flashcards"], help="AI recommends a ceiling based on note size.")
    if st.button("🔑 Generate Flashcards", key="fc_btn", disabled=not source_text):
        with st.spinner("Building flashcards…"):
            sys = "You write excellent two-sided flashcards that test recall without ambiguity."
            user = f"""Create {wanted} flashcards from the notes below.

Output JSON list with objects:
- 'front': the question/prompt
- 'back': the answer (concise but complete)
- Avoid duplicates; cover all key concepts.

NOTES:
{source_text}
"""
            cards_raw = call_llm(client, sys, user, temperature=0.25, max_tokens=2000)
        # Try to render as markdown if JSON isn't clean
        st.markdown("#### Flashcards")
        st.markdown(cards_raw)

        col_d1, col_d2 = st.columns(2)
        with col_d1:
            st.download_button("⬇️ Download .txt", data=cards_raw, file_name=f"{note_title or 'notes'}_flashcards.txt")
        with col_d2:
            st.download_button("⬇️ Download .pdf", data=to_pdf_bytes("Flashcards", cards_raw), file_name=f"{note_title or 'notes'}_flashcards.pdf", mime="application/pdf")

# ──────────────────────────────────────────────────────────────────────────────
#  QUIZ (Different item pool than exam)
# ──────────────────────────────────────────────────────────────────────────────
with tabs[2]:
    st.caption("Quick-check MCQs to gauge understanding (different pool than Mock Exam).")
    n_mcq = st.slider("Number of MCQs", 5, max(10, complexity["mcq"]), min(15, complexity["mcq"]), help="Shorter than the mock exam.")
    if st.button("🎯 Start Quiz", key="quiz_btn", disabled=not source_text):
        with st.spinner("Generating quiz…"):
            sys = "You are a strict test maker. Generate exam-quality MCQs with single correct answers."
            user = f"""Create {n_mcq} **unique** MCQs from the notes below.
- Output in Markdown with numbering.
- Each MCQ: question, 4 options (A–D), and an answer key at the end.
- Ensure this MCQ set is DIFFERENT from any Mock Exam you might generate.

NOTES:
{source_text}
"""
            quiz_md = call_llm(client, sys, user, temperature=0.25, max_tokens=2400)
        st.markdown(quiz_md)

        # Save history
        st.session_state.history_quizzes.append({"title": note_title or "Untitled", "mcq": n_mcq, "ts": int(time.time())})

        col_d1, col_d2 = st.columns(2)
        with col_d1:
            st.download_button("⬇️ Download .txt", data=quiz_md, file_name=f"{note_title or 'notes'}_quiz.txt")
        with col_d2:
            st.download_button("⬇️ Download .pdf", data=to_pdf_bytes("Quiz", quiz_md), file_name=f"{note_title or 'notes'}_quiz.pdf", mime="application/pdf")

# ──────────────────────────────────────────────────────────────────────────────
#  MOCK EXAM (Scaled, mixed sections, graded /100)
# ──────────────────────────────────────────────────────────────────────────────
with tabs[3]:
    st.caption("Full mock exam: MCQ + Fill-in-Blank + Short Answer + Essay, scaled to your notes, graded /100.")
    col_m1, col_m2 = st.columns(2)
    with col_m1:
        difficulty = st.select_slider("Difficulty", options=["Easy","Standard","Hard"], value="Standard")
    with col_m2:
        # Let them cap max length, but default based on complexity
        scale = st.select_slider("Exam length", options=["Short","Medium","Long"], value="Medium")

    if st.button("📝 Generate Mock Exam", key="exam_btn", disabled=not source_text):
        # Adjust counts by difficulty & scale
        base = complexity.copy()
        mult = 1.0
        if scale == "Short": mult *= 0.7
        if scale == "Long":  mult *= 1.25
        if difficulty == "Hard": mult *= 1.1
        if difficulty == "Easy": mult *= 0.9

        counts = {
            "mcq": max(6, int(base["mcq"] * mult)),
            "fib": max(4, int(base["fib"] * mult)),
            "short": max(2, int(base["short"] * mult)),
            "essay": max(1, int(base["essay"] * mult)),
        }

        with st.spinner("Composing a full exam…"):
            sys = "You are an expert examiner who creates rigorous but fair mock exams. You must grade to 100."
            user = f"""Create a **mock exam** from the notes with the following sections and counts, all DIFFERENT from the quiz bank:

1) MCQs: {counts['mcq']} questions, 4 options (A–D), answer key later.
2) Fill-in-the-blank: {counts['fib']} items (one-word or short phrase), answer key later.
3) Short answers: {counts['short']} questions (2–4 sentences each) with **model answers**.
4) Long answers / essays: {counts['essay']} prompts with **model answers** (5–10 bullet points).

After the exam, add:

- **Answer Key** for MCQ + FIB.
- **Marking Scheme** allocating marks so the **total is /100**.
- **Auto-Grader Instructions** (how a student can self-mark short & long answers).
- **Personalized Feedback Template**: strengths, weak areas, next steps.

Ensure coverage is broad across the notes; do not repeat items from the Quiz.

NOTES:
{source_text}
"""
            exam_md = call_llm(client, sys, user, temperature=0.25, max_tokens=4000)

        st.markdown("#### Mock Exam")
        st.markdown(exam_md)

        # Quick parse to get total marks if model returned a line like "Total: 100"
        # We still store standardized /100 in history
        st.session_state.history_exams.append({
            "title": note_title or "Untitled",
            "scale": scale,
            "difficulty": difficulty,
            "counts": counts,
            "score_max": 100,
            "ts": int(time.time())
        })

        col_d1, col_d2 = st.columns(2)
        with col_d1:
            st.download_button("⬇️ Download .txt", data=exam_md, file_name=f"{note_title or 'notes'}_mock_exam.txt")
        with col_d2:
            st.download_button("⬇️ Download .pdf", data=to_pdf_bytes("Mock Exam", exam_md), file_name=f"{note_title or 'notes'}_mock_exam.pdf", mime="application/pdf")

# ──────────────────────────────────────────────────────────────────────────────
#  ASK ZENTRA (Chat)
# ──────────────────────────────────────────────────────────────────────────────
with tabs[4]:
    st.caption("Ask anything about your uploaded notes — or general study help.")
    # Sample prompt chips
    chip_cols = st.columns(4)
    samples = [
        "Make me a 7-day study plan from these notes.",
        "Explain the 3 most testable concepts with examples.",
        "Give me memory hooks (mnemonics) for the key terms.",
        "Create a quick cram sheet for exam morning.",
    ]
    for i, s in enumerate(samples):
        if chip_cols[i].button(s, key=f"chip_{i}", use_container_width=True):
            st.session_state.chat.append({"role":"user","content": s})

    user_msg = st.text_input("Ask Zentra…", placeholder="e.g., Compare mitosis vs meiosis with a table")
    col_c1, col_c2 = st.columns([1, .35])
    with col_c1:
        ask = st.button("💬 Send", use_container_width=True)
    with col_c2:
        clear = st.button("🧹 Clear chat", use_container_width=True)

    if clear:
        st.session_state.chat = []

    if user_msg and ask:
        st.session_state.chat.append({"role":"user","content": user_msg})

    # Build conversation with context from notes (if any)
    if st.session_state.chat:
        convo = [{"role":"system","content":
                  "You are Zentra, a precise, friendly study tutor. If notes were uploaded, use them as primary context; otherwise, answer from general knowledge. Keep answers crisp and actionable."}]
        if source_text:
            convo.append({"role":"system", "content": f"Here are the student's notes:\n\n{source_text[:15000]}"})
        convo.extend(st.session_state.chat)

        if st.session_state.chat and st.session_state.chat[-1]["role"] == "user":
            with st.spinner("Zentra is thinking…"):
                resp = client.chat.completions.create(model=MODEL, messages=convo, temperature=0.2)
            reply = resp.choices[0].message.content.strip()
            st.session_state.chat.append({"role":"assistant","content": reply})

    # Render
    for turn in st.session_state.chat:
        if turn["role"] == "user":
            st.markdown(f"**You:** {turn['content']}")
        else:
            st.markdown(f"**Zentra:** {turn['content']}")

# ──────────────────────────────────────────────────────────────────────────────
#  PROGRESS (only Quizzes & Exams with history)
# ──────────────────────────────────────────────────────────────────────────────
with tabs[5]:
    st.caption("Your activity (local to this device).")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="kpi"><h3>{}</h3><p>Quizzes Taken</p></div>'.format(len(st.session_state.history_quizzes)), unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="kpi"><h3>{}</h3><p>Mock Exams Built</p></div>'.format(len(st.session_state.history_exams)), unsafe_allow_html=True)

    st.markdown("#### Quiz History")
    if not st.session_state.history_quizzes:
        st.markdown("_No quizzes yet._")
    else:
        for q in st.session_state.history_quizzes[::-1]:
            ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(q["ts"]))
            st.markdown(f"- **{q['title']}** · {q['mcq']} MCQs · _{ts}_")

    st.markdown("#### Mock Exam History")
    if not st.session_state.history_exams:
        st.markdown("_No exams yet._")
    else:
        for e in st.session_state.history_exams[::-1]:
            ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(e["ts"]))
            counts = e["counts"]
            st.markdown(f"- **{e['title']}** · {e['scale']} / {e['difficulty']} · MCQ {counts['mcq']}, FIB {counts['fib']}, SA {counts['short']}, Essay {counts['essay']} · _{ts}_")

# ──────────────────────────────────────────────────────────────────────────────
#  DISCLAIMER (collapsible)
# ──────────────────────────────────────────────────────────────────────────────
with st.expander("Disclaimer"):
    st.write(
        "Zentra is an AI assistant. Always verify generated content with your course requirements and your instructor’s guidance."
    )

  
