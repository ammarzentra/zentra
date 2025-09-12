# app.py — Zentra Pro Final Build (all fixes)

import os, io, tempfile, json, re
from typing import List, Tuple
import streamlit as st
from openai import OpenAI

# =========================
# PAGE & GLOBAL STYLES
# =========================
st.set_page_config(
    page_title="Zentra — Your Study Buddy",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
/* Hide streamlit cruft */
a[class*="viewerBadge"], div[class*="viewerBadge"], #ViewerBadgeContainer{display:none!important;}
footer{visibility:hidden;height:0}
.block-container{padding-top:0.5rem; padding-bottom:3rem; max-width:1200px;}

/* PAYWALL */
.paywall{
  background: linear-gradient(135deg,#141e30 0%,#243b55 100%);
  border-radius: 20px; padding: 48px 28px; color:#fff;
  text-align:center; margin:44px auto; max-width:760px;
  box-shadow: 0 10px 34px rgba(0,0,0,.35);
}
.paywall h1{margin:0; font-size:48px; font-weight:800; letter-spacing:.3px;}
.paywall p{margin:12px 0 20px; font-size:18px; opacity:.95;}
.features{text-align:left; margin:20px auto; display:inline-block; font-size:15px;}
.features li{margin:8px 0;}
.subscribe-btn{
  background:#0d6efd; color:#fff; padding:14px 28px;
  border-radius:12px; text-decoration:none;
  font-size:18px; font-weight:700;
  display:inline-block; transition:all .25s; border:0;
}
.subscribe-btn:hover{background:#0a58ca;}
.dev-btn .stButton>button{margin-top:12px; border-radius:10px;}

/* HERO (inside app) */
.hero{background:linear-gradient(90deg,#6a11cb 0%,#2575fc 100%);
  padding:34px 20px; border-radius:20px; color:#fff; margin:0 0 18px 0; text-align:center;}
.hero h1{margin:0;font-size:40px;font-weight:800;}
.hero p{margin:6px 0 0;opacity:.95; font-size:18px;}

/* SECTION / BUTTONS */
.section-title{font-weight:800;font-size:22px;margin:12px 0 14px;}
.tool-row .stButton>button{
  width:100%; border-radius:12px; border:1px solid #2b2f3a;
  padding:12px; background:#10141e; color:#e8ecf7; font-weight:700;
}
.tool-row .stButton>button:hover{background:#141a27; border-color:#3a4252;}

/* CHAT */
.chat-card{background:#0e1117; border:1px solid #232b3a; border-radius:14px; padding:12px;}
.chat-box{max-height:460px; overflow-y:auto; padding:10px; border-radius:12px; background:#0b1220; border:1px solid #1f2a3d;}
.chat-box p{margin:6px 0;}
.chat-head .stButton>button{width:100%;}

/* SIDEBAR */
[data-testid="stSidebar"]{
  background:linear-gradient(180deg,#0f172a,#1e293b);
  color:#e6eefc;
}
[data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3{
  color:#fff; font-weight:700;
}
.side-card{background:rgba(255,255,255,.04); padding:12px 14px; border-radius:12px; border:1px solid rgba(255,255,255,.08);}

/* Small helpers */
.helper{opacity:.8; font-size:.92rem; margin-top:-4px;}
.center-wrap{display:flex; justify-content:center;}
.upload-wrap{max-width:900px; width:100%;}
</style>
""", unsafe_allow_html=True)

# =========================
# STATE
# =========================
ss = st.session_state
if "chat_open" not in ss: ss.chat_open = False
if "messages" not in ss: ss.messages = []
if "history_quiz" not in ss: ss.history_quiz = []
if "history_mock" not in ss: ss.history_mock = []
if "notes_text" not in ss: ss.notes_text = ""
if "last_title" not in ss: ss.last_title = "Untitled notes"
if "dev_unlocked" not in ss: ss.dev_unlocked = False
if "pending_tool" not in ss: ss.pending_tool = None            # 'summary'|'cards'|'quiz'|'mock'
if "processing_choice" not in ss: ss.processing_choice = None # 'text'|'vision'
if "cached_upload_meta" not in ss: ss.cached_upload_meta = {} # {'ext':'.pdf', 'has_images':bool}

# =========================
# PAYWALL (keep temp dev login)
# =========================
if not ss.dev_unlocked:
    st.markdown(f"""
    <div class="paywall">
      <h1>⚡ Zentra — AI Study Buddy</h1>
      <p>Unlock smarter learning for just <b>$5.99/month</b></p>
      <ul class="features">
        <li>📄 Smart Summaries — exam-ready notes</li>
        <li>🧠 Flashcards — active recall Q/A (tap to reveal)</li>
        <li>🎯 Quizzes — pick answers, get scored + feedback</li>
        <li>📝 Mock Exams — graded with strengths & fixes</li>
        <li>💬 Ask Zentra — your 24/7 study tutor</li>
      </ul>
      <br>
      <a class="subscribe-btn" href="https://zentraai.lemonsqueezy.com/buy/XXXXXXXX" target="_blank">
        Subscribe Now →
      </a>
      <div class="features" style="margin-top:18px;">
        <b>How Zentra Helps You</b>
        <ul>
          <li>Builds custom summaries & flashcards from your notes</li>
          <li>Targets weak spots with adaptive quizzes</li>
          <li>Full mock exams with clear marking rubrics</li>
          <li>Actionable feedback so you improve each attempt</li>
        </ul>
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()
    colA, colB, colC = st.columns([1,1,1])
    with colB:
        if st.button("🚪 Temporary Dev Login (for testing)"):
            ss.dev_unlocked = True
            st.rerun()
    st.stop()

# =========================
# OPENAI
# =========================
def _client() -> OpenAI:
    key = st.secrets.get("OPENAI_API_KEY")
    if not key:
        st.error("Missing OPENAI_API_KEY in Streamlit Secrets.")
        st.stop()
    os.environ["OPENAI_API_KEY"] = key
    return OpenAI()

MODEL = "gpt-4o-mini"

def ask_llm(prompt: str, system="You are Zentra — precise, supportive, never make personal assumptions. Only use user notes if explicitly helpful. Be concise and clear."):
    r = _client().chat.completions.create(
        model=MODEL,
        messages=[{"role":"system","content":system},{"role":"user","content":prompt}],
        temperature=0.4,
    )
    return r.choices[0].message.content.strip()

# =========================
# FILE HANDLING
# =========================
def read_file(uploaded) -> Tuple[str, List[Tuple[str, bytes]]]:
    if not uploaded: return "", []
    name = uploaded.name.lower()
    data = uploaded.read()
    text, images = "", []
    if name.endswith(".txt"):
        text = data.decode("utf-8","ignore")
    elif name.endswith(".pdf"):
        # Extract text only; note: image-only PDFs will be blank.
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data))
            text = "\n".join([(p.extract_text() or "") for p in reader.pages])
        except Exception:
            text = ""
        # We cannot rasterize PDF pages without extra deps; warn user at use time.
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
        text = data.decode("utf-8","ignore")
    # cache some meta so we can ask processing choice smartly
    ss.cached_upload_meta = {
        "ext": os.path.splitext(name)[1],
        "has_images": name.endswith((".png",".jpg",".jpeg"))
    }
    return (text or "").strip(), images

def ensure_notes(pasted, uploaded):
    txt = (pasted or "").strip()
    imgs: List[Tuple[str, bytes]] = []
    if uploaded:
        t, ii = read_file(uploaded)
        if t: txt = (txt + "\n" + t).strip() if txt else t
        if ii: imgs = ii
        ss.last_title = uploaded.name
    if len(txt) < 5 and not imgs:
        st.warning("Your notes look empty. Paste text or upload a readable PDF/DOCX. (Image-only PDFs require the **Text + Images/Diagrams** option.)")
        st.stop()
    ss.notes_text = txt
    return txt, imgs

def adaptive_quiz_count(txt: str) -> int:
    return max(5, min(20, len(txt.split()) // 180))

# =========================
# SIDEBAR (clean & collapsible)
# =========================
with st.sidebar:
    st.markdown("## 🌟 Zentra Toolkit")
    with st.expander("How Zentra helps you", expanded=True):
        st.markdown(
            "- Turn notes into **summaries** & **flashcards**\n"
            "- Drill with **quizzes** and get instant **feedback**\n"
            "- Sit **mock exams** with grading & tips\n"
            "- **Ask Zentra** anything, anytime"
        )
    st.markdown("### 📂 History")
    with st.container():
        st.markdown("<div class='side-card'>", unsafe_allow_html=True)
        st.caption("Recent Quizzes")
        if ss.history_quiz: st.write(ss.history_quiz[-6:][::-1])
        else: st.write("—")
        st.caption("Recent Mock Exams")
        if ss.history_mock: st.write(ss.history_mock[-6:][::-1])
        else: st.write("—")
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("---")
    st.caption("⚠️ AI-generated help. Verify before exams.")

# =========================
# HERO
# =========================
st.markdown('<div class="hero"><h1>⚡ Zentra — Your Study Buddy</h1><p>Smarter notes → Better recall → Higher scores.</p></div>', unsafe_allow_html=True)

# =========================
# MAIN LAYOUT
# =========================
col_main, col_chat = st.columns([3, 1.4], gap="large")

# ---------- Helpers for the processing choice flow ----------
def needs_processing_choice(uploaded_present: bool) -> bool:
    """Only ask when a file is uploaded (pdf/docx/img). If only pasted text, skip."""
    if not uploaded_present: 
        return False
    ext = ss.cached_upload_meta.get("ext", "")
    # For pdf/docx/images we show the choice
    return ext in [".pdf", ".docx", ".png", ".jpg", ".jpeg"]

def render_processing_gate():
    st.markdown("#### Choose how to process this file")
    choice = st.radio(
        "Use notes as:",
        ["Text only", "Text + Images/Diagrams (beta)"],
        horizontal=True,
        index=0
    )
    colA, colB = st.columns([1,1])
    proceed = colA.button("Continue", type="primary")
    cancel = colB.button("Cancel")
    if proceed:
        ss.processing_choice = "vision" if "Images" in choice else "text"
        return True
    if cancel:
        ss.pending_tool = None
        ss.processing_choice = None
        st.experimental_rerun()
    return False

# ---------- Main column ----------
with col_main:
    # Upload section centered & bigger
    st.markdown('<div class="section-title">📁 Upload Your Notes</div>', unsafe_allow_html=True)
    st.markdown('<div class="center-wrap"><div class="upload-wrap">', unsafe_allow_html=True)
    cu, cm = st.columns([3,2], vertical_alignment="bottom")
    with cu:
        uploaded = st.file_uploader("Upload a file", type=["pdf","docx","txt","png","jpg","jpeg"], label_visibility="collapsed")
        pasted = st.text_area("Paste your notes here…", height=180, label_visibility="collapsed")
    with cm:
        st.markdown("<div class='helper'>Tip: You can paste plain notes or upload a file.</div>", unsafe_allow_html=True)
    st.markdown('</div></div>', unsafe_allow_html=True)

    # Tools
    st.markdown('<div class="section-title">✨ Study Tools</div>', unsafe_allow_html=True)
    st.markdown('<div class="tool-row">', unsafe_allow_html=True)
    c1, c2, c3, c4, c5 = st.columns(5)
    go_summary = c1.button("📄 Summaries", help="Exam-ready bullets from your notes")
    go_cards   = c2.button("🧠 Flashcards", help="Active recall Q/A — tap to reveal answers")
    go_quiz    = c3.button("🎯 Quizzes", help="Pick options, get scored + explanations")
    go_mock    = c4.button("📝 Mock Exams", help="Full exam: MCQ, short, long, fill. Graded.")
    open_chat  = c5.button("💬 Ask Zentra", help="Tutor chat — clear, focused explanations")
    st.markdown('</div>', unsafe_allow_html=True)

    # Open chat side
    if open_chat:
        ss.chat_open = True
        st.experimental_rerun()

    # Place to render outputs
    out_area = st.container()

    # ---------- Core Generators ----------
    def gen_summary(txt, use_vision=False, images: List[Tuple[str,bytes]] = None):
        # We don't have robust vision OCR here; text governs. (Images used if provided jpg/png.)
        prompt = f"""Summarize the notes into clear, exam-ready bullet points.
Prioritize definitions, laws, formulas, steps, and key facts. Keep bullets crisp.
Notes:
{txt}"""
        return ask_llm(prompt)

    def gen_flashcards(txt):
        prompt = f"""Create high-quality flashcards from the notes.
Return as bullet lines with **Q:** and **A:** pairs. Keep one concept per card.
Notes:
{txt}"""
        return ask_llm(prompt)

    def gen_quiz(txt, n):
        prompt = f"""Create {n} multiple-choice questions (A–D) from the notes.
After listing all questions, give an **Answer Key** section with the correct letters and 1–2 line explanations per question.
Format plainly in Markdown.

Notes:
{txt}"""
        return ask_llm(prompt)

    def gen_mock(txt, diff):
        prompt = f"""Create a **{diff}** mock exam from these notes with sections:
1) 5 MCQs (A–D)
2) 2 Short-answer
3) 1 Long-answer
4) 2 Fill-in-the-blank
Include a concise **Mark scheme** at the end for all questions.

Notes:
{txt}"""
        return ask_llm(prompt)

    # ---------- Renderers (Interactive) ----------
    def render_flashcards(markdown_cards: str):
        # Parse simple Q/A lines
        pairs = []
        for line in markdown_cards.splitlines():
            if line.strip().startswith("**Q:**"):
                q = line.split("**Q:**",1)[1].strip()
                pairs.append({"q": q, "a": ""})
            elif line.strip().startswith("**A:**") and pairs:
                a = line.split("**A:**",1)[1].strip()
                pairs[-1]["a"] = a

        st.subheader("🧠 Flashcards")
        if not pairs:
            st.markdown(markdown_cards)
            return
        for i, card in enumerate(pairs, 1):
            with st.expander(f"Q{i}: {card['q']}"):
                st.markdown(f"**Answer:** {card['a'] or '_(not provided)_'}")

    def render_quiz_interactive(quiz_md: str, notes_txt: str):
        st.subheader("🎯 Quiz")
        st.markdown(quiz_md)

        # Try to detect number of questions from "Q1.", "1)", etc.
        q_count = max(5, min(20, len(re.findall(r'\n\s*(?:Q\s*)?(\d+)[\.\)]', quiz_md)) or [10][-1]))
        # Build radios
        answers = []
        for i in range(1, q_count+1):
            answers.append(st.radio(f"Your answer for Q{i}", ["A","B","C","D"], horizontal=True, key=f"quiz_ans_{i}"))

        if st.button("Submit Quiz"):
            # Let model grade based on the quiz text + user choices
            grading = ask_llm(
                f"""You are Zentra. Grade this MCQ quiz.
Provide:
- Total score (0–100)
- Per-question: correct letter, user's letter, correct/incorrect, brief explanation
- Final tips to improve

QUIZ:
{quiz_md}

USER CHOICES:
{[a for a in answers]}

NOTES (context, optional):
{notes_txt}"""
            )
            st.success("✅ Quiz graded")
            st.markdown(grading)
            ss.history_quiz.append(ss.last_title or "Untitled Quiz")

    def render_mock_interactive(mock_md: str, notes_txt: str):
        st.subheader("📝 Mock Exam")
        st.markdown(mock_md)

        with st.form("mock_form"):
            st.caption("Answer below and submit for grading.")

            # Assume 5 MCQs:
            mcq = [st.radio(f"MCQ {i+1}", ["A","B","C","D"], horizontal=True, key=f"mock_mcq_{i}") for i in range(5)]
            short = [st.text_area(f"Short Answer {i+1}", key=f"mock_short_{i}") for i in range(2)]
            long_ans = st.text_area("Long Answer (Essay)", key="mock_long")
            fill = [st.text_input(f"Fill in {i+1}", key=f"mock_fill_{i}") for i in range(2)]

            submitted = st.form_submit_button("Submit Mock")
            if submitted:
                # Grade with nearest 10 between 10..100
                grading = ask_llm(
                    f"""You are Zentra. Grade this mock **fairly**.
Score rule: choose a total out of 100, rounded to nearest 10 (10,20,...,100).
Return:
- Total score (/100, rounded to nearest 10)
- Section breakdown (MCQ/Short/Long/Fill)
- Strengths
- Weaknesses
- Exact corrections for wrong/incomplete answers
- Targeted tips for next attempt

MOCK PAPER:
{mock_md}

STUDENT ANSWERS:
MCQ: {mcq}
Short: {short}
Long: {long_ans}
Fill: {fill}

NOTES (context, optional):
{notes_txt}"""
                )
                st.success("✅ Mock graded")
                st.markdown(grading)
                ss.history_mock.append(ss.last_title or "Untitled Mock")

    # ---------- Orchestration with processing choice ----------
    def start_tool(tool_name: str):
        """Entry point when user clicks a tool button."""
        ss.pending_tool = tool_name
        ss.processing_choice = None
        st.experimental_rerun()

    # Button clicks → set pending tool
    if go_summary: start_tool("summary")
    if go_cards:   start_tool("cards")
    if go_quiz:    start_tool("quiz")
    if go_mock:    start_tool("mock")

    # If any tool is pending, ensure we have notes and (maybe) ask processing choice
    if ss.pending_tool:
        text, images = ensure_notes(pasted, uploaded)
        uploaded_present = bool(uploaded)
        # Ask choice only when a file was uploaded (PDF/DOCX/IMG). Pasted-only skips.
        if needs_processing_choice(uploaded_present) and ss.processing_choice is None:
            # Show choice GATE here — only once per click, before generating anything
            done = render_processing_gate()
            if not done:
                st.stop()
            # else continue below with ss.processing_choice set

        use_vision = (ss.processing_choice == "vision")

        # Now run the right tool
        if ss.pending_tool == "summary":
            with st.spinner("Generating summary…"):
                out = gen_summary(text, use_vision, images if use_vision else None)
            out_area.subheader("✅ Summary")
            out_area.markdown(out or "_(empty)_")
            ss.pending_tool, ss.processing_choice = None, None

        elif ss.pending_tool == "cards":
            with st.spinner("Creating flashcards…"):
                cards_md = gen_flashcards(text)
            render_flashcards(cards_md)
            ss.pending_tool, ss.processing_choice = None, None

        elif ss.pending_tool == "quiz":
            n = adaptive_quiz_count(text)
            with st.spinner("Building quiz…"):
                quiz_md = gen_quiz(text, n)
            render_quiz_interactive(quiz_md, text)
            ss.pending_tool, ss.processing_choice = None, None

        elif ss.pending_tool == "mock":
            st.markdown("#### Select difficulty")
            diff = st.radio("", ["Easy","Standard","Hard"], horizontal=True, key="mock_diff_choice")
            if st.button("Start Mock", type="primary"):
                with st.spinner("Composing mock exam…"):
                    mock_md = gen_mock(text, diff)
                render_mock_interactive(mock_md, text)
                ss.pending_tool, ss.processing_choice = None, None

# =========================
# CHAT — Ask Zentra (no empty spacer, auto-scroll, close/clear)
# =========================
with col_chat:
    if ss.chat_open:
        st.markdown("### 💬 Ask Zentra")
        c1, c2 = st.columns(2)
        if c1.button("Close", use_container_width=True):
            ss.chat_open = False
            st.experimental_rerun()
        if c2.button("Clear", use_container_width=True):
            ss.messages = []
            st.experimental_rerun()

        # Render chat history inside a scrollable box
        chat_html = "<div class='chat-box' id='chat-box'>"
        for m in ss.messages:
            who = "🧑‍🎓 You" if m["role"] == "user" else "🤖 Zentra"
            chat_html += f"<p><b>{who}:</b> {m['content']}</p>"
        chat_html += "</div><script>var box=document.getElementById('chat-box'); if(box){box.scrollTop=box.scrollHeight;}</script>"
        st.markdown(chat_html, unsafe_allow_html=True)

        q = st.chat_input("Ask Zentra…")
        if q:
            ss.messages.append({"role": "user", "content": q})
            # Focus, no random personal context; use notes only when helpful
            reply = ask_llm(
                f"""You are Zentra, a focused tutor. Do not mention unrelated personal details.
Use the user's notes **only if** it helps answer their question; otherwise keep it general but precise.

NOTES (may be empty):
{ss.notes_text}

QUESTION:
{q}
"""
            )
            ss.messages.append({"role": "assistant", "content": reply})
            st.experimental_rerun()
