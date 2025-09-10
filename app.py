# app.py — Zentra (International Polished Final)

import io, os, base64, tempfile
from typing import List, Tuple
import streamlit as st
from openai import OpenAI
from pypdf import PdfReader
import docx2txt

# ---------- SETUP ----------
st.set_page_config(page_title="Zentra — AI Study Buddy", page_icon="⚡", layout="wide")

# Hide Streamlit chrome
st.markdown("""
<style>
[data-testid="stToolbar"], [data-testid="stDecoration"], header {visibility:hidden;height:0;}
footer {visibility:hidden;}
a[class*="viewerBadge"],div[class*="viewerBadge"],#ViewerBadgeContainer{display:none!important;}
.block-container{padding-top:1rem;max-width:1200px;}
.hero{background:linear-gradient(90deg,#6a11cb 0%,#2575fc 100%);padding:24px;border-radius:16px;color:#fff;}
.hero h1{font-size:36px;margin:0;}
.hero p{opacity:.9;margin:4px 0 0;}
.tool-btn{padding:10px 16px;border-radius:12px;background:#111;color:#fff;margin:6px;border:1px solid #333;}
.tool-btn:hover{background:#1b1b1b;border-color:#444;}
.ask-panel{position:fixed;right:20px;top:100px;width:min(420px,92vw);height:70vh;background:#0e1117;
 border:1px solid #333;border-radius:14px;z-index:9999;box-shadow:0 10px 30px rgba(0,0,0,.45);}
.ask-header{display:flex;justify-content:space-between;align-items:center;padding:10px 14px;border-bottom:1px solid #222;}
.ask-body{padding:12px;height:calc(70vh - 120px);overflow:auto;}
</style>
""", unsafe_allow_html=True)

# ---------- STATE ----------
for key,val in {
    "history_quiz":[], "history_mock":[], "show_chat":False,
    "chat":[], "notes_text":"", "last_title":"Untitled notes"
}.items():
    if key not in st.session_state: st.session_state[key]=val

# ---------- OPENAI ----------
def get_client()->OpenAI:
    key=st.secrets.get("OPENAI_API_KEY",None)
    if not key: st.error("Missing OPENAI_API_KEY"); st.stop()
    os.environ["OPENAI_API_KEY"]=key; return OpenAI()

MODEL_TEXT="gpt-4o-mini"; MODEL_VISION="gpt-4o-mini"

def ask_openai(prompt,system="You are a helpful study tutor. Be concise."):
    c=get_client()
    r=c.chat.completions.create(model=MODEL_TEXT,
        messages=[{"role":"system","content":system},{"role":"user","content":prompt}],
        temperature=0.4)
    return r.choices[0].message.content.strip()

def ask_openai_vision(prompt,images,text_hint):
    c=get_client()
    parts=[{"type":"text","text":f"Use images + text:\n{text_hint}\n\n{prompt}"}]
    for fname,b in images[:2]:
        b64=base64.b64encode(b).decode()
        mime="image/png" if fname.lower().endswith(".png") else "image/jpeg"
        parts.append({"type":"image_url","image_url":{"url":f"data:{mime};base64,{b64}"}})
    r=c.chat.completions.create(model=MODEL_VISION,messages=[{"role":"user","content":parts}],temperature=0.4)
    return r.choices[0].message.content.strip()

# ---------- HELPERS ----------
def read_file(up)->Tuple[str,List[Tuple[str,bytes]]]:
    if not up: return "",[]
    name=up.name.lower();data=up.read();text="";imgs=[]
    if name.endswith(".txt"): text=data.decode("utf-8","ignore")
    elif name.endswith(".pdf"):
        reader=PdfReader(io.BytesIO(data)); text="\n".join([p.extract_text() or "" for p in reader.pages])
    elif name.endswith(".docx"):
        with tempfile.NamedTemporaryFile(delete=False,suffix=".docx") as tmp:
            tmp.write(data);tmp.flush(); text=docx2txt.process(tmp.name)
    elif any(name.endswith(e) for e in[".png",".jpg",".jpeg"]): imgs.append((up.name,data))
    else: text=data.decode("utf-8","ignore")
    return text.strip(),imgs

def ensure_notes(pasted,uploaded):
    txt=pasted.strip();imgs=[]
    if uploaded:
        up_txt,up_imgs=read_file(uploaded)
        if up_txt: txt=(txt+"\n"+up_txt).strip() if txt else up_txt
        imgs=up_imgs; st.session_state.last_title=uploaded.name
    if not txt and not imgs: st.warning("Upload or paste notes first."); st.stop()
    st.session_state.notes_text=txt; return txt,imgs

def adaptive_quiz_count(txt): return max(3,min(20,len(txt.split())//180))

# ---------- SIDEBAR ----------
with st.sidebar:
    st.markdown("### ℹ️ About Zentra")
    st.write("Zentra helps students master content with summaries, flashcards, adaptive quizzes, and mock exams — plus an AI tutor.")
    st.markdown("### 🛠️ Tools explained")
    st.markdown("- **Summaries** → exam-ready notes\n- **Flashcards** → active recall Q/A\n- **Quizzes** → AI-chosen MCQs with explanations\n- **Mock Exams** → multi-section, marked\n- **Ask Zentra** → tutor across subjects")
    st.markdown("### 🧪 Mock exam evaluation")
    st.write("Sections: MCQ, short, long, fill-in. Marking scales with content. Difficulty: Easy / Standard / Hard.")
    st.markdown("### 🗂️ History")
    st.caption("Recent quizzes:"); st.write(st.session_state.history_quiz or "No quizzes yet")
    st.caption("Recent mocks:"); st.write(st.session_state.history_mock or "No mocks yet")
    st.markdown("---"); st.caption("Disclaimer: Zentra is AI-powered. Always verify before exams.")

# ---------- HERO ----------
st.markdown('<div class="hero"><h1>⚡ Zentra — AI Study Buddy</h1><p>Smarter notes → Better recall → Higher scores.</p></div>',unsafe_allow_html=True)
st.info("👋 Welcome to Zentra! Upload notes and let AI transform them into study material.")

# ---------- UPLOAD ----------
st.markdown("### 📁 Upload your notes")
c1,c2=st.columns([3,2])
with c1:
    uploaded=st.file_uploader("Drop files",type=["pdf","docx","txt","png","jpg","jpeg"],help="Supports text & images if Vision enabled")
    pasted=st.text_area("Or paste here…",height=150,label_visibility="collapsed")
with c2:
    st.write("**Analysis mode**")
    mode=st.radio("",["Text only","Include images (Vision)"],horizontal=True,label_visibility="collapsed")
include_images=(mode=="Include images (Vision)")

# ---------- TOOLS ----------
st.markdown("### ✨ Study Tools")
c1,c2,c3,c4,c5=st.columns(5)
with c1: go_summary=st.button("📄 Summaries",help="Concise exam-style notes")
with c2: go_cards=st.button("🧠 Flashcards",help="Active recall cards")
with c3: go_quiz=st.button("🎯 Quizzes",help="Adaptive MCQs with explanations")
with c4: go_mock=st.button("📝 Mock Exams",help="Multi-section, marked exam")
with c5: ask_click=st.button("💬 Ask Zentra",help="Tutor chat for all subjects")

if ask_click: st.session_state.show_chat=True

# ---------- ASK ZENTRA ----------
def render_chat():
    st.markdown('<div class="ask-panel">',unsafe_allow_html=True)
    st.markdown('<div class="ask-header"><b>💬 Ask Zentra</b><span style="cursor:pointer;" onclick="window.parent.location.reload()">✖</span></div>',unsafe_allow_html=True)
    st.markdown('<div class="ask-body">',unsafe_allow_html=True)
    if not st.session_state.chat: st.caption("Examples: *Explain this formula*, *Make a study plan*, *Test me on X*")
    for role,msg in st.session_state.chat: st.markdown(f"**{'You' if role=='user' else 'Zentra'}:** {msg}")
    q=st.text_input("Type your question…",key="ask_input",label_visibility="collapsed")
    if st.button("Send",key="ask_send") and q.strip():
        st.session_state.chat.append(("user",q.strip()))
        try: ans=ask_openai(f"Notes:\n{st.session_state.notes_text}\n\nUser: {q}")
        except Exception as e: ans=f"Error: {e}"
        st.session_state.chat.append(("assistant",ans)); st.rerun()
    st.markdown('</div>',unsafe_allow_html=True)
if st.session_state.show_chat: render_chat()

# ---------- HANDLERS ----------
def handle_summary(txt): st.subheader("✅ Summary"); st.markdown(ask_openai(f"Summarize into exam-style bullets:\n{txt}"))
def handle_flashcards(txt): st.subheader("🧠 Flashcards"); st.markdown(ask_openai(f"Create Q/A flashcards:\n{txt}"))
def handle_quiz(txt,inc,img):
    n=adaptive_quiz_count(txt); st.subheader("🎯 Quiz")
    base=f"Create {n} MCQs (A–D options) with explanations:\n{txt}"
    out=ask_openai_vision(base,img,txt) if inc and img else ask_openai(base)
    st.session_state.history_quiz.append(st.session_state.last_title); st.markdown(out)
def handle_mock(txt,diff,inc,img):
    st.subheader("📝 Mock Exam")
    base=f"Make a {diff} mock exam with MCQ, short, long, fill-in. Add marking scheme. Scale to notes.\n{txt}"
    out=ask_openai_vision(base,img,txt) if inc and img else ask_openai(base)
    st.session_state.history_mock.append(st.session_state.last_title); st.markdown(out)

# ---------- EXECUTION ----------
if go_summary or go_cards or go_quiz or go_mock: text,images=ensure_notes(pasted,uploaded)
if go_summary: handle_summary(text)
if go_cards: handle_flashcards(text)
if go_quiz: handle_quiz(text,include_images,images)
if go_mock:
    diff=st.radio("Select difficulty",["Easy","Standard","Hard"],horizontal=True)
    if st.button("Generate Mock",type="primary"): handle_mock(text,diff,include_images,images)
