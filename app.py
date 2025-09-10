# app.py — Zentra (Phase 2 Ready)

import io, os, base64, sqlite3
from typing import List, Tuple
import streamlit as st
from openai import OpenAI
from pypdf import PdfReader

# ---------- SETUP ----------
st.set_page_config(page_title="Zentra — AI Study Buddy", page_icon="⚡", layout="wide")

# ---------- DB INIT ----------
def init_db():
    conn = sqlite3.connect("zentra.db")
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT,
        title TEXT,
        score TEXT,
        feedback TEXT
    )""")
    conn.commit()
    return conn
conn = init_db()

def save_history(kind, title, score, feedback):
    cur = conn.cursor()
    cur.execute("INSERT INTO history (type,title,score,feedback) VALUES (?,?,?,?)",
                (kind, title, score, feedback))
    conn.commit()

def load_history():
    cur = conn.cursor()
    cur.execute("SELECT type,title,score,feedback FROM history ORDER BY id DESC LIMIT 10")
    return cur.fetchall()

# ---------- OPENAI ----------
def get_client():
    os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]
    return OpenAI()

MODEL_TEXT = "gpt-4o-mini"
MODEL_VISION = "gpt-4o-mini"

def ask_openai(prompt, system="You are Zentra, a study tutor. Be concise and supportive."):
    client = get_client()
    resp = client.chat.completions.create(
        model=MODEL_TEXT,
        messages=[{"role":"system","content":system},{"role":"user","content":prompt}]
    )
    return resp.choices[0].message.content.strip()

def ask_openai_vision(question, images, text_hint):
    client = get_client()
    parts=[{"type":"text","text":f"{question}\nNotes hint:\n{text_hint}"}]
    for fname,b in images[:2]:
        b64=base64.b64encode(b).decode()
        mime="image/png" if fname.endswith("png") else "image/jpeg"
        parts.append({"type":"image_url","image_url":{"url":f"data:{mime};base64,{b64}"}})
    resp=client.chat.completions.create(model=MODEL_VISION,messages=[{"role":"user","content":parts}])
    return resp.choices[0].message.content.strip()

# ---------- FILE HANDLING ----------
def read_file(uploaded) -> Tuple[str, List[Tuple[str, bytes]]]:
    if not uploaded: return "", []
    name = uploaded.name.lower(); data = uploaded.read()
    text, images = "", []
    if name.endswith(".txt"):
        text = data.decode("utf-8","ignore")
    elif name.endswith(".pdf"):
        try:
            reader=PdfReader(io.BytesIO(data))
            pages=[p.extract_text() or "" for p in reader.pages]
            text="\n".join(pages)
        except: text=""
    elif name.endswith(".docx"):
        import docx2txt
        text=docx2txt.process(io.BytesIO(data))
    elif any(name.endswith(ext) for ext in ["png","jpg","jpeg"]):
        images.append((uploaded.name,data))
    return text.strip(), images

# ---------- SIDEBAR ----------
with st.sidebar:
    st.markdown("## 📊 Toolbox")
    st.markdown("**About**: Zentra = summaries, flashcards, quizzes, mocks, tutor.")
    st.divider()
    st.markdown("### 🛠 Tools")
    st.markdown("• **Summaries** → exam bullets\n• **Flashcards** → Q/A recall\n• **Quizzes** → MCQs + explanations\n• **Mock Exams** → multi-section + rubric\n• **Ask Zentra** → tutor/chat")
    st.divider()
    st.markdown("### 🧪 Mock Evaluation")
    st.write("MCQ, short, long, fill-in.\nDifficulty: *Easy / Standard / Hard*. Scales with content.")
    st.divider()
    st.markdown("### 📂 History")
    for h in load_history():
        kind,title,score,fb=h
        st.markdown(f"**{kind}**: {title} → {score}\n> {fb}")
    st.divider()
    st.caption("Disclaimer: AI-generated content — verify before exams.")

# ---------- HERO ----------
st.markdown("""<div style="background:linear-gradient(90deg,#6a11cb,#2575fc);
padding:24px;border-radius:16px;color:white">
<h1>⚡ Zentra — AI Study Buddy</h1>
<p>Smarter notes → Better recall → Higher scores.</p>
</div>""",unsafe_allow_html=True)

st.info("👋 Welcome to Zentra! Upload your notes and let AI transform them into study material.")

# ---------- UPLOAD ----------
st.markdown("### 📁 Upload your notes")
col1,col2=st.columns([3,2])
with col1:
    uploaded=st.file_uploader("Drag & drop here",type=["pdf","docx","txt","png","jpg","jpeg"])
    pasted=st.text_area("Or paste notes…",height=150)
with col2:
    mode=st.radio("Analysis mode",["Text only","Include images (Vision)"])

# ---------- STUDY TOOLS ----------
st.markdown("### ✨ Study Tools")
c1,c2,c3,c4,c5=st.columns(5)
go_summary=c1.button("📄 Summaries")
go_cards=c2.button("🧠 Flashcards")
go_quiz=c3.button("🎯 Quizzes")
go_mock=c4.button("📝 Mock Exams")
ask_click=c5.button("💬 Ask Zentra")

# ---------- ASK ZENTRA CHAT ----------
if "chat" not in st.session_state: st.session_state.chat=[]
if ask_click: st.session_state.show_chat=True
if st.session_state.get("show_chat",False):
    st.markdown("### 💬 Ask Zentra")
    q=st.text_input("Ask anything…",key="ask_inp")
    if st.button("Send"):
        st.session_state.chat.append(("You",q))
        ans=ask_openai(q)
        st.session_state.chat.append(("Zentra",ans))
    if st.button("Clear"): st.session_state.chat=[]
    if st.button("Close"): st.session_state.show_chat=False
    for r,m in st.session_state.chat:
        st.markdown(f"**{r}**: {m}")

# ---------- HANDLERS ----------
def ensure_notes():
    txt,imgs="",""
    if uploaded: txt,imgs=read_file(uploaded)
    if pasted.strip(): txt+="\n"+pasted.strip()
    if not txt and not imgs: st.warning("Your notes look empty."); st.stop()
    return txt,imgs

if go_summary:
    txt,imgs=ensure_notes()
    st.markdown("#### ✅ Summary")
    st.write(ask_openai(f"Summarize in exam bullets:\n{txt}"))

if go_cards:
    txt,imgs=ensure_notes()
    st.markdown("#### 🧠 Flashcards")
    st.write(ask_openai(f"Make flashcards Q/A:\n{txt}"))

if go_quiz:
    txt,imgs=ensure_notes()
    st.markdown("#### 🎯 Quiz")
    out=ask_openai(f"Create adaptive MCQs with answers & explanations:\n{txt}")
    save_history("Quiz",uploaded.name if uploaded else "Notes","Completed","AI generated")
    st.write(out)

if go_mock:
    txt,imgs=ensure_notes()
    diff=st.selectbox("Difficulty",["Easy","Standard","Hard"])
    st.markdown("#### 📝 Mock Exam")
    st.write("Answer below then submit for evaluation:")
    mcq_ans=st.radio("Q1) Sample MCQ? ",["A","B","C","D"])
    short=st.text_area("Short Answer:")
    long=st.text_area("Long Essay:")
    if st.button("Submit Mock"):
        prompt=f"Evaluate this mock attempt.\nMCQ:{mcq_ans}\nShort:{short}\nLong:{long}\nNotes:{txt}"
        fb=ask_openai(prompt)
        save_history("Mock",uploaded.name if uploaded else "Notes","Scored",fb)
        st.success("✅ Mock evaluated")
        st.write(fb)
