# app.py  — Zentra: AI Study Buddy (final polished build)

import os, io, json, math, textwrap
from typing import List, Dict, Any

import streamlit as st
from openai import OpenAI
from fpdf import FPDF

# Lightweight text extractors
import pdfplumber
try:
    from docx import Document
    HAS_DOCX = True
except:
    HAS_DOCX = False

# ----------------------------- #
#          CONFIG / THEME       #
# ----------------------------- #

st.set_page_config(page_title="Zentra — AI Study Buddy", page_icon="⚡", layout="wide")

# Hide Streamlit badge/menu/footer (free-plan friendly CSS hack)
st.markdown("""
<style>
  #MainMenu {visibility: hidden;}
  footer {visibility: hidden;}
  .viewerBadge_link__qRIco {display: none !important;}
  .stDeployButton {display:none !important;}
  /* Hero gradient card */
  .hero {
      background: linear-gradient(135deg, #6C3CF0 0%, #5D6BF3 35%, #35C3F3 100%);
      border-radius: 18px; padding: 26px 22px; color: white;
      box-shadow: 0 8px 24px rgba(0,0,0,.25);
  }
  .pill { border: 1px solid rgba(255,255,255,.35); color: #fff; padding: 8px 14px; border-radius: 12px; margin-right:10px; }
  .pill:hover { background: rgba(0,0,0,.08); }
  .card {
      border: 1px solid rgba(255,255,255,0.06);
      background: rgba(255,255,255,0.02);
      border-radius: 14px; padding: 14px 16px; margin-bottom: 10px;
  }
  .action-btn {
      background: linear-gradient(135deg, #7C4DFF 0%, #6E8BFF 100%);
      color: #fff; padding: 10px 16px; border-radius: 10px; border: none;
  }
  /* Floating Ask Zentra chat panel */
  .chat-fab {
      position: fixed; right: 18px; bottom: 18px; z-index: 9999;
      background:#7C4DFF; color:#fff; border-radius: 999px; padding:10px 16px;
      box-shadow: 0 8px 20px rgba(0,0,0,.25); cursor:pointer;
  }
  .chat-panel {
      position: fixed; right: 18px; bottom: 70px; width: 360px; max-width: 92vw;
      background: #0f1116; border: 1px solid rgba(255,255,255,.08);
      border-radius: 14px; box-shadow: 0 10px 30px rgba(0,0,0,.35); z-index:9999;
  }
  .chat-header { padding: 10px 14px; border-bottom: 1px solid rgba(255,255,255,.08); font-weight: 600;}
  .chat-body { padding: 10px 14px; max-height: 48vh; overflow: auto; }
  .chat-input { padding: 10px 14px; border-top: 1px solid rgba(255,255,255,.08); }
  .msg-user { background:#2b2f38; padding: 8px 10px; border-radius:10px; margin:6px 0; }
  .msg-bot  { background:#1b1f27; padding: 8px 10px; border-radius:10px; margin:6px 0; }
</style>
""", unsafe_allow_html=True)

# ----------------------------- #
#             LLM               #
# ----------------------------- #

def get_client() -> OpenAI:
    api_key = st.secrets.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        st.error("Missing OPENAI_API_KEY. Add it in Streamlit Secrets.")
        st.stop()
    return OpenAI(api_key=api_key)

@st.cache_data(show_spinner=False)
def model_name() -> str:
    # Good quality + cost: adjust anytime
    return "gpt-4o-mini"

def chat_llm(system: str, user: str) -> str:
    """Simple helper to call OpenAI Chat Completions."""
    client = get_client()
    resp = client.chat.completions.create(
        model=model_name(),
        messages=[{"role":"system","content":system},{"role":"user","content":user}],
        temperature=0.5,
    )
    return resp.choices[0].message.content.strip()

def chat_llm_json(system: str, user: str) -> Dict[str, Any]:
    """Ask model for JSON output; returns parsed dict safely."""
    client = get_client()
    resp = client.chat.completions.create(
        model=model_name(),
        response_format={"type":"json_object"},
        messages=[{"role":"system","content":system},{"role":"user","content":user}],
        temperature=0.4,
    )
    content = resp.choices[0].message.content
    try:
        return json.loads(content)
    except:
        return {"error":"Model did not return valid JSON.","raw":content}

# ----------------------------- #
#        FILE / TEXT I/O        #
# ----------------------------- #

def extract_text_from_pdf(file) -> str:
    text = []
    with pdfplumber.open(file) as pdf:
        for p in pdf.pages:
            s = p.extract_text() or ""
            if s: text.append(s)
    return "\n".join(text)

def extract_text_from_docx(file) -> str:
    if not HAS_DOCX:
        return ""
    doc = Document(file)
    return "\n".join(p.text for p in doc.paragraphs)

def get_input_text(uploaded_file, pasted: str) -> str:
    if uploaded_file is not None:
        ext = (uploaded_file.name.split(".")[-1] or "").lower()
        try:
            if ext == "pdf":
                return extract_text_from_pdf(uploaded_file)
            elif ext in ("docx","doc"):
                t = extract_text_from_docx(uploaded_file)
                if not t:
                    st.warning("DOCX reader not available; paste text instead.")
                return t
            else:  # txt or others
                return uploaded_file.read().decode("utf-8", errors="ignore")
        except Exception as e:
            st.error(f"Could not read file: {e}")
            return pasted.strip()
    return pasted.strip()

def text_size_bucket(t: str) -> str:
    n = len(t.split())
    if n < 800: return "short"
    if n < 2500: return "medium"
    return "long"

# ----------------------------- #
#      PDF DOWNLOAD HELPERS     #
# ----------------------------- #

def bytes_pdf_from_lines(title: str, lines: List[str]) -> bytes:
    """Create a simple PDF from a list of text lines — returns bytes (fixes earlier error)."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_title(title)
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, title, ln=1)
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 12)

    for line in lines:
        for wrapped in textwrap.wrap(line, width=92):
            pdf.multi_cell(0, 7, wrapped)
        pdf.ln(1)
    # IMPORTANT: return bytes, not a filename (fixes Streamlit cloud issue)
    return pdf.output(dest="S").encode("latin-1")

# ----------------------------- #
#      GENERATION FUNCTIONS     #
# ----------------------------- #

def make_summary(text: str) -> str:
    sys = "You write focused, exam-ready summaries. Avoid fluff; be clear and structured."
    user = f"""Summarize the following notes into concise bullet points with mini headings.
- Prioritize definitions, formulas, key mechanisms, timelines, theorems
- Keep it tight but COMPLETE for revision
- Use bullet points and short paragraphs

NOTES:
{text}
"""
    return chat_llm(sys, user)

def make_flashcards(text: str) -> List[Dict[str,str]]:
    sys = "You produce high-yield flashcards for spaced repetition."
    user = f"""Create flashcards in JSON with keys: question, answer.
- Use cloze/deep-recall phrasing (no trivia).
- Cover the whole topic proportionally.
NOTES:
{text}
"""
    data = chat_llm_json(sys, user)
    cards = data.get("flashcards") if isinstance(data, dict) else None
    if not cards:
        # fallback: try to parse lines
        plain = chat_llm(sys, user).split("\n")
        cards = []
        for ln in plain:
            if "—" in ln or "-" in ln:
                parts = ln.split("—") if "—" in ln else ln.split("-")
                if len(parts)>=2: cards.append({"question":parts[0].strip(), "answer":parts[1].strip()})
    # Limit sane length
    return cards[:80]

def pick_quiz_count(text: str) -> int:
    bucket = text_size_bucket(text)
    return 5 if bucket=="short" else 10 if bucket=="medium" else 15

def make_quiz(text: str, count: int) -> Dict[str, Any]:
    sys = "You generate high-quality MCQ quizzes with clear correct answers and brief explanations."
    user = f"""Create a quiz as JSON with array 'items'. Each item:
- question (string)
- options (array of 4 concise options)
- answer_index (0-3)
- explanation (string, 1-2 lines)

Number of items: {count}
Use varied coverage across the topic.
NOTES:
{text}
"""
    data = chat_llm_json(sys, user)
    return data

def make_mock_exam(text: str, difficulty: str) -> Dict[str, Any]:
    sys = "You design rigorous mock exams that sample all key ideas and provide an answer key and rubric."
    user = f"""Build a mock exam in JSON with:
- sections: array of objects with fields:
    type: one of ["MCQ","Short","Long","Problem"]
    count: number of questions
    questions: array of question text (for MCQ include 'options' and 'answer_index')
- total_marks: integer
- marking_scheme: brief explanation how marks are allocated
- answer_key: explanations/solutions

Difficulty: {difficulty.upper()}
Ensure coverage of all major subtopics. Keep it exam-like and professional.
NOTES:
{text}
"""
    return chat_llm_json(sys, user)

# ----------------------------- #
#          SESSION STATE        #
# ----------------------------- #

if "notes" not in st.session_state: st.session_state["notes"] = ""
if "quiz_user_answers" not in st.session_state: st.session_state["quiz_user_answers"] = {}
if "ask_open" not in st.session_state: st.session_state["ask_open"] = False
if "chat" not in st.session_state: st.session_state["chat"] = []  # list of dicts: {"role":"user/bot","text":...}
if "history" not in st.session_state: st.session_state["history"] = {"summaries":0,"flashcards":0,"quizzes":0,"exams":0}

# ----------------------------- #
#           SIDEBAR             #
# ----------------------------- #

with st.sidebar:
    st.markdown("### 📊 Progress")
    c1, c2 = st.columns(2)
    c1.metric("Quizzes", st.session_state["history"]["quizzes"])
    c2.metric("Mock Exams", st.session_state["history"]["exams"])

    st.markdown("### ℹ️ About Zentra")
    st.caption(
        "Zentra accelerates learning with clean summaries, active-recall flashcards, adaptive quizzes, "
        "and mock exams — plus an AI tutor. Consistency + feedback = progress."
    )

    st.markdown("### 🧭 What each tool does")
    st.markdown("- **Summaries** → exam-ready notes.")
    st.markdown("- **Flashcards** → spaced-repetition questions.")
    st.markdown("- **Quizzes** → MCQs with explanations.")
    st.markdown("- **Mock Exams** → multi-section exam with marking guide.")
    st.markdown("- **Ask Zentra** → your study tutor/chat.")

# ----------------------------- #
#             HERO              #
# ----------------------------- #

st.markdown(
    f"""
<div class="hero">
  <div style="font-size:28px; font-weight:800; margin-bottom:4px;">⚡ Zentra — AI Study Buddy</div>
  <div style="opacity:.95; margin-bottom:12px;">
    Smarter notes → better recall → higher scores. Upload or paste your notes; Zentra builds
    <b>summaries</b>, <b>flashcards</b>, <b>quizzes</b> & <b>mock exams</b> — plus a tutor you can chat with.
  </div>
  <div>
    <span class="pill" title="Turns long notes into exam-ready bullets.">Summaries</span>
    <span class="pill" title="High-yield Q→A cards for spaced repetition.">Flashcards</span>
    <span class="pill" title="MCQs with explanations; adaptive coverage.">Quizzes</span>
    <span class="pill" title="Full exam with multiple sections + marking guide.">Mock Exams</span>
    <span class="pill" title="Ask anything about your notes or topic.">Ask Zentra</span>
  </div>
</div>
""", unsafe_allow_html=True)

st.markdown("")

# ----------------------------- #
#     INPUT AREA (ALWAYS ON)    #
# ----------------------------- #

st.subheader("📥 Upload your notes (PDF / DOCX / TXT) or paste below")

left, right = st.columns([2,1])
with left:
    uploaded = st.file_uploader("Drag and drop files here", type=["pdf","docx","txt"], label_visibility="collapsed")
with right:
    analysis_mode = st.radio("Analysis mode", ["Text only", "Include images (beta)"], index=0, horizontal=True)

pasted = st.text_area("Or paste notes here…", height=150)

if st.button("Load notes", type="primary", help="Click after selecting a file or pasting text."):
    text = get_input_text(uploaded, pasted)
    if not text.strip():
        st.warning("Please upload a file or paste some notes first.")
    else:
        st.session_state["notes"] = text
        st.success("Notes loaded ✔")

notes = st.session_state["notes"]

# Helper to gate actions
def needs_notes() -> bool:
    if not notes.strip():
        st.warning("Upload or paste notes, then click **Load notes**.")
        return True
    return False

# ----------------------------- #
#        FEATURE CARDS          #
# ----------------------------- #

st.markdown("### 🔧 What do you need?")
fc1, fc2, fc3, fc4, fc5 = st.columns(5)
do_summary = fc1.button("📝 Summaries", use_container_width=True)
do_flash   = fc2.button("🔑 Flashcards", use_container_width=True)
do_quiz    = fc3.button("🎯 Quizzes", use_container_width=True)
do_exam    = fc4.button("🧪 Mock Exams", use_container_width=True)
open_ask   = fc5.button("🤖 Ask Zentra", use_container_width=True)

# ----------------------------- #
#           ACTIONS             #
# ----------------------------- #

# Summaries
if do_summary:
    if not needs_notes():
        with st.spinner("Generating summary…"):
            summary = make_summary(notes)
        st.session_state["history"]["summaries"] += 1
        st.markdown("#### ✅ Summary")
        st.markdown(summary)

        pdf_bytes = bytes_pdf_from_lines("Zentra Summary", summary.splitlines())
        st.download_button("⬇️ Download Summary (PDF)", data=pdf_bytes, file_name="summary.pdf", mime="application/pdf")

# Flashcards
if do_flash:
    if not needs_notes():
        with st.spinner("Building flashcards…"):
            cards = make_flashcards(notes)
        st.session_state["history"]["flashcards"] += 1

        st.markdown("#### ✅ Flashcards")
        for i, c in enumerate(cards, 1):
            with st.expander(f"Card {i}: {c.get('question','')}"):
                st.write(c.get("answer",""))

        # Flashcards to printable PDF (Q then A)
        lines = []
        for i, c in enumerate(cards, 1):
            lines.append(f"Card {i} — Q: {c.get('question','')}")
            lines.append(f"    A: {c.get('answer','')}\n")
        st.download_button("⬇️ Download Flashcards (PDF)", data=bytes_pdf_from_lines("Zentra Flashcards", lines),
                           file_name="flashcards.pdf", mime="application/pdf")

# Quizzes
if do_quiz:
    if not needs_notes():
        count = pick_quiz_count(notes)
        with st.spinner(f"Generating a {count}-question quiz…"):
            quiz = make_quiz(notes, count)
        items = quiz.get("items", [])

        if not items:
            st.error("Quiz generation failed. Try again.")
        else:
            st.session_state["history"]["quizzes"] += 1
            st.markdown("#### ✅ Quiz")
            answers = {}
            score = 0

            for idx, q in enumerate(items):
                st.markdown(f"**Q{idx+1}. {q['question']}**")
                choice = st.radio("", q["options"], index=None, key=f"q_{idx}", horizontal=False, label_visibility="collapsed")
                if choice is not None:
                    chosen_idx = q["options"].index(choice)
                    answers[idx] = chosen_idx
                    if chosen_idx == int(q["answer_index"]):
                        score += 1

            if st.button("Check answers"):
                total = len(items)
                st.info(f"Score: **{score}/{total}**")
                wrongs = []
                for i, q in enumerate(items):
                    chosen = answers.get(i, None)
                    if chosen is None or chosen != int(q["answer_index"]):
                        wrongs.append({"question": q["question"], "your": chosen, "correct": int(q["answer_index"]), "explanation": q.get("explanation","")})
                if wrongs:
                    st.markdown("##### ❌ Review your mistakes")
                    for w in wrongs:
                        st.markdown(f"- **{w['question']}**  \n  {w['explanation'] or 'Focus on the key concept.'}")

            # Download quiz (with answers)
            q_lines = []
            for i, q in enumerate(items, 1):
                q_lines.append(f"Q{i}. {q['question']}")
                for j, opt in enumerate(q['options']):
                    lab = chr(65+j)
                    q_lines.append(f"   {lab}. {opt}")
                ans = int(q["answer_index"])
                q_lines.append(f"Answer: {chr(65+ans)} — {q.get('explanation','')}\n")
            st.download_button("⬇️ Download Quiz (PDF)", data=bytes_pdf_from_lines("Zentra Quiz", q_lines),
                               file_name="quiz.pdf", mime="application/pdf")

# Mock Exam
if do_exam:
    if not needs_notes():
        difficulty = st.selectbox("Select difficulty", ["Easy","Standard","Difficult"], index=1)
        go = st.button("Generate Mock Exam")
        if go:
            with st.spinner(f"Preparing a {difficulty} mock exam…"):
                exam = make_mock_exam(notes, difficulty)
            st.session_state["history"]["exams"] += 1

            st.markdown("#### ✅ Mock Exam")
            sections = exam.get("sections", [])
            total = exam.get("total_marks", None)
            if total: st.caption(f"Total marks: {total}")
            for si, s in enumerate(sections, 1):
                st.markdown(f"**Section {si}: {s.get('type','')} ({s.get('count','?')} q)**")
                if s.get("type") == "MCQ":
                    for qi, q in enumerate(s.get("questions", []), 1):
                        st.write(f"Q{qi}. {q.get('question','')}")
                        opts = q.get("options", [])
                        if opts: st.write("Options: " + "; ".join(opts))
                else:
                    for qi, q in enumerate(s.get("questions", []), 1):
                        st.write(f"Q{qi}. {q}")

            if exam.get("marking_scheme"):
                with st.expander("Marking scheme"):
                    st.write(exam["marking_scheme"])
            if exam.get("answer_key"):
                with st.expander("Answer key / solutions"):
                    st.write(exam["answer_key"])

            # Download exam
            e_lines = []
            if total: e_lines.append(f"Total marks: {total}\n")
            for si, s in enumerate(sections, 1):
                e_lines.append(f"Section {si}: {s.get('type','')} ({s.get('count','?')} q)")
                for qi, q in enumerate(s.get("questions", []), 1):
                    if s.get("type") == "MCQ":
                        e_lines.append(f"  Q{qi}. {q.get('question','')}")
                        opts = q.get("options", [])
                        for j, oo in enumerate(opts):
                            e_lines.append(f"     {chr(65+j)}. {oo}")
                        ai = q.get("answer_index")
                        if ai is not None:
                            e_lines.append(f"     Ans: {chr(65+int(ai))}")
                    else:
                        e_lines.append(f"  Q{qi}. {q}")
                e_lines.append("")
            if exam.get("marking_scheme"):
                e_lines.append("Marking scheme:")
                e_lines.append(str(exam["marking_scheme"]))
            if exam.get("answer_key"):
                e_lines.append("\nAnswer key / solutions:")
                e_lines.append(str(exam["answer_key"]))
            st.download_button("⬇️ Download Mock Exam (PDF)", data=bytes_pdf_from_lines("Zentra Mock Exam", e_lines),
                               file_name="mock_exam.pdf", mime="application/pdf")

# ----------------------------- #
#        ASK ZENTRA (POPUP)     #
# ----------------------------- #

# Toggle FAB
st.markdown(f"""<div class="chat-fab" onclick="var e=document.getElementById('zentra-chat'); if(e) e.style.display=(e.style.display=='none'?'block':'none');">💬 Ask Zentra</div>""",
            unsafe_allow_html=True)

# Render chat panel (always in DOM; toggled via JS/CSS)
panel_display = "block" if st.session_state["ask_open"] else "none"
st.markdown(f"""
<div id="zentra-chat" class="chat-panel" style="display:{panel_display}">
  <div class="chat-header">🤖 Ask Zentra</div>
  <div class="chat-body" id="chat-scroll">
""", unsafe_allow_html=True)

# Dump chat history to HTML (so it feels persistent)
for msg in st.session_state["chat"]:
    cls = "msg-user" if msg["role"]=="user" else "msg-bot"
    st.markdown(f"""<div class="{cls}">{msg["text"]}</div>""", unsafe_allow_html=True)

st.markdown("""</div>""", unsafe_allow_html=True)

with st.container():
    # input inside panel
    q = st.text_input("Ask about your uploaded/pasted notes, or anything related:",
                      key="ask_input", label_visibility="collapsed",
                      placeholder="e.g., Explain this paragraph / Build a 7-day study plan…")
    colA, colB = st.columns([1,1])
    with colA:
        ask_btn = st.button("Send", key="ask_send")
    with colB:
        clear_btn = st.button("Clear", key="ask_clear")

if ask_btn:
    if not q.strip():
        st.warning("Type a question first.")
    else:
        st.session_state["chat"].append({"role":"user","text":q})
        context = notes if notes.strip() else "(No notes provided by the user.)"
        sys = "You are Zentra, a friendly but precise study tutor. Keep explanations tight and helpful."
        user = f"""User question: {q}

If relevant, use the following notes as context:
{context}
"""
        with st.spinner("Thinking…"):
            ans = chat_llm(sys, user)
        st.session_state["chat"].append({"role":"bot","text":ans})
        st.session_state["ask_open"] = True  # keep open

if clear_btn:
    st.session_state["chat"] = []
    st.session_state["ask_open"] = True

st.markdown("""</div>""", unsafe_allow_html=True)
