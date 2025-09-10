# app.py  —  Zentra (polished)

import os, base64, io, json, math, textwrap
from typing import List, Tuple
import streamlit as st

# --------- OpenAI client (v1+ SDK) ----------
try:
    from openai import OpenAI
except Exception:
    st.stop()

API_KEY = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
if not API_KEY:
    st.warning("Add your OpenAI key in Streamlit Secrets as OPENAI_API_KEY.")
client = OpenAI(api_key=API_KEY)

TEXT_MODEL = "gpt-4o-mini"
VISION_MODEL = "gpt-4o-mini"

# ---------- UI STYLE / CSS ----------
st.set_page_config(page_title="Zentra — AI Study Buddy", page_icon="⚡", layout="wide")

HIDE_ST = """
<style>
/* Hide Streamlit footer + menu */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
/* Remove bottom-right 'Deploy' on some devices */
button[kind="header"] {display: none !important;}

/* App theme */
:root {
  --zentra-purple: #6e37ff;
  --zentra-blue: #00a4ff;
  --card: #101318;
  --muted: #1b1f27;
  --text: #e9edf1;
  --sub: #a7b1c2;
  --accent: #ffd166;
}
html, body, [class*="css"] { color: var(--text); }
.block-container { padding-top: 1.2rem; }

/* Hero card */
.z-hero {
  padding: 26px 24px;
  border-radius: 18px;
  background: linear-gradient(135deg, var(--zentra-purple), var(--zentra-blue));
  margin-bottom: 18px;
  color: #fff;
  box-shadow: 0 12px 40px rgba(25,25,35,.35);
}
.z-hero h1 { font-size: 40px; line-height: 1.1; margin: 0 0 10px 0; }
.z-hero p { margin: 0 0 6px 0; font-size: 16px; opacity: .95; }

/* Feature buttons row */
.z-pill { 
  display:inline-flex; align-items:center; gap:10px;
  margin: 8px 10px 0 0; padding: 10px 14px; border-radius: 12px;
  background: rgba(0,0,0,.28); color: #fff; border: 1px solid rgba(255,255,255,.25);
  cursor: pointer; user-select: none; transition: .15s all;
}
.z-pill:hover { transform: translateY(-1px); background: rgba(0,0,0,.35); }

/* Section titles */
.z-title { font-weight: 800; letter-spacing: .5px; }

/* Card */
.z-card {
  background: var(--card); border: 1px solid #232737; border-radius: 14px; padding: 16px;
}

/* Sidebar polish */
section[data-testid="stSidebar"] { width: 315px !important; }
[data-testid="stSidebar"] .sidebar-content { padding-top: 12px; }
.z-side h4 { margin: 0 0 8px 0; }
.z-side p, .z-side li, .z-side small { color: var(--sub); }

/* Floating Ask Zentra bubble (top-right) */
.z-ask-btn {
  position: fixed; top: 16px; right: 16px; z-index: 9999;
  background: var(--accent); color:#1a1a1a; font-weight: 700;
  border: none; padding: 10px 14px; border-radius: 999px; box-shadow: 0 8px 22px rgba(0,0,0,.25);
  cursor: pointer;
}
.z-chat {
  position: fixed; right: 16px; bottom: 18px; z-index: 9998; width: min(420px, 92vw);
  background: #0d1117; border: 1px solid #222a3a; border-radius: 14px; padding: 10px 10px 12px 10px;
  box-shadow: 0 18px 50px rgba(0,0,0,.5);
}
.z-chat h4 { margin: 4px 0 6px 6px; }
.z-chat .inner { max-height: 52vh; overflow:auto; padding: 8px; border-radius: 10px; background: #0a0e14; border: 1px solid #1f2734; }
.z-msg { margin: 6px 0; padding: 10px 12px; border-radius: 12px; }
.z-user { background: #16233a; }
.z-ai { background: #111921; }

/* Tool row quick buttons */
.z-quick button { margin-right: 8px; }

/* Hover tooltips (title attr) */
a[role="button"] { text-decoration: none !important; }
</style>
"""
st.markdown(HIDE_ST, unsafe_allow_html=True)

# ---------- SIDEBAR ----------
with st.sidebar:
    st.markdown("### 📊 Progress")
    c1, c2 = st.columns(2)
    c1.metric("Quizzes", st.session_state.get("q_count", 0))
    c2.metric("Mock Exams", st.session_state.get("m_count", 0))

    st.divider()
    st.markdown("### ℹ️ About Zentra", help="Why we built this")
    st.write(
        "Zentra accelerates learning with **clean summaries**, **active-recall flashcards**, "
        "**adaptive quizzes**, **mock exams**, and a built-in **AI tutor**. "
        "Consistency + feedback = progress."
    )

    st.divider()
    st.markdown("### 🧰 What each tool does")
    st.markdown("- **Summaries** → exam-ready bullet points")
    st.markdown("- **Flashcards** → spaced-repetition prompts")
    st.markdown("- **Quizzes** → MCQs that adapt to coverage & difficulty")
    st.markdown("- **Mock Exams** → multi-section test + marking guide")
    with st.expander("🧪 How mock exam evaluation works"):
        st.write(
            "We auto-size the exam by note length and weight sections. "
            "Scoring scales from 10 → 100 depending on content volume; "
            "rubrics are included so you can see where to improve."
        )

    st.divider()
    st.markdown("### 🧠 How Zentra works")
    st.write(
        "Upload notes (**PDF/DOCX/TXT**, and optionally **images**). "
        "Select **Text-only** for cheaper runs, or **Include images** to analyze figures using vision."
    )

    st.divider()
    with st.expander("⚠️ Disclaimer"):
        st.write(
            "Zentra is an AI assistant. Always verify important answers and follow your course rules."
        )

# ---------- Floating Ask Zentra toggle ----------
if "show_chat" not in st.session_state: st.session_state.show_chat = False
if "chat" not in st.session_state: st.session_state.chat = []

colA, colB, colC = st.columns([1,6,1])
with colB:
    st.markdown(
        '<button class="z-ask-btn" onclick="window.parent.postMessage({type:\'zentra_toggle_chat\'}, \'*\')">💬 Ask Zentra</button>',
        unsafe_allow_html=True,
    )

# small js to toggle Streamlit state
st.components.v1.html("""
<script>
window.addEventListener('message', (e)=>{
  if(e.data && e.data.type==='zentra_toggle_chat'){
    const s = window.parent.document.querySelector('iframe').contentWindow;
    s.postMessage({is_toggle_chat: true}, '*');
  }
});
</script>
""", height=0)

# bridge to session_state
msg = st.experimental_get_query_params()
# Cheap hack: Streamlit can't get postMessage easily; add a small button as fallback
toggle = st.button(" ", key="__hidden_toggle__", help="hidden")
if toggle: st.session_state.show_chat = not st.session_state.show_chat

# ---------- HERO ----------
st.markdown(
    """
<div class="z-hero">
  <h1>⚡ Zentra — AI Study Buddy</h1>
  <p>Smarter notes → better recall → higher scores. Upload or paste your notes; Zentra builds <b>summaries</b>, <b>flashcards</b>, <b>quizzes</b> & <b>mock exams</b> — plus a tutor you can chat with.</p>
  <div>
    <a role="button" class="z-pill" title="Turn long notes into exam-ready bullets" href="#tools">🗂️ Summaries</a>
    <a role="button" class="z-pill" title="Active-recall prompts that cover all key points" href="#tools">🧠 Flashcards</a>
    <a role="button" class="z-pill" title="MCQs that adapt to your content" href="#tools">🎯 Quizzes</a>
    <a role="button" class="z-pill" title="Multi-section exam + rubric" href="#tools">📝 Mock Exams</a>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

st.success("👋 Welcome to Zentra! Upload your notes and let AI transform them into study material.", icon="👋")

# ---------- Upload / Paste ----------
st.markdown("### 🗂️ Upload your notes (PDF / DOCX / TXT) or paste below")
uCol1, uCol2 = st.columns([3,1])
with uCol1:
    files = st.file_uploader(
        "Upload file",
        type=["pdf", "docx", "txt", "png", "jpg", "jpeg"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )
with uCol2:
    vision_mode = st.radio(
        "Analysis mode",
        ["Text only", "Include images (beta)"],
        index=0,
        horizontal=True,
        label_visibility="visible",
    )

raw_text = st.text_area("Or paste your notes here…", height=180, label_visibility="collapsed")

def read_txt(f) -> str:
    try:
        return f.read().decode("utf-8", errors="ignore")
    except Exception:
        f.seek(0)
        return f.read().decode("latin-1", errors="ignore")

def read_pdf(f) -> str:
    # robust fallback pypdf (no heavy deps)
    try:
        from pypdf import PdfReader
        reader = PdfReader(f)
        text = []
        for page in reader.pages:
            text.append(page.extract_text() or "")
        return "\n".join(text)
    except Exception:
        return ""

def read_docx(f) -> str:
    try:
        import docx2txt  # lightweight
        # docx2txt expects a path; use bytes -> temp
        data = f.read()
        bio = io.BytesIO(data)
        # workaround: save temp
        tmp = "/tmp/_docx_upload.docx"
        with open(tmp, "wb") as out: out.write(bio.getbuffer())
        return docx2txt.process(tmp) or ""
    except Exception:
        return ""

def gather_text_and_images(files) -> Tuple[str, List[str]]:
    text_chunks, img_dataurls = [], []
    if not files: return "", []
    for f in files:
        name = (f.name or "").lower()
        try:
            if name.endswith(".txt"):
                text_chunks.append(read_txt(f))
            elif name.endswith(".pdf"):
                text_chunks.append(read_pdf(f))
            elif name.endswith(".docx"):
                text_chunks.append(read_docx(f))
            elif name.endswith((".png",".jpg",".jpeg")):
                if vision_mode.startswith("Include"):
                    # convert to base64 data URL for OpenAI vision
                    bytes_data = f.read()
                    b64 = base64.b64encode(bytes_data).decode("utf-8")
                    mime = "image/png" if name.endswith(".png") else "image/jpeg"
                    img_dataurls.append(f"data:{mime};base64,{b64}")
            else:
                pass
        except Exception:
            # keep going; don't crash
            pass
    return "\n".join([c for c in text_chunks if c.strip()]), img_dataurls

uploaded_text, uploaded_images = gather_text_and_images(files)
full_text = "\n".join([t for t in [uploaded_text, raw_text] if t.strip()])

def token_hint_len(s: str) -> int:
    # rough count to guide volumes
    return max(1, len(s.split()))

def smart_counts(words: int) -> Tuple[int,int]:
    # returns (#flashcards, #quiz_qs) sized to content length
    if words < 400:
        return (8, 6)
    if words < 1200:
        return (14, 10)
    if words < 2500:
        return (22, 16)
    return (32, 24)

# ---------- OpenAI helpers ----------
def ask_openai(prompt: str, images: List[str] = None) -> str:
    """Unified call: text-only or with images (vision)"""
    try:
        if images and len(images) > 0 and vision_mode.startswith("Include"):
            content = [{"type":"text","text":prompt}]
            for durl in images[:8]:  # limit a bit
                content.append({"type":"image_url","image_url":{"url": durl}})
            resp = client.chat.completions.create(
                model=VISION_MODEL,
                messages=[{"role":"user","content": content}],
                temperature=0.3,
            )
        else:
            resp = client.chat.completions.create(
                model=TEXT_MODEL,
                messages=[{"role":"user","content": prompt}],
                temperature=0.25,
            )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"⚠️ Error: {e}"

def need_text() -> bool:
    if not full_text.strip() and not uploaded_images:
        st.warning("Upload a file or paste some notes first.", icon="⚠️")
        return True
    return False

st.markdown('<div id="tools"></div>', unsafe_allow_html=True)
st.subheader("✨ Study Tools")

# Quick action row
q = st.container()
with q:
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        do_summary = st.button("🗂️ Summaries", help="Exam-ready bullet points")
    with c2:
        do_cards = st.button("🧠 Flashcards", help="Active-recall prompts")
    with c3:
        do_quiz = st.button("🎯 Quizzes", help="Adaptive MCQs")
    with c4:
        do_mock = st.button("📝 Mock Exams", help="Multi-section exam + rubric")

# ---------- Actions ----------
if do_summary:
    if not need_text():
        prompt = f"""Summarize clearly in exam-style bullets.
Cover all major sections and sub-concepts.
Use short lines, logical grouping, and headers.
Text:
{full_text[:18000]}"""
        summary = ask_openai(prompt, uploaded_images)
        st.markdown("#### 📌 Summary")
        st.write(summary)

if do_cards:
    if not need_text():
        words = token_hint_len(full_text)
        n_cards, _ = smart_counts(words)
        prompt = f"""Create {n_cards} high-quality **flashcards** from the notes.
Mix definition, concept-explain, compare/contrast, application.
Return in numbered Q / A format.
Notes:
{full_text[:18000]}"""
        cards = ask_openai(prompt, uploaded_images)
        st.markdown("#### 🧠 Flashcards")
        st.write(cards)

if do_quiz:
    if not need_text():
        words = token_hint_len(full_text)
        _, n_q = smart_counts(words)
        prompt = f"""Build an **adaptive quiz** with {n_q} multiple-choice questions.
Each item: 1 correct + 3 plausible distractors. Vary difficulty, cover all topics.
After the list, include an **Answer Key with short explanations**.
Notes:
{full_text[:18000]}"""
        quiz = ask_openai(prompt, uploaded_images)
        st.markdown("#### 🎯 Quiz")
        st.write(quiz)
        st.session_state["q_count"] = st.session_state.get("q_count",0)+1

if do_mock:
    if not need_text():
        words = token_hint_len(full_text)
        # Scale total marks by content size
        total = 20 if words<600 else 40 if words<1500 else 70 if words<3000 else 100
        prompt = f"""Create a **mock exam** sized to the notes. Include:
- Section A: {max(5, total//5)} MCQs (1 mark each).
- Section B: {max(3, total//10)} Short-answer prompts (3–5 lines).
- Section C: {max(1, total//20)} Long-answer prompts (analytical).
Provide a **marking scheme** and **rubric** for each section.
Total marks: {total}. Balance topic coverage fairly.
Notes:
{full_text[:18000]}"""
        exam = ask_openai(prompt, uploaded_images)
        st.markdown("#### 📝 Mock Exam")
        st.write(exam)
        st.session_state["m_count"] = st.session_state.get("m_count",0)+1

# ---------- Floating Ask Zentra chat ----------
def chat_turn(user_msg: str) -> str:
    # include recent chat + (optionally) current doc context
    history = st.session_state.chat[-10:]
    hist_text = ""
    for role, msg in history:
        hist_text += f"{role.upper()}: {msg}\n"
    context = f"\n\nCONTEXT (notes snippet):\n{full_text[:3500]}" if full_text.strip() else ""
    prompt = f"""You are Zentra, a precise tutor. Answer clearly and concisely.
Explain at the student's level and show steps when helpful.
If the user highlights a line, unpack it with intuition and examples.
{context}
{hist_text}
USER: {user_msg}
"""
    reply = ask_openai(prompt, uploaded_images)
    return reply

if st.session_state.show_chat:
    with st.container():
        st.markdown('<div class="z-chat">', unsafe_allow_html=True)
        st.markdown("<h4>💬 Ask Zentra</h4>", unsafe_allow_html=True)
        st.markdown('<div class="inner">', unsafe_allow_html=True)
        if len(st.session_state.chat)==0:
            st.markdown('<div class="z-msg z-ai">Hi! Ask anything about your notes or any concept.</div>', unsafe_allow_html=True)
        else:
            for role, msg in st.session_state.chat[-12:]:
                cls = "z-user" if role=="user" else "z-ai"
                st.markdown(f'<div class="z-msg {cls}">{msg}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        with st.form("ask_form", clear_on_submit=True):
            ask = st.text_input("Type your question", label_visibility="collapsed")
            sent = st.form_submit_button("Send")
        if sent and ask.strip():
            st.session_state.chat.append(("user", ask.strip()))
            ans = chat_turn(ask.strip())
            st.session_state.chat.append(("ai", ans))
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

# ---------- Hover-to-Ask (selection helper) ----------
st.markdown("""
<script>
document.addEventListener('mouseup', function(){
  let s = window.getSelection().toString();
  if(s && s.length > 3){
    const ok = confirm("Ask Zentra about:\n\n" + s + "\n\nOpen chat?");
    if(ok){
      // toggle chat
      const stBtn = window.parent.document.querySelector('button[kind="secondary"]');
      // fallback to hidden button
      const all = window.parent.document.querySelectorAll('button');
    }
  }
});
</script>
""", unsafe_allow_html=True)
