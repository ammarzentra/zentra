import os, io, base64, datetime
from typing import List, Tuple
import streamlit as st

# OpenAI SDK (v1+)
from openai import OpenAI

# File parsing
from pypdf import PdfReader
import docx  # python-docx

# ----------------- CONFIG -----------------
st.set_page_config(page_title="Zentra — AI Study Buddy", page_icon="⚡", layout="wide")

# Secrets / Client
API_KEY = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
if not API_KEY:
    st.warning("Add your OpenAI key in Streamlit Secrets as OPENAI_API_KEY.")
client = OpenAI(api_key=API_KEY)

TEXT_MODEL   = "gpt-4o-mini"
VISION_MODEL = "gpt-4o-mini"  # lightweight vision

# ----------------- STYLE (NO STREAMLIT BADGES) -----------------
st.markdown("""
<style>
/* Kill Streamlit chrome + mobile badges */
#MainMenu, footer, header {visibility: hidden;}
div[data-testid="stToolbar"]{display:none!important;}
div[data-testid="stDecoration"]{display:none!important;}
div[data-testid="stStatusWidget"]{display:none!important;}
.stAppDeployButton{display:none!important;}
[class*="viewerBadge"]{display:none!important;}

/* Theme */
:root {
  --purple:#6e37ff; --blue:#00a4ff; --card:#0f1420; --muted:#161b28;
  --text:#ecf1f8; --sub:#a9b5c8; --accent:#ffd166;
}
html, body, [class*="css"]{ color:var(--text); }
.block-container{ padding-top:1.0rem; }

/* Hero */
.z-hero{
  padding:26px 24px; border-radius:18px;
  background:linear-gradient(135deg,var(--purple),var(--blue));
  box-shadow:0 14px 44px rgba(20,22,35,.35); color:#fff; margin-bottom:16px;
}
.z-hero h1{ font-size:40px; margin:0 0 6px 0; line-height:1.1; font-weight:900; }
.z-hero p{ margin:0; opacity:.96; }

/* Upload line hint */
.z-hint{ color:var(--sub); font-size:12px; margin-top:6px; }

/* Card */
.z-card{ background:var(--card); border:1px solid #20283b; border-radius:14px; padding:14px; }

/* Buttons row */
.stButton>button{ width:100%; border-radius:10px; font-weight:700; padding:12px; }
.btn-summary{ background:#181f30; border:1px solid #27314a; }
.btn-cards{ background:#181f30; border:1px solid #27314a; }
.btn-quiz{ background:#181f30; border:1px solid #27314a; }
.btn-mock{ background:#181f30; border:1px solid #27314a; }

/* Floating Ask bubble (top-right) */
.z-ask{
  position:fixed; top:12px; right:14px; z-index:9998;
  background:var(--accent); color:#111; padding:10px 14px; border-radius:999px;
  font-weight:800; box-shadow:0 10px 28px rgba(0,0,0,.3);
}
.z-ask a{ color:#111; text-decoration:none; }

/* Chat popup (closable) */
.z-chat{
  position:fixed; right:16px; bottom:18px; z-index:9999; width:min(420px,92vw);
  background:#0b1018; border:1px solid #1f2a3f; border-radius:14px;
  box-shadow:0 20px 60px rgba(0,0,0,.6);
}
.z-chat .hd{ display:flex; align-items:center; justify-content:space-between; padding:10px 12px; border-bottom:1px solid #1c2637; }
.z-chat .hd b{ font-size:16px; }
.z-chat .inner{ max-height:52vh; overflow:auto; padding:10px; }
.z-msg{ margin:6px 0; padding:10px 12px; border-radius:12px; font-size:14px; line-height:1.45; }
.z-user{ background:#16233a; }
.z-ai{ background:#111a25; }
.z-chat .ft{ padding:8px 10px; border-top:1px solid #1c2637; }

/* Sidebar polish */
section[data-testid="stSidebar"]{ width:320px !important; }
.z-side h4{ margin:0 0 6px 0; }
.z-side p, .z-side li, .z-side small{ color:var(--sub); }

/* Footer brand */
.z-foot{
  text-align:center; color:#7f8aa3; font-size:12px; margin-top:16px; opacity:.9;
}
</style>
""", unsafe_allow_html=True)

# ----------------- SIDEBAR -----------------
if "history" not in st.session_state:
    st.session_state.history = {"quizzes": [], "mocks": []}  # list of dicts

with st.sidebar:
    st.markdown('<div class="z-side">', unsafe_allow_html=True)
    st.markdown("### 📘 About Zentra")
    st.write("Zentra turns your notes into **summaries**, **flashcards**, **quizzes**, and **mock exams**, plus an on-demand **AI tutor**. Smarter practice → better recall → higher scores.")

    st.markdown("### 🧰 What each tool does")
    st.markdown("- **Summaries** → exam-ready bullet points")
    st.markdown("- **Flashcards** → spaced-recall prompts covering all key points")
    st.markdown("- **Quizzes** → AI-chosen number of MCQs to test core concepts")
    st.markdown("- **Mock Exams** → multi-section exam with marking & rubric")
    st.caption("Tip: Hover tool buttons for one-line hints.")

    st.markdown("### 🧪 Mock Exam Evaluation")
    st.write(
        "Zentra sizes total marks by content length (10→100). Sections include MCQs, "
        "short and long answers, and fill-in-the-blanks. A **marking scheme & rubric** "
        "explain how to score and improve."
    )

    st.markdown("### 🧾 History")
    if st.session_state.history["quizzes"] or st.session_state.history["mocks"]:
        if st.session_state.history["quizzes"]:
            st.write("**Quizzes**")
            for q in st.session_state.history["quizzes"][-8:][::-1]:
                st.caption(f"• {q['ts']} — ~{q['n_questions']} Qs (auto)")
        if st.session_state.history["mocks"]:
            st.write("**Mock Exams**")
            for m in st.session_state.history["mocks"][-8:][::-1]:
                st.caption(f"• {m['ts']} — {m['difficulty']} — Total {m['total_marks']} marks")
    else:
        st.caption("No attempts yet. Generate a quiz or mock to see history.")

    st.markdown("### ⚠️ Disclaimer")
    st.write("Zentra is an AI study assistant. Always verify outputs and follow your course rules.")
    st.markdown('</div>', unsafe_allow_html=True)

# ----------------- FLOATING ASK ZENTRA -----------------
# Use query params to open/close without JS hacks
qp = st.experimental_get_query_params()
chat_open = qp.get("chat", ["close"])[0] == "open"

ask_tip = "Ask Zentra anything — from any subject. Get clear explanations, study plans, and answers tailored just for you."
st.markdown(
    f'<div class="z-ask" title="{ask_tip}"><a href="?chat=open#chat">💬 Ask Zentra</a></div>',
    unsafe_allow_html=True,
)

# ----------------- HEADER -----------------
st.markdown("""
<div class="z-hero">
  <h1>⚡ Zentra — AI Study Buddy</h1>
  <p>Smarter notes → Better recall → Higher scores.</p>
</div>
""", unsafe_allow_html=True)

# First-time welcome
if "welcomed" not in st.session_state:
    st.info("👋 Welcome to Zentra! Upload your notes and let AI transform them into study material.")
    st.session_state.welcomed = True

# ----------------- UPLOAD -----------------
st.markdown("### 📂 Upload your notes")
u1, u2 = st.columns([4,2])
with u1:
    uploads = st.file_uploader("Upload", type=["pdf","docx","txt","png","jpg","jpeg"],
                               accept_multiple_files=True, label_visibility="collapsed")
    st.caption("*(Supports PDF, DOCX, TXT — and images if you enable Vision)*")
with u2:
    mode = st.radio("Analysis mode", ["Text only","Include images (Vision)"], index=0, horizontal=True)

# Also allow pasted text
raw_text = st.text_area("Or paste your notes here…", height=160, label_visibility="collapsed")

# ----------------- EXTRACTORS -----------------
def read_pdf(file) -> str:
    try:
        data = file.getvalue()
        reader = PdfReader(io.BytesIO(data))
        parts = []
        for p in reader.pages:
            try:
                parts.append(p.extract_text() or "")
            except Exception:
                parts.append("")
        return "\n".join(parts)
    except Exception:
        return ""

def read_docx(file) -> str:
    try:
        data = file.getvalue()
        bio = io.BytesIO(data)
        document = docx.Document(bio)
        return "\n".join([para.text for para in document.paragraphs])
    except Exception:
        return ""

def read_txt(file) -> str:
    try:
        return file.read().decode("utf-8", errors="ignore")
    except Exception:
        try:
            file.seek(0)
            return file.read().decode("latin-1", errors="ignore")
        except Exception:
            return ""

def collect_text_and_images(files) -> Tuple[str, List[str]]:
    text_chunks, imgs = [], []
    if not files: return "", []
    for f in files:
        name = (f.name or "").lower()
        try:
            if name.endswith(".pdf"):
                text_chunks.append(read_pdf(f))
            elif name.endswith(".docx"):
                text_chunks.append(read_docx(f))
            elif name.endswith(".txt"):
                text_chunks.append(read_txt(f))
            elif name.endswith((".png",".jpg",".jpeg")) and mode.startswith("Include"):
                b = f.getvalue()
                b64 = base64.b64encode(b).decode("utf-8")
                mime = "image/png" if name.endswith(".png") else "image/jpeg"
                imgs.append(f"data:{mime};base64,{b64}")
        except Exception:
            # never crash the app on a single bad file
            pass
    return "\n".join([t for t in text_chunks if t.strip()]), imgs

uploaded_text, uploaded_imgs = collect_text_and_images(uploads)
full_text = "\n".join([t for t in [uploaded_text, raw_text] if t and t.strip()])

# ----------------- AI HELPERS -----------------
def ask_openai(prompt: str, images: List[str] = None, temperature: float = 0.25) -> str:
    try:
        if images and mode.startswith("Include"):
            content = [{"type":"text","text": prompt}]
            for d in images[:8]:
                content.append({"type":"image_url","image_url":{"url": d}})
            resp = client.chat.completions.create(
                model=VISION_MODEL,
                messages=[{"role":"user","content": content}],
                temperature=temperature,
            )
        else:
            resp = client.chat.completions.create(
                model=TEXT_MODEL,
                messages=[{"role":"user","content": prompt}],
                temperature=temperature,
            )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"⚠️ Error: {e}"

def word_count(s: str) -> int:
    return max(1, len(s.split()))

def ai_counts_hint(w: int) -> Tuple[int,int]:
    # hint sizes (AI still decides contents)
    if w < 400:   return (10, 6)   # flashcards, quiz
    if w < 1200:  return (16, 12)
    if w < 2500:  return (24, 18)
    return (36, 24)

def need_notes() -> bool:
    if not full_text.strip() and not uploaded_imgs:
        st.warning("Upload a file or paste notes first.", icon="⚠️")
        return True
    return False

# ----------------- TOOLS UI -----------------
st.markdown("### ✨ Study Tools")
t1, t2, t3, t4 = st.columns(4)

# Summaries
with t1:
    gen_summary = st.button("📑 Summaries", help="Turn your notes into exam-ready bullet points", type="primary")
# Flashcards
with t2:
    gen_cards = st.button("🃏 Flashcards", help="Spaced-recall prompts covering all key ideas", type="primary")
# Quizzes
with t3:
    gen_quiz = st.button("🎯 Quizzes", help="AI decides how many MCQs you need", type="primary")
# Mock Exams (difficulty shows only after tap)
with t4:
    open_mock = st.button("📝 Mock Exams", help="Full multi-section exam + marking", type="primary")

# ----------------- ACTIONS -----------------
if gen_summary:
    if not need_notes():
        prompt = f"""Summarize the following notes into **clear exam-ready bullet points**.
Group by topics with short headers; cover *all* major points and definitions.
Be concise but complete. Include key formulas/dates if present.

NOTES:
{full_text[:18000]}"""
        st.subheader("📌 Summary")
        st.write(ask_openai(prompt, uploaded_imgs))

if gen_cards:
    if not need_notes():
        w = word_count(full_text)
        n_cards, _ = ai_counts_hint(w)
        prompt = f"""Create ~{n_cards} **flashcards** that cover all essential knowledge.
Mix definitions, conceptual why/how, compare/contrast, and applied examples.
Format as:
1) Q: ...
   A: ...
2) Q: ...
   A: ...
Use the notes below:

{full_text[:18000]}"""
        st.subheader("🧠 Flashcards")
        st.write(ask_openai(prompt, uploaded_imgs))

if gen_quiz:
    if not need_notes():
        w = word_count(full_text)
        _, n_q = ai_counts_hint(w)  # hint only; AI can adjust
        prompt = f"""Generate an **adaptive multiple-choice quiz** that fully tests key concepts.
You decide the appropriate number of questions (typical range {max(6, n_q-4)}–{n_q+6}).
Each item: 1 correct answer + 3 plausible distractors.
Vary difficulty and rotate stems (conceptual, application, scenario).
After the questions, include an **Answer Key with concise explanations**.

NOTES:
{full_text[:18000]}"""
        st.subheader("🎯 Quiz")
        quiz_text = ask_openai(prompt, uploaded_imgs)
        st.write(quiz_text)
        # Track sidebar history (approx count if we can estimate)
        approx_qs = 0
        for line in quiz_text.splitlines():
            if line.strip().startswith(("1)","1.","Q1","Q 1")):
                approx_qs = max(approx_qs, 1)
                break
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        st.session_state.history["quizzes"].append({"ts": ts, "n_questions": "auto"})

if open_mock:
    if not need_notes():
        st.info("Choose difficulty level for your mock exam.")
        dcol1, dcol2, dcol3 = st.columns(3)
        with dcol1: d_easy = st.button("Easy")
        with dcol2: d_med  = st.button("Medium")
        with dcol3: d_hard = st.button("Hard")

        chosen = "Medium"
        if d_easy: chosen = "Easy"
        if d_med:  chosen = "Medium"
        if d_hard: chosen = "Hard"

        if d_easy or d_med or d_hard:
            w = word_count(full_text)
            total = 20 if w < 600 else 40 if w < 1500 else 70 if w < 3000 else 100
            prompt = f"""Create a **professional mock exam** with difficulty = {chosen}.
Auto-size to the notes (total marks ~{total}). Include sections:
- MCQs (1 mark each)
- Short-answer (3–5 lines each)
- Long-answer (analytical/essay)
- Fill-in-the-blanks (core facts/terms)

Provide:
1) The full exam paper grouped by sections.
2) A **marking scheme** and **rubric** describing how to grade.
3) Topic coverage summary and common pitfalls.

NOTES:
{full_text[:18000]}"""
            st.subheader(f"📝 Mock Exam — {chosen}")
            exam = ask_openai(prompt, uploaded_imgs)
            st.write(exam)
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            st.session_state.history["mocks"].append({"ts": ts, "difficulty": chosen, "total_marks": total})

# ----------------- ASK ZENTRA POPUP -----------------
# Open popup if ?chat=open
if chat_open:
    st.markdown('<div id="chat"></div>', unsafe_allow_html=True)
    if "chat_log" not in st.session_state:
        st.session_state.chat_log = [("ai","Hi! I’m Zentra. Ask me anything about your notes or any subject.")]

    st.markdown('<div class="z-chat">', unsafe_allow_html=True)
    st.markdown('<div class="hd"><b>💬 Ask Zentra</b> <a href="?chat=close" style="text-decoration:none;color:#9fb3d9;">✖</a></div>', unsafe_allow_html=True)
    st.markdown('<div class="inner">', unsafe_allow_html=True)
    for role, msg in st.session_state.chat_log[-22:]:
        cls = "z-user" if role=="user" else "z-ai"
        st.markdown(f'<div class="z-msg {cls}">{msg}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    with st.form("zentra_chat", clear_on_submit=True):
        user_q = st.text_input("Type your question", label_visibility="collapsed")
        send = st.form_submit_button("Send")
    if send and user_q.strip():
        st.session_state.chat_log.append(("user", user_q.strip()))
        # Include context snippet from current notes
        context = f"\n\nCONTEXT (excerpt from notes):\n{full_text[:3000]}" if full_text.strip() else ""
        reply = ask_openai(
            f"You are Zentra, a precise, friendly tutor. Explain clearly with steps and examples when helpful."
            f"{context}\n\nUSER: {user_q.strip()}"
        )
        st.session_state.chat_log.append(("ai", reply))
        st.experimental_set_query_params(chat="open")  # keep open on rerun
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# ----------------- FOOTER BRAND -----------------
st.markdown('<div class="z-foot">Powered by Zentra AI</div>', unsafe_allow_html=True)
