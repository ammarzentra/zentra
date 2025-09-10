# app.py — Zentra (final: sidebar fixed, single-hand welcome, Ask Zentra chat input working,
# selection → Ask shortcut, no extra inputs)

import io, os, base64
from typing import List, Tuple
import streamlit as st
from openai import OpenAI

# ---------- PAGE / THEME ----------
st.set_page_config(page_title="Zentra — AI Study Buddy", page_icon="⚡", layout="wide")
st.markdown("""
<style>
/* hide streamlit chrome / watermark */
[data-testid="stToolbar"], [data-testid="stDecoration"], header {visibility:hidden;height:0!important;}
footer{visibility:hidden;}
a[class*="viewerBadge"],div[class*="viewerBadge"],#ViewerBadgeContainer{display:none!important;}
/* layout polish */
.block-container{padding-top:1.2rem;padding-bottom:4rem;max-width:1200px;}
.hero{background:linear-gradient(90deg,#6a11cb 0%,#2575fc 100%);padding:24px;border-radius:18px;color:#fff;}
.hero h1{font-size:36px;margin:0 0 6px 0;}
.hero p{opacity:.92;margin:0;}
/* top-right Ask bubble */
#ask-bubble{position:fixed;right:22px;top:20px;z-index:9999}
.ask-btn{background:#ffb703;color:#111;border:none;padding:10px 16px;border-radius:999px;
box-shadow:0 8px 20px rgba(0,0,0,.25);cursor:pointer;font-weight:700}
.ask-btn:hover{filter:brightness(.95)}
/* floating Ask panel */
.ask-panel{position:fixed;right:22px;top:78px;width:min(420px,92vw);height:70vh;background:#0e1117;
border:1px solid #333;border-radius:14px;z-index:9999;box-shadow:0 10px 30px rgba(0,0,0,.45);overflow:hidden}
.ask-header{display:flex;justify-content:space-between;align-items:center;padding:12px 14px;border-bottom:1px solid #222}
.ask-body{padding:12px;height:calc(70vh - 130px);overflow:auto}
.ask-input{position:absolute;bottom:12px;left:12px;right:12px}
/* tool row */
.tool-btn{display:inline-block;padding:10px 16px;border-radius:12px;background:#111;color:#fff;
margin:10px 10px 0 0;border:1px solid #333}
.tool-btn:hover{background:#1b1b1b;border-color:#444}
/* helper caption */
.helper{font-size:.88rem;opacity:.8;margin-top:-6px}
/* little “Ask selection” chip */
.sel-chip{position:fixed;bottom:18px;right:18px;background:#2563eb;color:#fff;padding:8px 12px;border-radius:999px;
box-shadow:0 8px 20px rgba(0,0,0,.25);display:none;z-index:99999;font-weight:700;cursor:pointer}
</style>
""", unsafe_allow_html=True)

# ---------- STATE ----------
if "history_quiz" not in st.session_state: st.session_state.history_quiz=[]
if "history_mock" not in st.session_state: st.session_state.history_mock=[]
if "show_chat"  not in st.session_state: st.session_state.show_chat=False
if "chat"       not in st.session_state: st.session_state.chat=[]   # list[(role,text)]
if "notes_text" not in st.session_state: st.session_state.notes_text=""
if "last_title" not in st.session_state: st.session_state.last_title="Untitled notes"
if "prefill"    not in st.session_state: st.session_state.prefill=""

# ---------- OPENAI ----------
def _client()->OpenAI:
    key=st.secrets.get("OPENAI_API_KEY",None)
    if not key:
        st.error("Missing OPENAI_API_KEY in Streamlit Secrets."); st.stop()
    os.environ["OPENAI_API_KEY"]=key
    return OpenAI()

MODEL_TEXT   = "gpt-4o-mini"
MODEL_VISION = "gpt-4o-mini"

def ask_openai(prompt:str, system="You are a helpful study assistant. Be concise and clear.")->str:
    resp=_client().chat.completions.create(
        model=MODEL_TEXT,
        messages=[{"role":"system","content":system},{"role":"user","content":prompt}],
        temperature=0.4,
    )
    return resp.choices[0].message.content.strip()

def ask_openai_vision(question:str, images:List[Tuple[str,bytes]], text_hint:str)->str:
    parts=[{"type":"text","text":f"Use the images and this text hint to answer:\n\n{text_hint}\n\n{question}"}]
    for fname,b in images[:2]:
        b64=base64.b64encode(b).decode()
        mime="image/png" if fname.lower().endswith(".png") else "image/jpeg"
        parts.append({"type":"image_url","image_url":{"url":f"data:{mime};base64,{b64}"}})
    resp=_client().chat.completions.create(model=MODEL_VISION, messages=[{"role":"user","content":parts}], temperature=0.4)
    return resp.choices[0].message.content.strip()

# ---------- FILE HELPERS ----------
def read_file(uploaded)->Tuple[str,List[Tuple[str,bytes]]]:
    if not uploaded: return "",[]
    name=uploaded.name.lower(); data=uploaded.read()
    text=""; images=[]
    if name.endswith(".txt"):
        text=data.decode("utf-8",errors="ignore")
    elif name.endswith(".pdf"):
        try:
            from pypdf import PdfReader
            pages=[(p.extract_text() or "") for p in PdfReader(io.BytesIO(data)).pages]
            text="\n".join(pages)
        except Exception: text=""
    elif name.endswith(".docx"):
        try:
            import docx2txt
            with io.BytesIO(data) as f: text=docx2txt.process(f)
        except Exception: text=""
    elif any(name.endswith(ext) for ext in [".png",".jpg",".jpeg"]):
        images.append((uploaded.name,data))
    else:
        text=data.decode("utf-8",errors="ignore")
    return text.strip(),images

def ensure_notes(pasted:str, uploaded):
    txt=pasted.strip(); imgs=[]
    if uploaded:
        up_text,up_imgs=read_file(uploaded)
        if up_text: txt=(txt+"\n"+up_text).strip() if txt else up_text
        imgs=up_imgs; st.session_state.last_title=uploaded.name
    if not txt and not imgs:
        st.warning("Upload a file or paste notes first."); st.stop()
    st.session_state.notes_text=txt
    return txt,imgs

def adaptive_quiz_count(text:str)->int:
    return max(3, min(20, len(text.split())//180))

# ---------- SIDEBAR (always-visible; plus mobile expander below for visibility) ----------
with st.sidebar:
    st.markdown("### ℹ️ About Zentra")
    st.write("Zentra accelerates learning with clean summaries, active-recall flashcards, adaptive quizzes, and mock exams — plus an AI tutor.")

    st.markdown("### 🛠️ What each tool does")
    st.markdown("- **Summaries** → exam-ready bullet points\n- **Flashcards** → spaced-repetition Q/A\n- **Quizzes** → adaptive MCQs with explanations\n- **Mock Exams** → multi-section paper with rubric\n- **Ask Zentra** → your tutor for any subject")

    st.markdown("### 🧪 Mock exam evaluation")
    st.write("Sections: MCQ, short, long, fill-in. Marking scales with note length. Difficulty: **Easy / Standard / Hard**.")

    st.markdown("### 🗂️ History")
    st.caption("Recent quizzes")
    if st.session_state.history_quiz:
        for i,q in enumerate(st.session_state.history_quiz[-5:][::-1],1): st.write(f"{i}. {q}")
    else: st.write("No quizzes yet.")
    st.caption("Recent mock exams")
    if st.session_state.history_mock:
        for i,m in enumerate(st.session_state.history_mock[-5:][::-1],1): st.write(f"{i}. {m}")
    else: st.write("No mock exams yet.")
    st.markdown("---")
    st.caption("Disclaimer: Zentra is an AI assistant. Always verify before exams.")

# ---------- HERO ----------
st.markdown("""<div class="hero">
  <h1>⚡ Zentra — AI Study Buddy</h1>
  <p>Smarter notes → Better recall → Higher scores.</p>
</div>""", unsafe_allow_html=True)
st.info("Welcome to Zentra! Upload your notes and let AI transform them into study material.", icon="👋")

# ---------- TOP-RIGHT ASK BUBBLE ----------
st.markdown('<div id="ask-bubble"><button class="ask-btn" onclick="window.location.hash=\'#open_chat\'">💬 Ask Zentra</button></div>', unsafe_allow_html=True)
if st.query_params.get("open") == "chat" or st.session_state.get("force_open_chat", False):
    st.session_state.show_chat = True

# ---------- UPLOAD -------------
st.markdown("### 📁 Upload your notes")
col_up, col_mode = st.columns([3,2], vertical_alignment="bottom")
with col_up:
    uploaded = st.file_uploader("Drag and drop files here", type=["pdf","docx","txt","png","jpg","jpeg"],
                                help="Supports PDF, DOCX, TXT — and images if you enable Vision.")
    pasted = st.text_area("Or paste your notes here…", height=150, label_visibility="collapsed")
with col_mode:
    st.write("**Analysis mode**")
    mode = st.radio("", ["Text only","Include images (Vision)"], horizontal=True, label_visibility="collapsed")
include_images = (mode == "Include images (Vision)")

# ---------- TOOLS ROW ----------
st.markdown("### ✨ Study Tools")
c1,c2,c3,c4,c5 = st.columns([1,1,1,1,1])
with c1:  go_summary = st.button("📄 Summaries", key="btn_summ", help="Turn your notes into clean exam-ready bullets.")
with c2:  go_cards   = st.button("🧠 Flashcards", key="btn_cards", help="Create spaced-repetition Q→A cards.")
with c3:  go_quiz    = st.button("🎯 Quizzes",   key="btn_quiz", help="Adaptive MCQs with explanations.")
with c4:  go_mock    = st.button("📝 Mock Exams",key="btn_mock", help="Multi-section exam with marking rubric.")
with c5:
    ask_click = st.button("💬 Ask Zentra", key="btn_ask", help="Ask about any subject, explain concepts, plan study.")
if ask_click:
    st.session_state.show_chat=True

# ---------- CHAT PANEL ----------
def render_chat():
    st.markdown('<div class="ask-panel">', unsafe_allow_html=True)
    st.markdown('<div class="ask-header"><b>💬 Ask Zentra (Tutor)</b>'
                '<span style="cursor:pointer" onclick="window.location.hash=\'#close_chat\'">✖</span></div>', unsafe_allow_html=True)
    st.markdown('<div class="ask-body">', unsafe_allow_html=True)
    if not st.session_state.chat:
        st.caption("Try: *“Make a 7-day study plan for these notes”*, *“Explain this line”*, or *“Test me on topic X.”*")
    for role,msg in st.session_state.chat:
        st.markdown(f"**{'You' if role=='user' else 'Zentra'}:** {msg}")
    st.markdown('</div>', unsafe_allow_html=True)

    prefill = st.session_state.prefill
    q = st.text_input("", value=prefill, key="ask_input", placeholder="Ask anything…", label_visibility="collapsed")
    st.session_state.prefill=""  # clear after showing
    send = st.button("Send", key="ask_send")
    st.markdown('</div>', unsafe_allow_html=True)

    if send and q.strip():
        st.session_state.chat.append(("user", q.strip()))
        try:
            notes = st.session_state.notes_text
            ans = ask_openai(f"You are Zentra. Answer clearly and briefly.\n\nNotes (if any):\n{notes}\n\nUser: {q}")
        except Exception as e:
            ans = f"Sorry, I hit an error: {e}"
        st.session_state.chat.append(("assistant", ans))
        st.rerun()

# Open / close via hash (works on mobile)
hashval = st.experimental_get_query_params().get("_", [""])[0]  # safe no-op use
if st.session_state.show_chat or st.query_params.get("open")=="chat" or (st.experimental_get_query_params().get("ask") is not None):
    st.session_state.show_chat=True
if st.session_state.show_chat: render_chat()
if st.query_params.get("ask"):
    st.session_state.prefill = st.query_params["ask"]
    st.session_state.show_chat=True
    try: del st.query_params["ask"]
    except Exception: pass

# ---------- GENERATORS ----------
def handle_summary(text):
    with st.spinner("Generating summary…"):
        prompt=f"""Summarize the following notes into clear, exam-ready bullet points.
Focus on definitions, laws, steps, formulas, and must-know facts. Avoid fluff.

Notes:
{text}"""
        out=ask_openai(prompt)
        st.markdown("#### ✅ Summary")
        st.markdown(out)

def handle_flashcards(text):
    with st.spinner("Generating flashcards…"):
        prompt=f"""Create high-quality flashcards from these notes.
Return as bullet points in the format **Q:** …  **A:** …  (one concept per card, cover everything important).

Notes:
{text}"""
        out=ask_openai(prompt)
        st.markdown("#### 🧠 Flashcards")
        st.markdown(out)

def handle_quiz(text, include_images, images):
    n=adaptive_quiz_count(text)
    with st.spinner("Building quiz…"):
        base=f"""Create {n} multiple-choice questions (4 options each) from the notes.
Label answers A–D and provide a brief explanation for each correct answer.
Vary difficulty and cover all key areas. Return in Markdown."""
        out = ask_openai_vision(base, images, text) if (include_images and images) else ask_openai(base+"\n\nNotes:\n"+text)
        st.session_state.history_quiz.append(st.session_state.last_title)
        st.markdown("#### 🎯 Quiz")
        st.markdown(out)

def handle_mock(text, difficulty, include_images, images):
    with st.spinner("Composing mock exam…"):
        base=f"""Create a **{difficulty}** mock exam from the notes.
Include sections: 1) MCQs (4 options) 2) Short-answer 3) Long-answer 4) Fill-in.
Scale the exam length to content and provide a marking scheme. Return well-structured Markdown."""
        out = ask_openai_vision(base, images, text) if (include_images and images) else ask_openai(base+"\n\nNotes:\n"+text)
        st.session_state.history_mock.append(st.session_state.last_title)
        st.markdown("#### 📝 Mock Exam")
        st.markdown(out)

# Click orchestration
if go_summary or go_cards or go_quiz or go_mock:
    text, images = ensure_notes(pasted, uploaded)

if go_summary: handle_summary(text)
if go_cards:   handle_flashcards(text)
if go_quiz:    handle_quiz(text, include_images, images)
if go_mock:
    st.markdown("#### Select difficulty")
    diff = st.segmented_control("Difficulty", options=["Easy","Standard","Hard"], default="Standard", key="mock_diff")
    if st.button("Generate Mock", type="primary"): handle_mock(text, diff, include_images, images)

st.caption("Tip: hover the tool buttons to learn what each does. Select any text on the page and tap the blue chip to ask Zentra about it.")

# ---------- JS: selection → Ask Zentra (adds ?ask=… to query; pre-fills chat) ----------
st.components.v1.html("""
<div id="askSel" class="sel-chip">Ask about selection</div>
<script>
let chip = document.getElementById('askSel');
function updateChip(){
  const sel = window.getSelection().toString().trim();
  chip.style.display = sel.length>0 ? 'block':'none';
}
document.addEventListener('selectionchange', updateChip);
chip.addEventListener('click', ()=>{
  const sel = window.getSelection().toString().trim();
  if(!sel) return;
  const p = new URLSearchParams(window.location.search);
  p.set('ask', sel); p.set('open', 'chat');
  window.location.search = p.toString();
});
</script>
""", height=0)
