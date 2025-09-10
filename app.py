# app.py — Zentra (Final Polished)

import io
import os
import base64
from typing import List, Tuple
import streamlit as st
from openai import OpenAI

# ---------- SETUP ----------
st.set_page_config(page_title="Zentra — AI Study Buddy", page_icon="⚡", layout="wide")

# Hide Streamlit chrome
st.markdown("""
<style>
[data-testid="stToolbar"], [data-testid="stDecoration"], header {visibility: hidden; height: 0 !important;}
footer {visibility: hidden;}
a[class*="viewerBadge"], div[class*="viewerBadge"], #ViewerBadgeContainer {display:none !important;}
.block-container {padding-top: 1rem; max-width: 1200px;}
.hero {background: linear-gradient(90deg,#6a11cb 0%,#2575fc 100%); padding: 24px; border-radius: 16px; color: #fff;}
.hero h1 {font-size: 36px; margin: 0;}
.hero p {opacity:.9; margin: 4px 0 0;}
.tool-btn {padding:10px 16px; border-radius:12px; background:#111; color:#fff; margin:6px; border:1px solid #333;}
.tool-btn:hover {background:#1b1b1b; border-color:#444;}
.ask-panel {position: fixed; right: 20px; top: 100px; width: min(420px,92vw); height:70vh;
 background:#0e1117; border:1px solid #333; border-radius:14px; z-index:9999; box-shadow:0 10px 30px rgba(0,0,0,.45);}
.ask-header {display:flex; justify-content:space-between; align-items:center; padding:10px 14px; border-bottom:1px solid #222;}
.ask-body {padding:12px; height:calc(70vh - 120px); overflow:auto;}
.ask-input {position:absolute; bottom:12px; left:12px; right:12px;}
</style>
""", unsafe_allow_html=True)

# ---------- STATE ----------
if "history_quiz" not in st.session_state: st.session_state.history_quiz = []
if "history_mock" not in st.session_state: st.session_state.history_mock = []
if "show_chat" not in st.session_state: st.session_state.show_chat = False
if "chat" not in st.session_state: st.session_state.chat = []
if "notes_text" not in st.session_state: st.session_state.notes_text = ""
if "last_title" not in st.session_state: st.session_state.last_title = "Untitled notes"

# ---------- OPENAI ----------
def get_client() -> OpenAI:
    key = st.secrets.get("OPENAI_API_KEY", None)
    if not key:
        st.error("Missing OPENAI_API_KEY in secrets")
        st.stop()
    os.environ["OPENAI_API_KEY"] = key
    return OpenAI()

MODEL_TEXT = "gpt-4o-mini"
MODEL_VISION = "gpt-4o-mini"

def ask_openai(prompt: str, system="You are a helpful study assistant. Be concise."):
    client = get_client()
    resp = client.chat.completions.create(
        model=MODEL_TEXT,
        messages=[{"role":"system","content":system},{"role":"user","content":prompt}],
        temperature=0.4,
    )
    return resp.choices[0].message.content.strip()

def ask_openai_vision(question: str, images: List[Tuple[str, bytes]], text_hint: str):
    client = get_client()
    parts = [{"type":"text","text": f"Use the images + text:\n{text_hint}\n\nQ: {question}"}]
    for fname,b in images[:2]:
        b64 = base64.b64encode(b).decode()
        mime = "image/png" if fname.lower().endswith(".png") else "image/jpeg"
        parts.append({"type":"image_url","image_url":{"url": f"data:{mime};base64,{b64}"}})
    resp = client.chat.completions.create(model=MODEL_VISION, messages=[{"role":"user","content":parts}], temperature=0.4)
    return resp.choices[0].message.content.strip()

# ---------- HELPERS ----------
def read_file(uploaded) -> Tuple[str, List[Tuple[str, bytes]]]:
    if not uploaded: return "", []
    name = uploaded.name.lower(); data = uploaded.read(); text=""; imgs=[]
    if name.endswith(".txt"):
        text = data.decode("utf-8", errors="ignore")
    elif name.endswith(".pdf"):
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        text = "\n".join([p.extract_text() or "" for p in reader.pages])
    elif name.endswith(".docx"):
        import docx2txt, tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
            tmp.write(data); tmp.flush()
            text = docx2txt.process(tmp.name)
    elif any(name.endswith(ext) for ext in [".png",".jpg",".jpeg"]):
        imgs.append((uploaded.name,data))
    else:
        text = data.decode("utf-8", errors="ignore")
    return text.strip(), imgs

def ensure_notes(pasted, uploaded):
    txt = pasted.strip(); imgs=[]
    if uploaded:
        up_txt, up_imgs = read_file(uploaded)
        if up_txt: txt = (txt+"\n"+up_txt).strip() if txt else up_txt
        imgs = up_imgs; st.session_state.last_title = uploaded.name
    if not txt and not imgs:
        st.warning("Upload or paste notes first."); st.stop()
    st.session_state.notes_text = txt; return txt, imgs

def adaptive_quiz_count(text:str)->int: return max(3,min(20,len(text.split())//180))

# ---------- SIDEBAR ----------
with st.sidebar:
    st.markdown("### ℹ️ About Zentra")
    st.write("Zentra accelerates learning with summaries, flashcards, adaptive quizzes, and mock exams — plus an AI tutor.")

    st.markdown("### 🛠️ What each tool does")
    st.markdown("- **Summaries** → exam-ready bullet points\n- **Flashcards** → spaced-repetition Q/A\n- **Quizzes** → MCQs with explanations (AI chooses count)\n- **Mock Exams** → multi-section exam with marking guide\n- **Ask Zentra** → your AI tutor/chat")

    st.markdown("### 🧪 Mock exam evaluation")
    st.write("Sections: MCQ, short, long, fill-in. Marking is criterion-based; length scales with notes. Difficulty: Easy / Standard / Hard.")

    st.markdown("### 🗂️ History")
    st.caption("Recent quizzes")
    if st.session_state.history_quiz: [st.write(f"- {q}") for q in st.session_state.history_quiz[-5:][::-1]]
    else: st.write("No quizzes yet.")
    st.caption("Recent mock exams")
    if st.session_state.history_mock: [st.write(f"- {m}") for m in st.session_state.history_mock[-5:][::-1]]
    else: st.write("No mock exams yet.")

    st.markdown("---")
    st.caption("Disclaimer: Zentra is an AI assistant. Verify before exams.")

# ---------- HERO ----------
st.markdown('<div class="hero"><h1>⚡ Zentra — AI Study Buddy</h1><p>Smarter notes → Better recall → Higher scores.</p></div>', unsafe_allow_html=True)
st.info("👋 Welcome to Zentra! Upload your notes and let AI transform them into study material.")

# ---------- UPLOAD ----------
st.markdown("### 📁 Upload your notes")
col1,col2=st.columns([3,2])
with col1:
    uploaded=st.file_uploader("Drag and drop",type=["pdf","docx","txt","png","jpg","jpeg"],help="Supports PDF, DOCX, TXT — and images if Vision enabled.")
    pasted=st.text_area("Or paste notes here…",height=150,label_visibility="collapsed")
with col2:
    st.write("**Analysis mode**")
    mode=st.radio("",["Text only","Include images (Vision)"],horizontal=True,label_visibility="collapsed")
include_images=(mode=="Include images (Vision)")

# ---------- TOOLS ----------
st.markdown("### ✨ Study Tools")
c1,c2,c3,c4,c5=st.columns(5)
with c1: go_summary=st.button("📄 Summaries",help="Exam-ready bullet points")
with c2: go_cards=st.button("🧠 Flashcards",help="Spaced-repetition Q/A")
with c3: go_quiz=st.button("🎯 Quizzes",help="Adaptive MCQs with explanations")
with c4: go_mock=st.button("📝 Mock Exams",help="Multi-section exam with rubric")
with c5: ask_click=st.button("💬 Ask Zentra",help="Tutor chat for all subjects")

if ask_click: st.session_state.show_chat=True

# ---------- ASK ZENTRA CHAT ----------
def render_chat():
    st.markdown('<div class="ask-panel">',unsafe_allow_html=True)
    st.markdown('<div class="ask-header"><b>💬 Ask Zentra</b><span style="cursor:pointer;" onclick="window.parent.location.reload()">✖</span></div>',unsafe_allow_html=True)
    st.markdown('<div class="ask-body">',unsafe_allow_html=True)
    if not st.session_state.chat: st.caption("Ask anything: formulas, summaries, study plans…")
    for role,msg in st.session_state.chat: st.markdown(f"**{'You' if role=='user' else 'Zentra'}:** {msg}")
    st.markdown('</div>',unsafe_allow_html=True)
    q=st.text_input("Ask Zentra",key="ask_input",placeholder="Type your question…",label_visibility="collapsed")
    if st.button("Send",key="ask_send") and q.strip():
        st.session_state.chat.append(("user",q.strip()))
        try: ans=ask_openai(f"Notes:\n{st.session_state.notes_text}\n\nUser: {q}")
        except Exception as e: ans=f"Error: {e}"
        st.session_state.chat.append(("assistant",ans)); st.rerun()
    st.markdown('</div>',unsafe_allow_html=True)
if st.session_state.show_chat: render_chat()

# ---------- HANDLERS ----------
def handle_summary(txt):
    with st.spinner("Generating summary…"):
        out=ask_openai(f"Summarize clearly into exam-style bullet points:\n{txt}")
        st.subheader("✅ Summary"); st.markdown(out)
def handle_flashcards(txt):
    with st.spinner("Generating flashcards…"):
        out=ask_openai(f"Create flashcards in Q/A format covering all concepts:\n{txt}")
        st.subheader("🧠 Flashcards"); st.markdown(out)
def handle_quiz(txt,inc,img):
    n=adaptive_quiz_count(txt)
    with st.spinner("Building quiz…"):
        base=f"Create {n} MCQs with 4 options + explanations:\n{txt}"
        out=ask_openai_vision(base,img,txt) if inc and img else ask_openai(base)
        st.session_state.history_quiz.append(st.session_state.last_title)
        st.subheader("🎯 Quiz"); st.markdown(out)
def handle_mock(txt,diff,inc,img):
    with st.spinner("Composing mock exam…"):
        base=f"Create a {diff} mock exam with sections: MCQ, short, long, fill-in. Scale length to notes. Add marking scheme.\n{txt}"
        out=ask_openai_vision(base,img,txt) if inc and img else ask_openai(base)
        st.session_state.history_mock.append(st.session_state.last_title)
        st.subheader("📝 Mock Exam"); st.markdown(out)

# Execute actions
if go_summary or go_cards or go_quiz or go_mock:
    text,images=ensure_notes(pasted,uploaded)
if go_summary: handle_summary(text)
if go_cards: handle_flashcards(text)
if go_quiz: handle_quiz(text,include_images,images)
if go_mock:
    st.markdown("#### Select difficulty")
    diff=st.radio("Difficulty",["Easy","Standard","Hard"],horizontal=True)
    if st.button("Generate Mock",type="primary"): handle_mock(text,diff,include_images,images)
