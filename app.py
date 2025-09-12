# app.py — Zentra Final Polished Build (with 3-day trial, fixed buttons, GenZ punchline)

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
/* HERO PAYWALL */
.paywall{
  background: linear-gradient(135deg,#6a11cb 0%,#2575fc 100%);
  border-radius: 18px; padding: 50px 28px; color:#fff;
  text-align:center; margin:40px auto; max-width:720px;
  box-shadow: 0 8px 30px rgba(0,0,0,.35);
}
.paywall h1{margin:0; font-size:46px; font-weight:800;}
.paywall p{margin:12px 0 20px; font-size:17px; opacity:.95;}
.features{text-align:left; margin:20px auto; display:inline-block; font-size:15px;}
.features li{margin:8px 0;}
.subscribe-btn{
  background:#ff9f1c; color:#000; padding:14px 32px;
  border-radius:12px; text-decoration:none;
  font-size:18px; font-weight:800;
  display:inline-block; transition:all .25s;
}
.subscribe-btn:hover{background:#ffbf69;}
/* inside app */
.hero{background:linear-gradient(90deg,#6a11cb 0%,#2575fc 100%);
  padding:28px; border-radius:16px; color:#fff; margin-bottom:20px; text-align:center;}
.hero h1{margin:0;font-size:38px;font-weight:800;}
.hero p{margin:6px 0 0;opacity:.92;font-size:18px;}
.section-title{font-weight:800;font-size:22px;margin:10px 0 14px;}
.tool-row .stButton>button{
  width:100%; border-radius:12px; border:1px solid #2b2f3a;
  padding:10px; background:#10141e; color:#e8ecf7; font-weight:700;
}
.tool-row .stButton>button:hover{background:#141a27; border-color:#3a4252;}
.chat-box{max-height:420px; overflow-y:auto; padding:10px;
  border:1px solid #232b3a; border-radius:14px; background:#0e1117;}
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
if "pending_tool" not in st.session_state: st.session_state.pending_tool = None

# ---------- PAYWALL ----------
if not st.session_state.dev_unlocked:
    st.markdown(f"""
    <div class="paywall">
      <h1>⚡ Zentra — AI Study Buddy</h1>
      <p>Unlock your personal AI Study Buddy for just <b>$5.99/month</b> <br> 🎉 Includes <b>3-day FREE trial</b></p>
      <ul class="features">
        <li>📄 Smart Summaries — exam-ready notes</li>
        <li>🧠 Flashcards — active recall Q/A</li>
        <li>🎯 Quizzes — instant explanations + scoring</li>
        <li>📝 Mock Exams — graded with feedback</li>
        <li>💬 Ask Zentra — your AI tutor anytime</li>
      </ul>
      <br>
      <a class="subscribe-btn" href="https://zentraai.lemonsqueezy.com/buy/XXXXXXXX" target="_blank">
        🚀 Subscribe Now
      </a>
      <div class="bubble" style="margin-top:20px;font-size:15px;line-height:1.5;text-align:left;">
        <b>Why Zentra?</b><br/>
        Tutors cost $$$ and still don’t scale. Zentra gives you 24/7 AI support, <br/>
        instant feedback, and tools to prep smarter, not harder. <br/>
        GenZ punchline: *Less grind. More brain.*
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
    if not key:
        st.error("Missing OPENAI_API_KEY in Streamlit Secrets."); st.stop()
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
    st.markdown("## 🌟 Zentra Toolkit")
    st.markdown("### How Zentra helps you")
    st.write("- Turn notes into summaries & flashcards\n- Drill with quizzes and get instant feedback\n- Sit mock exams with grading & tips\n- Ask Zentra anything, anytime")
    st.markdown("### 📂 History")
    st.caption("Recent Quizzes:"); st.write(st.session_state.history_quiz or "—")
    st.caption("Recent Mock Exams:"); st.write(st.session_state.history_mock or "—")
    st.markdown("---"); st.caption("⚠️ AI-generated help. Verify before exams.")

# ---------- HERO ----------
st.markdown('<div class="hero"><h1>⚡ Zentra — Your Study Buddy</h1><p>Smarter notes → Better recall → Higher scores.</p></div>', unsafe_allow_html=True)

# ---------- MAIN ----------
col_main,col_chat=st.columns([3,1.4],gap="large")
with col_main:
    st.markdown('<div class="section-title">📁 Upload Your Notes</div>', unsafe_allow_html=True)
    cu,cm=st.columns([3,2],vertical_alignment="bottom")
    with cu:
        uploaded=st.file_uploader("Upload file",type=["pdf","docx","txt","png","jpg","jpeg"],label_visibility="collapsed")
        pasted=st.text_area("Paste your notes here…",height=150,label_visibility="visible")
    out_area=st.container()

    st.markdown('<div class="section-title">✨ Study Tools</div>', unsafe_allow_html=True)
    st.markdown('<div class="tool-row">',unsafe_allow_html=True)
    c1,c2,c3,c4,c5=st.columns(5)
    go_summary=c1.button("📄 Summaries", help="Generate exam-ready bullet summaries")
    go_cards=c2.button("🧠 Flashcards", help="Test recall with Q/A flashcards")
    go_quiz=c3.button("🎯 Quizzes", help="MCQs with instant scoring & feedback")
    go_mock=c4.button("📝 Mock Exams", help="Full exam: MCQ, short, long, fill. Graded.")
    open_chat=c5.button("💬 Ask Zentra", help="Chat directly with your AI tutor")
    st.markdown('</div>',unsafe_allow_html=True)

    if go_summary: st.session_state.pending_tool="summary"; st.rerun()
    if go_cards: st.session_state.pending_tool="cards"; st.rerun()
    if go_quiz: st.session_state.pending_tool="quiz"; st.rerun()
    if go_mock: st.session_state.pending_tool="mock"; st.rerun()
    if open_chat: st.session_state.chat_open=True; st.rerun()

    if st.session_state.pending_tool:
        text,_=ensure_notes(pasted,uploaded)
        choice=st.radio("How should Zentra process your file?",["Text only","Text + Images/Diagrams"])
        if st.button(f"Continue with {st.session_state.pending_tool.title()}"):
            tool=st.session_state.pending_tool
            st.session_state.pending_tool=None
            if tool=="summary":
                with st.spinner("Generating summary…"):
                    out=ask_llm(f"Summarize notes into exam bullets.\n\nNotes:\n{text}")
                out_area.subheader("✅ Summary"); out_area.markdown(out or "_(empty)_")
            elif tool=="cards":
                with st.spinner("Generating flashcards…"):
                    out=ask_llm(f"Make Q/A flashcards. Hide answers until revealed.\n\nNotes:\n{text}")
                out_area.subheader("🧠 Flashcards"); out_area.markdown(out or "_(empty)_")
            elif tool=="quiz":
                with st.spinner("Building quiz…"):
                    n=adaptive_quiz_count(text)
                    out=ask_llm(f"Create {n} MCQs (A–D). Hide answers until end. Score out of {n}. Give feedback for wrong answers.\n\nNotes:\n{text}")
                st.session_state.history_quiz.append(st.session_state.last_title)
                out_area.subheader("🎯 Quiz"); out_area.markdown(out or "_(empty)_")
            elif tool=="mock":
                with st.form("mock_form"):
                    st.write("### Mock Exam")
                    raw=ask_llm(f"Create a mock exam: 5 MCQs, 2 short, 1 long, 2 fill-in. Provide correct answers separately for grading.\n\nNotes:\n{text}")
                    st.markdown(raw)
                    mcq_ans=[st.radio(f"MCQ {i+1}",["A","B","C","D"]) for i in range(5)]
                    short_ans=[st.text_area(f"Short {i+1}") for i in range(2)]
                    long_ans=st.text_area("Long Answer")
                    fill_ans=[st.text_input(f"Fill {i+1}") for i in range(2)]
                    if st.form_submit_button("Submit Mock"):
                        result=ask_llm(f"Grade this exam out of 100 with feedback:\nMCQs {mcq_ans}\nShort {short_ans}\nLong {long_ans}\nFill {fill_ans}\n\nNotes:\n{text}")
                        st.success("✅ Graded"); st.markdown(result)
                        st.session_state.history_mock.append(f"{st.session_state.last_title} — graded")

# ---------- CHAT ----------
with col_chat:
    if st.session_state.chat_open:
        st.markdown("### 💬 Ask Zentra")
        if st.button("Close"): st.session_state.chat_open=False; st.rerun()
        if st.button("Clear"): st.session_state.messages=[]; st.rerun()

        chat_html = "<div class='chat-box' id='chat-box'>"
        for m in st.session_state.messages:
            role = "🧑‍🎓 You" if m["role"]=="user" else "🤖 Zentra"
            chat_html += f"<p><b>{role}:</b> {m['content']}</p>"
        chat_html += "</div><script>var box=document.getElementById('chat-box');box.scrollTop=box.scrollHeight;</script>"
        st.markdown(chat_html, unsafe_allow_html=True)

        q=st.chat_input("Ask Zentra…")
        if q:
            st.session_state.messages.append({"role":"user","content":q})
            ans=ask_llm(f"You are Zentra.\nNotes:{st.session_state.notes_text}\n\nUser:{q}")
            st.session_state.messages.append({"role":"assistant","content":ans})
            st.rerun()
