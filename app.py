# app.py — Zentra Final Polished Version (Fixed Ask Zentra Chatbox + No Empty Box)

import os, io, tempfile
from typing import List, Tuple
import streamlit as st
from openai import OpenAI

# ---------- PAGE CONFIG ----------
st.set_page_config(
    page_title="Zentra — Your Study Buddy",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------- GLOBAL STYLES ----------
st.markdown("""
<style>
a[class*="viewerBadge"], div[class*="viewerBadge"], #ViewerBadgeContainer{display:none!important;}
footer{visibility:hidden;height:0}
.block-container{padding-top:0.75rem; padding-bottom:3rem; max-width:1200px;}
.hero{background:linear-gradient(90deg,#6a11cb 0%,#2575fc 100%);
  padding:28px; border-radius:16px; color:#fff; margin-bottom:20px; text-align:center;}
.hero h1{margin:0;font-size:40px;font-weight:800;}
.hero p{margin:6px 0 0;opacity:.92;font-size:16px;}
.section-title{font-weight:800;font-size:22px;margin:10px 0 14px;}
.tool-row .stButton>button{
  width:100%; border-radius:12px; border:1px solid #2b2f3a;
  padding:10px; background:#10141e; color:#e8ecf7; font-weight:700;
}
.tool-row .stButton>button:hover{background:#141a27; border-color:#3a4252;}
.chat-card{background:#0e1117; border:1px solid #232b3a; border-radius:14px;
  padding:12px; max-height:420px; overflow-y:auto;}
.sidebar-card{background:#0f1420; border:1px solid #243047; border-radius:14px; padding:14px; margin-bottom:14px;}
</style>
""", unsafe_allow_html=True)

# ---------- STATE ----------
if "chat_open" not in st.session_state: st.session_state.chat_open = False
if "messages" not in st.session_state: st.session_state.messages = []
if "history_quiz" not in st.session_state: st.session_state.history_quiz = []
if "history_mock" not in st.session_state: st.session_state.history_mock = []
if "notes_text" not in st.session_state: st.session_state.notes_text = ""
if "last_title" not in st.session_state: st.session_state.last_title = "Untitled notes"
if "pending_action" not in st.session_state: st.session_state.pending_action = None
if "dev_unlocked" not in st.session_state: st.session_state.dev_unlocked = False

# ---------- PAYWALL ----------
if not st.session_state.dev_unlocked:
    st.markdown(f"""
    <div class="hero">
      <h1>⚡ Zentra — Your Study Buddy</h1>
      <p>Smarter notes → Better recall → Higher scores.</p>
    </div>
    <div class="sidebar-card" style="max-width:700px; margin:auto; text-align:center;">
      <p><b>Unlock your AI Study Buddy for just $5.99/month</b></p>
      <ul style="text-align:left;">
        <li>📄 Smart Summaries — exam-ready notes</li>
        <li>🧠 Flashcards — active recall Q/A</li>
        <li>🎯 Quizzes — instant explanations</li>
        <li>📝 Mock Exams — graded with feedback</li>
        <li>💬 Ask Zentra — your AI tutor anytime</li>
      </ul>
      <a style="background:#f72585;color:#fff;padding:12px 26px;border-radius:10px;text-decoration:none;font-weight:700;"
         href="https://zentraai.lemonsqueezy.com/buy/XXXXXXXX" target="_blank">
        👉 Subscribe Now
      </a>
      <div class="sidebar-card" style="margin-top:18px;text-align:left;">
        <b>How Zentra Works</b><br/>
        - Upload your study material<br/>
        - Zentra auto-creates summaries & flashcards<br/>
        - Practice quizzes & mocks with feedback<br/>
        - Chat with Zentra like a tutor<br/>
        - Track progress & get exam-ready faster
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
def ask_llm(prompt: str, system="You are Zentra, a precise and supportive study buddy. Be concise and clear."):
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
    text,images="",[]
    if name.endswith(".txt"): text=data.decode("utf-8","ignore")
    elif name.endswith(".pdf"):
        try:
            from pypdf import PdfReader
            reader=PdfReader(io.BytesIO(data))
            text="\n".join([(p.extract_text() or "") for p in reader.pages])
        except: text=""
    elif name.endswith(".docx"):
        try:
            import docx2txt
            with tempfile.NamedTemporaryFile(delete=False,suffix=".docx") as tmp:
                tmp.write(data); tmp.flush()
                text=docx2txt.process(tmp.name)
        except: text=""
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
    st.markdown('<div class="sidebar-card"><h3>📚 Your Study Toolkit</h3>'
                'Zentra turns your notes into a full study toolkit: summaries, flashcards, quizzes, mocks, and a tutor — all in one place.'
                '</div>', unsafe_allow_html=True)

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
    cu,cm=st.columns([3,2],vertical_alignment="bottom")
    with cu:
        uploaded=st.file_uploader("Upload file (PDF, DOCX, TXT, Images)",type=["pdf","docx","txt","png","jpg","jpeg"],label_visibility="collapsed")
        pasted=st.text_area("Paste your notes here…",height=150,label_visibility="collapsed")
    with cm: pass

    st.markdown('<div class="section-title">✨ Study Tools</div>', unsafe_allow_html=True)
    st.markdown('<div class="tool-row">',unsafe_allow_html=True)
    c1,c2,c3,c4,c5=st.columns(5)
    go_summary=c1.button("📄 Summaries")
    go_cards=c2.button("🧠 Flashcards")
    go_quiz=c3.button("🎯 Quizzes")
    go_mock=c4.button("📝 Mock Exams")
    open_chat=c5.button("💬 Ask Zentra")
    st.markdown('</div>',unsafe_allow_html=True)

    if open_chat: st.session_state.chat_open=True; st.rerun()
    out_area=st.container()

    if (go_summary or go_cards or go_quiz or go_mock) and uploaded:
        st.session_state.pending_action = "summary" if go_summary else "cards" if go_cards else "quiz" if go_quiz else "mock"
        choice = st.radio("Do you want to process this file as:", ["Text only","Text + images/diagrams"])
        if st.button(f"Continue with {st.session_state.pending_action.title()}"):
            text,_=ensure_notes(pasted,uploaded)
            if st.session_state.pending_action=="summary":
                with st.spinner("Generating summary…"):
                    out=ask_llm(f"Summarize into exam-ready bullets.\n\nNotes:\n{text}")
                out_area.subheader("✅ Summary"); out_area.markdown(out or "_(empty)_")
            elif st.session_state.pending_action=="cards":
                with st.spinner("Generating flashcards…"):
                    out=ask_llm(f"Make concise Q/A flashcards.\n\nNotes:\n{text}")
                out_area.subheader("🧠 Flashcards"); out_area.markdown(out or "_(empty)_")
            elif st.session_state.pending_action=="quiz":
                with st.spinner("Building quiz…"):
                    n=adaptive_quiz_count(text)
                    out=ask_llm(f"Create {n} MCQs (A–D) with answer+explanation.\n\nNotes:\n{text}")
                st.session_state.history_quiz.append(st.session_state.last_title)
                out_area.subheader("🎯 Quiz"); out_area.markdown(out or "_(empty)_")
            elif st.session_state.pending_action=="mock":
                diff=st.radio("Difficulty",["Easy","Standard","Hard"],horizontal=True)
                if st.button("Start Mock"):
                    with st.form("mock_form"):
                        st.write(f"### Mock Exam ({diff})")
                        raw=ask_llm(f"Create a {diff} mock with MCQs, short, long, fill-in.\n\nNotes:\n{text}")
                        st.markdown(raw)
                        mcq_ans=[st.radio(f"MCQ {i+1}",["A","B","C","D"]) for i in range(5)]
                        short_ans=[st.text_area(f"Short {i+1}") for i in range(2)]
                        long_ans=st.text_area("Long Answer")
                        fill_ans=[st.text_input(f"Fill {i+1}") for i in range(2)]
                        if st.form_submit_button("Submit Mock"):
                            result=ask_llm(f"Grade:\nMCQ {mcq_ans}\nShort {short_ans}\nLong {long_ans}\nFill {fill_ans}\n\nNotes:\n{text}")
                            st.success("✅ Graded"); st.markdown(result)
                            st.session_state.history_mock.append(f"{st.session_state.last_title} — graded")

# ---------- CHAT ----------
with col_chat:
    if st.session_state.chat_open:
        st.markdown("### 💬 Ask Zentra")
        if st.button("Close"): st.session_state.chat_open=False; st.rerun()
        if st.button("Clear"): st.session_state.messages=[]; st.rerun()
        st.markdown('<div class="chat-card">',unsafe_allow_html=True)
        for m in st.session_state.messages:
            with st.chat_message(m["role"]): st.markdown(m["content"])
        q=st.chat_input("Ask Zentra…")
        if q:
            st.session_state.messages.append({"role":"user","content":q})
            with st.chat_message("user"): st.markdown(q)
            ans=ask_llm(f"You are Zentra.\nNotes:{st.session_state.notes_text}\n\nUser:{q}")
            st.session_state.messages.append({"role":"assistant","content":ans})
            with st.chat_message("assistant"): st.markdown(ans)
            st.rerun()
        st.markdown('</div>',unsafe_allow_html=True)
