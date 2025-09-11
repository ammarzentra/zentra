# app.py — Zentra with Paywall + Scrollable Chat (final)

import os, io, tempfile
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
.block-container{padding-top:0.75rem; padding-bottom:3rem; max-width:1200px;}
/* PAYWALL */
.paywall{
  background: linear-gradient(135deg,#6a11cb 0%,#2575fc 100%);
  border-radius: 18px; padding: 50px 28px; color:#fff;
  text-align:center; margin:40px auto; max-width:700px;
  box-shadow: 0 8px 30px rgba(0,0,0,.35);
}
.paywall h1{margin:0; font-size:46px; font-weight:800;}
.paywall p{margin:12px 0 20px; font-size:17px; opacity:.95;}
.features{text-align:left; margin:20px auto; display:inline-block; font-size:15px;}
.features li{margin:8px 0;}
.subscribe-btn{
  background:#f72585; color:#fff; padding:14px 28px;
  border-radius:12px; text-decoration:none;
  font-size:18px; font-weight:700;
  display:inline-block; transition:all .25s;
}
.subscribe-btn:hover{background:#b5179e;}
/* inside app */
.hero{background:linear-gradient(90deg,#6a11cb 0%,#2575fc 100%);
  padding:22px; border-radius:16px; color:#fff; margin-bottom:10px; text-align:center;}
.hero h1{margin:0;font-size:34px;font-weight:800;}
.hero p{margin:6px 0 0;opacity:.92}
.section-title{font-weight:800;font-size:22px;margin:10px 0 14px;}
.tool-row .stButton>button{
  width:100%; border-radius:12px; border:1px solid #2b2f3a;
  padding:10px; background:#10141e; color:#e8ecf7; font-weight:700;
}
.tool-row .stButton>button:hover{background:#141a27; border-color:#3a4252;}
/* chatbox */
.chat-box{
  background:#0e1117; border:1px solid #232b3a;
  border-radius:14px; padding:12px;
  max-height:420px; overflow-y:auto;
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
if "dev_unlocked" not in st.session_state: st.session_state.dev_unlocked = False

# ---------- PAYWALL ----------
if not st.session_state.dev_unlocked:
    st.markdown(f"""
    <div class="paywall">
      <h1>⚡ Zentra — AI Study Buddy</h1>
      <p>Unlock your personal AI Study Buddy for just <b>$5.99/month</b></p>
      <ul class="features">
        <li>📄 Smart Summaries — exam-ready notes</li>
        <li>🧠 Flashcards — active recall Q/A</li>
        <li>🎯 Quizzes — instant explanations</li>
        <li>📝 Mock Exams — graded with feedback</li>
        <li>💬 Ask Zentra — your AI tutor anytime</li>
      </ul>
      <br>
      <a class="subscribe-btn" href="https://zentraai.lemonsqueezy.com/buy/XXXXXXXX" target="_blank">
        👉 Subscribe Now
      </a>
      <div style="margin-top:20px; text-align:left; font-size:14px; background:#0f1420; border-radius:14px; padding:16px; border:1px solid #243047;">
        <b>How Zentra Works</b><br/>
        • Upload your study material<br/>
        • Zentra auto-creates summaries & flashcards<br/>
        • Practice quizzes & mocks with feedback<br/>
        • Chat with Zentra like a tutor<br/>
        • Track progress & get exam-ready faster
      </div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("🚪 Dev Login (Temp)"):
        st.session_state.dev_unlocked = True
        st.rerun()

    st.stop()

# ---------- OPENAI ----------
def _client() -> OpenAI:
    key = st.secrets.get("OPENAI_API_KEY")
    if not key: st.error("Missing OPENAI_API_KEY in Streamlit Secrets."); st.stop()
    os.environ["OPENAI_API_KEY"] = key
    return OpenAI()

MODEL = "gpt-4o-mini"
def ask_llm(prompt: str, system="You are Zentra, a supportive AI study buddy. Be concise."):
    r=_client().chat.completions.create(
        model=MODEL,
        messages=[{"role":"system","content":system},{"role":"user","content":prompt}],
        temperature=0.4
    )
    return r.choices[0].message.content.strip()

# ---------- FILE HANDLING ----------
def read_file(uploaded) -> Tuple[str,List[Tuple[str,bytes]]]:
    if not uploaded: return "", []
    name=uploaded.name.lower(); data=uploaded.read()
    text,images=" ",[]
    if name.endswith(".txt"): text=data.decode("utf-8","ignore")
    elif name.endswith(".pdf"):
        from pypdf import PdfReader
        reader=PdfReader(io.BytesIO(data))
        text="\n".join([(p.extract_text() or "") for p in reader.pages])
    elif name.endswith(".docx"):
        import docx2txt
        with tempfile.NamedTemporaryFile(delete=False,suffix=".docx") as tmp:
            tmp.write(data); tmp.flush()
            text=docx2txt.process(tmp.name)
    elif name.endswith((".png",".jpg",".jpeg")):
        images.append((uploaded.name,data))
    else:
        text=data.decode("utf-8","ignore")
    return (text or "").strip(), images

def ensure_notes(pasted,uploaded):
    txt=(pasted or "").strip(); imgs=[]
    if uploaded:
        t,ii=read_file(uploaded)
        if t: txt=(txt+"\n"+t).strip() if txt else t
        if ii: imgs=ii
        st.session_state.last_title=uploaded.name
    if len(txt)<5 and not imgs:
        st.warning("Your notes look empty."); st.stop()
    st.session_state.notes_text=txt; return txt,imgs

def adaptive_quiz_count(txt:str)->int:
    return max(3,min(20,len(txt.split())//180))

# ---------- SIDEBAR ----------
with st.sidebar:
    st.markdown("## 📚 Your Study Toolkit")
    st.write("Zentra turns your notes into a full study toolkit: summaries, flashcards, quizzes, mocks, and a tutor — all in one place.")
    st.markdown("### 📂 History")
    st.caption("Recent Quizzes:"); st.write(st.session_state.history_quiz or "—")
    st.caption("Recent Mock Exams:"); st.write(st.session_state.history_mock or "—")
    st.markdown("---"); st.caption("Disclaimer: AI-generated. Verify before exams.")

# ---------- HERO ----------
st.markdown('<div class="hero"><h1>⚡ Zentra — Your Study Buddy</h1><p>Smarter notes → Better recall → Higher scores.</p></div>', unsafe_allow_html=True)

# ---------- MAIN ----------
col_main,col_chat=st.columns([3,1.4],gap="large")
with col_main:
    st.markdown('<div class="section-title">📁 Upload Your Notes</div>', unsafe_allow_html=True)
    uploaded=st.file_uploader("Drag and drop file",type=["pdf","docx","txt","png","jpg","jpeg"])
    pasted=st.text_area("Paste your notes here…",height=150)

    st.markdown('<div class="section-title">✨ Study Tools</div>', unsafe_allow_html=True)
    c1,c2,c3,c4,c5=st.columns(5)
    go_summary=c1.button("📄 Summaries")
    go_cards=c2.button("🧠 Flashcards")
    go_quiz=c3.button("🎯 Quizzes")
    go_mock=c4.button("📝 Mock Exams")
    open_chat=c5.button("💬 Ask Zentra")
    if open_chat: st.session_state.chat_open=True; st.rerun()

    out_area=st.container()

    if go_summary or go_cards or go_quiz or go_mock:
        text,_=ensure_notes(pasted,uploaded)

    if go_summary:
        with st.spinner("Generating summary…"):
            out=ask_llm(f"Summarize into exam-ready bullets.\n\nNotes:\n{text}")
        out_area.subheader("✅ Summary"); out_area.markdown(out)

    if go_cards:
        with st.spinner("Generating flashcards…"):
            out=ask_llm(f"Make Q/A flashcards.\n\nNotes:\n{text}")
        out_area.subheader("🧠 Flashcards"); out_area.markdown(out)

    if go_quiz:
        with st.spinner("Building quiz…"):
            n=adaptive_quiz_count(text)
            out=ask_llm(f"Create {n} MCQs (A–D) with answers + explanations.\n\nNotes:\n{text}")
        st.session_state.history_quiz.append(st.session_state.last_title)
        out_area.subheader("🎯 Quiz"); out_area.markdown(out)

    if go_mock:
        diff=st.radio("Difficulty",["Easy","Standard","Hard"],horizontal=True)
        if st.button("Start Mock"):
            raw=ask_llm(f"Create a {diff} mock exam with MCQs, short, long, fill-in.\n\nNotes:\n{text}")
            st.markdown(raw)

# ---------- CHAT ----------
with col_chat:
    if st.session_state.chat_open:
        st.markdown("### 💬 Ask Zentra")
        if st.button("Close"): st.session_state.chat_open=False; st.rerun()
        if st.button("Clear"): st.session_state.messages=[]; st.rerun()

        st.markdown('<div class="chat-box">',unsafe_allow_html=True)
        for m in st.session_state.messages:
            with st.chat_message(m["role"]): st.markdown(m["content"])
        st.markdown('</div>',unsafe_allow_html=True)

        q=st.chat_input("Ask Zentra…")
        if q:
            st.session_state.messages.append({"role":"user","content":q})
            with st.chat_message("user"): st.markdown(q)
            ans=ask_llm(f"You are Zentra.\nNotes:{st.session_state.notes_text}\n\nUser:{q}")
            st.session_state.messages.append({"role":"assistant","content":ans})
            with st.chat_message("assistant"): st.markdown(ans)
            st.rerun()
