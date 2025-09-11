# ---------- PAYWALL ----------
if "subscribed" not in st.session_state:
    st.session_state.subscribed = False

if not st.session_state.subscribed:
    st.markdown("## 🔒 Access Zentra")
    st.write("To use Zentra’s study tools, please subscribe below 👇")
    st.link_button("👉 Subscribe on Gumroad ($5.99/month)", "https://zentraa07.gumroad.com/l/moirk")
    st.stop()  # stop rendering until subscribed



# app.py — Zentra (final stable release)

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

# ---------- STYLES ----------
st.markdown("""
<style>
a[class*="viewerBadge"], div[class*="viewerBadge"], #ViewerBadgeContainer{display:none!important;}
footer{visibility:hidden;height:0}
.block-container{padding-top:1rem;padding-bottom:3rem;max-width:1200px;}
.hero{background:linear-gradient(90deg,#6a11cb 0%,#2575fc 100%);
padding:22px;border-radius:16px;color:#fff;margin-bottom:10px;}
.hero h1{margin:0;font-size:34px}
.hero p{margin:6px 0 0;opacity:.92}
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
        st.warning("Your notes look empty. Paste text or upload a readable PDF/DOCX.")
        st.stop()
    st.session_state.notes_text = txt
    return txt, imgs

def adaptive_quiz_count(txt: str) -> int:
    return max(3, min(20, len(txt.split()) // 180))

# ---------- SIDEBAR ----------
with st.sidebar:
    st.markdown("## 📊 Toolbox")
    st.write("**How Zentra Works**: Turns notes into smart tools for learning. Smarter notes → better recall → higher scores.")

    st.markdown("### 📌 What Zentra Offers")
    st.markdown("- **Summaries** → exam-ready bullets\n- **Flashcards** → active recall Q/A\n- **Quizzes** → MCQs + explanations (AI chooses count)\n- **Mock Exams** → graded, multi-section with evaluation\n- **Ask Zentra** → personal AI tutor")

    st.markdown("### 🧪 Mock Evaluation")
    st.write("Includes MCQs, short, long, and fill-in. Difficulty: *Easy / Standard / Hard*. Zentra grades responses with a marking scheme, then gives **personal feedback** on weak areas and how to improve.")

    st.markdown("### 📂 History")
    st.caption("Recent Quizzes:"); st.write(st.session_state.history_quiz or "—")
    st.caption("Recent Mock Exams:"); st.write(st.session_state.history_mock or "—")

    st.markdown("---")
    st.caption("Disclaimer: AI-generated. Always verify before exams.")

# ---------- HERO ----------
st.markdown('<div class="hero"><h1>⚡ Zentra — AI Study Buddy</h1><p>Smarter notes → Better recall → Higher scores.</p></div>', unsafe_allow_html=True)
st.info("Welcome to Zentra! Upload your notes and let AI transform them into study material.")

# ---------- MAIN ----------
col_main, col_chat = st.columns([3, 1.4], gap="large")

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

    # Study tools
    st.markdown("### ✨ Study Tools")
    c1,c2,c3,c4,c5 = st.columns(5)
    go_summary = c1.button("📄 Summaries")
    go_cards   = c2.button("🧠 Flashcards")
    go_quiz    = c3.button("🎯 Quizzes")
    go_mock    = c4.button("📝 Mock Exams")
    open_chat  = c5.button("💬 Ask Zentra")

    if open_chat: st.session_state.chat_open = True

    out_area = st.container()

    # Handlers
    def do_summary(txt):
        with st.spinner("Generating summary…"):
            prompt = f"Summarize into clear exam-ready bullet points.\n\nNotes:\n{txt}"
            out = ask_llm(prompt)
        out_area.subheader("✅ Summary"); out_area.markdown(out or "_(empty)_")

    def do_cards(txt):
        with st.spinner("Generating flashcards…"):
            prompt = f"Make Q/A flashcards from these notes. One concept per card.\n\nNotes:\n{txt}"
            out = ask_llm(prompt)
        out_area.subheader("🧠 Flashcards"); out_area.markdown(out or "_(empty)_")

    def do_quiz(txt):
        with st.spinner("Building quiz…"):
            n = adaptive_quiz_count(txt)
            prompt = f"Create {n} MCQs (A–D) with answers + explanations.\n\nNotes:\n{txt}"
            out = ask_llm(prompt)
        st.session_state.history_quiz.append(st.session_state.last_title)
        out_area.subheader("🎯 Quiz"); out_area.markdown(out or "_(empty)_")

    def do_mock(txt, diff):
        with st.form("mock_form", clear_on_submit=False):
            st.write(f"### Mock Exam ({diff})")
            st.caption("Answer the questions below, then submit for grading.")

            # Get mock from AI
            prompt = f"""Create a **{diff}** mock exam with:
1) 5 MCQs (A–D)
2) 2 short-answer
3) 1 long-answer
4) 2 fill-in

Return in structured markdown format."""
            raw = ask_llm(prompt + f"\n\nNotes:\n{txt}")

            st.markdown(raw)

            # Response fields
            mcq_ans = [st.radio(f"MCQ {i+1}", ["A","B","C","D"]) for i in range(5)]
            short_ans = [st.text_area(f"Short Answer {i+1}") for i in range(2)]
            long_ans = st.text_area("Long Answer (Essay)")
            fill_ans = [st.text_input(f"Fill in {i+1}") for i in range(2)]

            submitted = st.form_submit_button("Submit Mock")
            if submitted:
                grading_prompt = f"""You are Zentra. Grade fairly.

STUDENT ANSWERS:
MCQs: {mcq_ans}
Short: {short_ans}
Long: {long_ans}
Fill: {fill_ans}

Notes:\n{txt}
Provide:
- Score (0–100)
- Breakdown by section
- Strengths
- Weaknesses
- Advice to improve"""

                result = ask_llm(grading_prompt)
                st.success("✅ Mock Graded")
                st.markdown(result)

                st.session_state.history_mock.append(
                    f"{st.session_state.last_title} — {result.splitlines()[0]}"
                )

    if go_summary or go_cards or go_quiz or go_mock:
        text, _ = ensure_notes(pasted, uploaded)

    if go_summary: do_summary(text)
    if go_cards:   do_cards(text)
    if go_quiz:    do_quiz(text)
    if go_mock:
        diff = st.radio("Difficulty", ["Easy","Standard","Hard"], horizontal=True)
        if st.button("Start Mock"): do_mock(text, diff)

# ---------- ASK ZENTRA ----------
with col_chat:
    if st.session_state.chat_open:
        st.markdown("### 💬 Ask Zentra")
        if st.button("Close"): st.session_state.chat_open = False; st.rerun()
        if st.button("Clear"): st.session_state.messages = []; st.rerun()

        for m in st.session_state.messages:
            with st.chat_message(m["role"]): st.markdown(m["content"])

        q = st.chat_input("Type your question…")
        if q:
            st.session_state.messages.append({"role":"user","content":q})
            with st.chat_message("user"): st.markdown(q)
            try:
                ans = ask_llm(f"You are Zentra. Notes:\n{st.session_state.notes_text}\n\nUser: {q}")
            except Exception as e: ans = f"Error: {e}"
            st.session_state.messages.append({"role":"assistant","content":ans})
            with st.chat_message("assistant"): st.markdown(ans)
            st.rerun()
