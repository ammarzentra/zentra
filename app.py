# app.py — Zentra (final, polished; full features; temp trial access)

import os, io, base64, tempfile
from typing import List, Tuple
import streamlit as st
from openai import OpenAI

# ---------- PAGE CONFIG ----------
st.set_page_config(
    page_title="Zentra — AI Study Buddy",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------- GLOBAL STYLES ----------
st.markdown("""
<style>
/* hide streamlit cruft */
a[class*="viewerBadge"], div[class*="viewerBadge"], #ViewerBadgeContainer{display:none!important;}
footer{visibility:hidden;height:0}
/* layout */
.block-container{padding-top:0.75rem; padding-bottom:3rem; max-width:1200px;}
/* HERO */
.hero{
  position:relative;
  background: radial-gradient(1200px 400px at 30% -10%, #7b2ff7 0%, rgba(123,47,247,0) 60%),
              linear-gradient(90deg, #6a11cb 0%, #2575fc 100%);
  border-radius: 18px; padding: 38px 28px; color:#fff; overflow:hidden;
  text-align:center; margin-bottom: 8px;
}
.hero h1{margin:0; font-size: 44px; line-height:1.15; font-weight:800; letter-spacing:.2px;}
.hero p{margin:8px 0 0; font-size:16px; opacity:.95;}
/* tiny top-right utility area */
.util-top{
  display:flex; gap:10px; position:absolute; top:12px; right:12px;
}
.util-btn{background:#ffffff22; backdrop-filter: blur(6px); padding:6px 10px; border-radius:9px; font-size:12px; color:#fff; border:1px solid #ffffff33;}
.util-btn:hover{background:#ffffff33;}
/* bubble card */
.bubble{
  background:#0f1420; border:1px solid #243047; color:#dbe2f1;
  border-radius:16px; padding:14px 16px; margin: 8px 0 16px;
  box-shadow: 0 8px 26px rgba(0,0,0,.25);
}
/* section title */
.section-title{font-weight:800; font-size:22px; margin: 8px 0 10px;}
/* tool buttons */
.tool-row .stButton>button{
  width:100%; border-radius:12px; border:1px solid #2b2f3a; padding:10px 12px;
  background:#10141e; color:#e8ecf7; font-weight:700;
}
.tool-row .stButton>button:hover{background:#141a27; border-color:#3a4252;}
/* chat side */
.chat-card{
  background:#0e1117; border:1px solid #232b3a; border-radius:14px; padding:12px;
}
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
if "dev_unlocked" not in st.session_state: st.session_state.dev_unlocked = False  # temp bypass toggle

# ---------- OPENAI ----------
def _client() -> OpenAI:
    key = st.secrets.get("OPENAI_API_KEY")
    if not key:
        st.error("Missing OPENAI_API_KEY in Streamlit Secrets.")
        st.stop()
    os.environ["OPENAI_API_KEY"] = key
    return OpenAI()

MODEL = "gpt-4o-mini"

def ask_llm(prompt: str, system="You are Zentra, a precise and supportive study buddy. Be concise and clear."):
    r = _client().chat.completions.create(
        model=MODEL,
        messages=[{"role":"system","content":system},{"role":"user","content":prompt}],
        temperature=0.4,
    )
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
        st.warning("Your notes look empty. Paste text or upload a readable PDF/DOCX.")
        st.stop()
    st.session_state.notes_text = txt
    return txt, imgs

def adaptive_quiz_count(txt: str) -> int:
    return max(3, min(20, len(txt.split()) // 180))

# ---------- SIDEBAR (Toolbox) ----------
with st.sidebar:
    st.markdown("## 📊 Toolbox")
    st.write("**How Zentra Works** — turn your notes into smart study tools. Consistent active recall + feedback = higher scores.")

    st.markdown("### 📌 What Zentra Offers")
    st.markdown(
        "- **Summaries** → exam-ready bullets\n"
        "- **Flashcards** → active-recall Q/A\n"
        "- **Quizzes** → MCQs + explanations (AI chooses count)\n"
        "- **Mock Exams** → graded, multi-section with evaluation\n"
        "- **Ask Zentra** → personal AI tutor"
    )

    st.markdown("### 🧪 Mock Evaluation")
    st.write(
        "Includes MCQs, short, long, and fill-in. Difficulty: *Easy / Standard / Hard*. "
        "Zentra grades responses with a marking scheme and gives **personal feedback** on weak areas + next steps."
    )

    st.markdown("### 📂 History")
    st.caption("Recent Quizzes:")
    st.write(st.session_state.history_quiz or "—")
    st.caption("Recent Mock Exams:")
    st.write(st.session_state.history_mock or "—")

    st.markdown("---")
    st.caption("Disclaimer: AI-generated. Always verify before exams.")

# ---------- HERO ----------
st.markdown("""
<div class="hero">
  <div class="util-top">
    <!-- Temporary dev-unlock so you can use the app while payments are pending -->
    <form action="#" method="post">
      <button class="util-btn" onclick="window.parent.postMessage({type:'dev_unlock'}, '*'); return false;">Start trial (temp)</button>
    </form>
  </div>
  <h1>⚡ Zentra — AI Study Buddy</h1>
  <p>Smarter notes → Better recall → Higher scores.</p>
</div>
""", unsafe_allow_html=True)

# capture dev unlock click (Streamlit workaround)
st.session_state.dev_unlocked = True if st.session_state.get("dev_unlocked") else st.session_state.dev_unlocked
# A lightweight JS hook that toggles a query param (forces rerun)
st.components.v1.html("""
<script>
window.addEventListener("message", (e)=>{
  if(e.data && e.data.type==="dev_unlock"){
    const url = new URL(window.location.href);
    url.searchParams.set("dev","1");
    window.location.href = url.toString();
  }
});
</script>
""", height=0)

if st.query_params.get("dev") == "1":
    st.session_state.dev_unlocked = True

# Bubble explainer
with st.container():
    st.markdown("""
<div class="bubble">
  <b>How Zentra Works</b><br/>
  1) Upload notes (PDF/DOCX/TXT) or paste text<br/>
  2) Generate summaries, flashcards, quizzes, or a graded mock<br/>
  3) Ask <i>Ask Zentra</i> anything — explanations, study plans, step-by-step help<br/>
  4) Track quiz/mock history in the sidebar
</div>
""", unsafe_allow_html=True)

st.info("Welcome to Zentra! Upload your notes and let AI transform them into study material.")

# ---------- MAIN LAYOUT ----------
col_main, col_chat = st.columns([3, 1.4], gap="large")

with col_main:
    # Upload
    st.markdown('<div class="section-title">📁 Upload your notes</div>', unsafe_allow_html=True)
    cu, cm = st.columns([3,2], vertical_alignment="bottom")
    with cu:
        uploaded = st.file_uploader("Drag and drop file here", type=["pdf","docx","txt","png","jpg","jpeg"], label_visibility="collapsed")
        pasted = st.text_area("Or paste your notes here…", height=150, label_visibility="collapsed")
    with cm:
        st.write("**Analysis mode**")
        mode = st.radio("", ["Text only", "Include images (Vision)"], horizontal=True, label_visibility="collapsed")
    include_images = (mode == "Include images (Vision)")

    # Study tools
    st.markdown('<div class="section-title">✨ Study Tools</div>', unsafe_allow_html=True)
    st.markdown('<div class="tool-row">', unsafe_allow_html=True)
    c1,c2,c3,c4,c5 = st.columns(5)
    go_summary = c1.button("📄 Summaries", use_container_width=True)
    go_cards   = c2.button("🧠 Flashcards", use_container_width=True)
    go_quiz    = c3.button("🎯 Quizzes",    use_container_width=True)
    go_mock    = c4.button("📝 Mock Exams", use_container_width=True)
    open_chat  = c5.button("💬 Ask Zentra", use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    if open_chat:
        st.session_state.chat_open = True
        st.rerun()

    out_area = st.container()

    # Handlers
    def do_summary(txt):
        with st.spinner("Generating summary…"):
            prompt = f"""Summarize into clear exam-ready bullet points.
Focus on definitions, laws, steps, formulas, and must-know facts. No fluff.

Notes:
{txt}"""
            out = ask_llm(prompt)
        out_area.subheader("✅ Summary"); out_area.markdown(out or "_(empty)_")

    def do_cards(txt):
        with st.spinner("Generating flashcards…"):
            prompt = f"""Make Q/A flashcards from these notes.
Return as lines:

**Q:** ...
**A:** ...

One concept per card, concise but complete.

Notes:
{txt}"""
            out = ask_llm(prompt)
        out_area.subheader("🧠 Flashcards"); out_area.markdown(out or "_(empty)_")

    def do_quiz(txt):
        with st.spinner("Building quiz…"):
            n = adaptive_quiz_count(txt)
            prompt = f"""Create {n} MCQs (options A–D) with the correct answer and a brief explanation after each question.
Vary difficulty and cover all key areas.

Notes:
{txt}"""
            out = ask_llm(prompt)
        st.session_state.history_quiz.append(st.session_state.last_title)
        out_area.subheader("🎯 Quiz"); out_area.markdown(out or "_(empty)_")

    def do_mock(txt, diff):
        with st.form("mock_form", clear_on_submit=False):
            st.write(f"### Mock Exam ({diff})")
            st.caption("Answer the questions below, then submit for grading.")

            # Generate mock
            prompt = f"""Create a **{diff}** mock exam with sections:
1) 5 MCQs (A–D)
2) 2 short-answer
3) 1 long-answer (essay)
4) 2 fill-in

Scale length to the content and include a brief rubric.

Notes:
{txt}"""
            raw = ask_llm(prompt)
            st.markdown(raw)

            # Response fields
            mcq_ans = [st.radio(f"MCQ {i+1}", ["A","B","C","D"]) for i in range(5)]
            short_ans = [st.text_area(f"Short Answer {i+1}") for i in range(2)]
            long_ans = st.text_area("Long Answer (Essay)")
            fill_ans = [st.text_input(f"Fill in {i+1}") for i in range(2)]

            submitted = st.form_submit_button("Submit Mock")
            if submitted:
                grading_prompt = f"""You are Zentra. Grade fairly and clearly.

STUDENT ANSWERS:
MCQs: {mcq_ans}
Short: {short_ans}
Long: {long_ans}
Fill: {fill_ans}

Use these notes to assess correctness and coverage:
{txt}

Provide:
- Overall Score (0–100)
- Section breakdown (MCQ / Short / Long / Fill-in)
- Strengths
- Weaknesses
- Specific advice + next steps
"""
                result = ask_llm(grading_prompt)
                st.success("✅ Mock Graded"); st.markdown(result)
                try:
                    headline = result.splitlines()[0]
                except:
                    headline = "Scored"
                st.session_state.history_mock.append(f"{st.session_state.last_title} — {headline}")

    # Orchestration (require notes if any tool clicked)
    if go_summary or go_cards or go_quiz or go_mock:
        text, _ = ensure_notes(pasted, uploaded)

    if go_summary: do_summary(text)
    if go_cards:   do_cards(text)
    if go_quiz:    do_quiz(text)
    if go_mock:
        st.markdown("#### Select difficulty")
        diff = st.radio("", ["Easy","Standard","Hard"], horizontal=True, key="mock_diff")
        if st.button("Start Mock", type="primary"): do_mock(text, diff)

# ---------- ASK ZENTRA (side chat) ----------
with col_chat:
    if st.session_state.chat_open:
        st.markdown("### 💬 Ask Zentra")
        with st.container():
            st.markdown('<div class="chat-card">', unsafe_allow_html=True)
            b1,b2 = st.columns(2)
            if b1.button("Clear", use_container_width=True):
                st.session_state.messages = []; st.rerun()
            if b2.button("Close", use_container_width=True):
                st.session_state.chat_open = False; st.rerun()

            if not st.session_state.messages:
                st.caption("Try: *Explain this line*, *Make a 7-day plan*, *Test me on chapter X*")

            for m in st.session_state.messages:
                with st.chat_message(m["role"]):
                    st.markdown(m["content"])

            q = st.chat_input("Type your question…")
            if q:
                st.session_state.messages.append({"role":"user","content":q})
                with st.chat_message("user"): st.markdown(q)
                try:
                    ans = ask_llm(
                        f"You are Zentra. If notes help, use them.\n\nNOTES (may be empty):\n{st.session_state.notes_text}\n\nUSER: {q}"
                    )
                except Exception as e:
                    ans = f"Error: {e}"
                st.session_state.messages.append({"role":"assistant","content":ans})
                with st.chat_message("assistant"): st.markdown(ans)
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
