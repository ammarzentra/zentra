# app.py — Zentra: full build with image-aware tools, quiz/mock grading, polished UI

import os, io, base64, tempfile
from typing import List, Tuple, Dict, Any
import json
import streamlit as st
from openai import OpenAI

# -------------------- PAGE CONFIG --------------------
st.set_page_config(
    page_title="Zentra — Your Study Buddy",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -------------------- GLOBAL STYLES --------------------
st.markdown("""
<style>
a[class*="viewerBadge"], div[class*="viewerBadge"], #ViewerBadgeContainer{display:none!important;}
footer{visibility:hidden;height:0}
.block-container{padding-top:0.8rem; padding-bottom:3rem; max-width:1200px;}
/* Paywall */
.page-bg{
  position:fixed; inset:0; z-index:-1;
  background: radial-gradient(1200px 600px at 20% -10%, rgba(59,130,246,.25), transparent 60%),
              radial-gradient(1000px 500px at 120% 10%, rgba(147,51,234,.22), transparent 60%),
              linear-gradient(180deg,#0b1020 0%,#0a0f1a 100%);
}
.paywall{
  background: linear-gradient(135deg,#121a2b 0%,#0c1220 100%);
  border-radius: 18px; padding: 48px 28px; color:#eaf0ff;
  text-align:center; margin:40px auto; max-width:760px;
  box-shadow: 0 12px 36px rgba(0,0,0,.55), inset 0 0 0 1px rgba(255,255,255,.04);
}
.paywall h1{margin:0 0 .4rem 0; font-size:46px; font-weight:850; letter-spacing:.2px;}
.paywall-sub{margin:.25rem 0 1.2rem; opacity:.9; font-size:16px;}
.badges{display:flex; gap:12px; justify-content:center; margin-bottom:18px; flex-wrap:wrap}
.badge{padding:6px 12px; border-radius:24px; font-size:13px; border:1px solid rgba(255,255,255,.12);}
.paycard{background:#0e1626; border:1px solid #1f2a40; border-radius:16px; padding:18px; margin:0 auto 18px; max-width:560px; text-align:left}
.paycard li{margin:8px 0}
.primary-btn{
  background: linear-gradient(180deg,#1e3a8a,#1e40af);
  border: 1px solid #1d4ed8;
  color:#f9fafb; font-weight:800; letter-spacing:.3px;
  padding:14px 28px; border-radius:12px; text-decoration:none; display:inline-block; font-size:17px;
  box-shadow: 0 4px 14px rgba(29,78,216,.45); transition: all .15s ease-in-out;
}
.primary-btn:hover{ background: linear-gradient(180deg,#1e40af,#1e3a8a); transform: translateY(-1px); box-shadow: 0 8px 22px rgba(29,78,216,.55);}
/* In-app hero */
.hero{background:linear-gradient(90deg,#6a11cb 0%,#2575fc 100%); padding:22px; border-radius:16px; color:#fff; margin:10px 0 16px; text-align:center;}
.hero h1{margin:0;font-size:34px;font-weight:850;}
.hero p{margin:6px 0 0;opacity:.92}
/* Sections */
.section-title{font-weight:850;font-size:22px;margin:10px 0 14px; display:flex; align-items:center; gap:.5rem}
.big-uploader .stFileUploader{width:100%}
.big-textarea textarea{min-height:220px}
.tool-row .stButton>button{
  width:100%; border-radius:12px; border:1px solid #2b2f3a;
  padding:10px; background:#10141e; color:#e8ecf7; font-weight:700;
}
.tool-row .stButton>button:hover{background:#141a27; border-color:#3a4252;}
.choice-bar {border:1px solid #283142; border-radius:12px; padding:12px 14px; margin-top:8px;}
/* Chat */
.chat-card{background:#0f1420; border:1px solid #243047; border-radius:14px; padding:12px;}
.chat-box{max-height:420px; overflow-y:auto; padding:6px 10px; border-radius:10px; background:#0b111a; border:1px solid #1f2a3b;}
.chat-msg{margin:6px 0}
.chat-role{opacity:.8;margin-right:.35rem}
.chat-input .stChatInput{margin-top:.5rem}
</style>
<div class="page-bg"></div>
""", unsafe_allow_html=True)

# -------------------- STATE --------------------
ss = st.session_state
defaults = {
    "chat_open": False, "messages": [], "history_quiz": [], "history_mock": [],
    "notes_text": "", "last_title": "Untitled notes",
    "dev_unlocked": False, "pending_tool": "", "process_choice": "",
    "pending_text": "", "pending_images": [], "uploaded_name": ""
}
for k,v in defaults.items():
    if k not in ss: ss[k]=v

# -------------------- OPENAI --------------------
def _client() -> OpenAI:
    key = st.secrets.get("OPENAI_API_KEY")
    if not key:
        st.error("Missing OPENAI_API_KEY in Streamlit Secrets."); st.stop()
    os.environ["OPENAI_API_KEY"] = key
    return OpenAI()

MODEL = "gpt-4o-mini"

def ask_text(prompt: str, system="You are Zentra, a precise, supportive study buddy. Keep answers clear and exam-focused."):
    r = _client().chat.completions.create(
        model=MODEL,
        messages=[{"role":"system","content":system},{"role":"user","content":prompt}],
        temperature=0.35,
    )
    return r.choices[0].message.content.strip()

def ask_vision(prompt: str, images: List[bytes]):
    # Build a multimodal content list: text + up to 6 images (base64 data URLs)
    content: List[Dict[str,Any]] = [{"type":"text","text":prompt}]
    take = min(6, len(images))
    for i in range(take):
        b64 = base64.b64encode(images[i]).decode("utf-8")
        content.append({"type":"image_url","image_url":{"url":f"data:image/png;base64,{b64}"}})
    r = _client().chat.completions.create(
        model=MODEL,
        messages=[{"role":"system","content":"You are Zentra, a precise, supportive study buddy. Read the diagrams carefully and incorporate them."},
                  {"role":"user","content":content}],
        temperature=0.35,
    )
    return r.choices[0].message.content.strip()

# -------------------- FILE PARSING --------------------
def read_text_and_images(uploaded_file) -> Tuple[str, List[Tuple[str, bytes]]]:
    """Return extracted text and list of (name, bytes) images (PNG bytes)."""
    if not uploaded_file: return "", []
    name = uploaded_file.name.lower()
    data = uploaded_file.read()
    text = ""
    images: List[Tuple[str, bytes]] = []

    if name.endswith(".txt"):
        text = data.decode("utf-8","ignore")

    elif name.endswith(".pdf"):
        # Text via PyPDF
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data))
            text = "\n".join([(p.extract_text() or "") for p in reader.pages])
        except Exception:
            text = ""
        # Images via PyMuPDF if available
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(stream=data, filetype="pdf")
            count = 0
            for page in doc:
                for img in page.get_images(full=True):
                    xref = img[0]
                    pix = fitz.Pixmap(doc, xref)
                    img_bytes = pix.tobytes("png")
                    images.append((f"page{page.number}_img{xref}.png", img_bytes))
                    count += 1
                    if count >= 6: break
                if count >= 6: break
        except Exception:
            # No PyMuPDF — fall back silently
            pass

    elif name.endswith(".docx"):
        try:
            import docx2txt
            with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
                tmp.write(data); tmp.flush()
                text = docx2txt.process(tmp.name)
        except Exception:
            text = ""

    elif name.endswith((".png",".jpg",".jpeg")):
        # Treat whole image as a diagram page; no text
        images.append((uploaded_file.name, data))

    else:
        text = data.decode("utf-8","ignore")

    return (text or "").strip(), images

def ensure_notes(pasted: str, uploaded):
    txt = (pasted or "").strip()
    imgs: List[Tuple[str, bytes]] = []
    uploaded_name = ""
    if uploaded:
        t, ii = read_text_and_images(uploaded)
        if t: txt = (txt + "\n" + t).strip() if txt else t
        if ii: imgs = ii
        uploaded_name = uploaded.name
        ss["last_title"] = uploaded.name
    ss["notes_text"] = txt
    ss["uploaded_name"] = uploaded_name
    return txt, [b for _,b in imgs]

def adaptive_quiz_count(txt: str) -> int:
    return max(5, min(20, len(txt.split()) // 180))

# -------------------- PAYWALL --------------------
if not ss.dev_unlocked:
    st.markdown("""
    <div class="paywall">
      <h1>⚡ Zentra — AI Study Buddy</h1>
      <div class="badges">
        <div class="badge">3-day free trial</div>
        <div class="badge">Cancel anytime</div>
      </div>
      <p class="paywall-sub">Unlock your personal AI study buddy for just <b>$5.99/month</b></p>

      <div class="paycard">
        <ul>
          <li>📄 Smart Summaries → exam-ready notes</li>
          <li>🧠 Flashcards → active recall Q/A</li>
          <li>🎯 Quizzes → MCQs with instant scoring & explanations</li>
          <li>📝 Mock Exams → MCQ + short + long + fill-in, graded with feedback</li>
          <li>💬 Ask Zentra → your on-demand tutor</li>
        </ul>
      </div>

      <a class="primary-btn" href="https://zentraai.lemonsqueezy.com/buy/XXXXXXXX" target="_blank">Subscribe Now</a>
      <div style="margin-top:12px;opacity:.75;font-size:13px;">Secure checkout • Student-friendly pricing</div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("🚪 Dev Login (Temp)"):
        ss.dev_unlocked = True
        st.rerun()
    st.stop()

# -------------------- SIDEBAR --------------------
with st.sidebar:
    st.markdown("## 🧰 Zentra Toolkit")
    st.write("Shrink long notes into **summaries**, drill with **quizzes**, build **flashcards**, and sit **mock exams** — all in one place.")
    with st.expander("💡 How Zentra helps you"):
        st.markdown("- Turn long notes into short, complete summaries\n- Find weak topics fast with targeted quizzes\n- Practice graded mocks with feedback\n- Keep momentum with quick flashcards\n- Study smarter, not longer")

    st.markdown("### 📜 History")
    st.caption("Recent Quizzes:")
    if ss.history_quiz:
        for i, item in enumerate(ss.history_quiz[-5:][::-1]):
            st.write(f"• {item}")
        if st.button("Clear quiz history"):
            ss.history_quiz = []; st.rerun()
    else:
        st.write("—")

    st.caption("Recent Mock Exams:")
    if ss.history_mock:
        for i, item in enumerate(ss.history_mock[-5:][::-1]):
            st.write(f"• {item}")
        if st.button("Clear mock history"):
            ss.history_mock = []; st.rerun()
    else:
        st.write("—")

    st.markdown("---")
    st.caption("AI-generated help. Verify before exams.")

# -------------------- HERO --------------------
st.markdown('<div class="hero"><h1>⚡ Zentra — Your Study Buddy</h1><p>Smarter notes → Better recall → Higher scores.</p></div>', unsafe_allow_html=True)

# -------------------- MAIN LAYOUT --------------------
col_main, col_chat = st.columns([3, 1.45], gap="large")

with col_main:
    st.markdown('<div class="section-title">📁 Upload Your Notes</div>', unsafe_allow_html=True)
    up_left, up_right = st.columns([3,2], vertical_alignment="top")
    with up_left:
        uploaded = st.file_uploader("Upload file", type=["pdf","docx","txt","png","jpg","jpeg"], label_visibility="collapsed", key="file_upl")
        pasted = st.text_area("Paste your notes here…", key="paste_notes", placeholder="Paste your notes here…", label_visibility="collapsed",
                              help=None, height=220)
    with up_right:
        st.empty()  # no tip panel

    # -------------------- Study Tools row --------------------
    st.markdown('<div class="section-title">✨ Study Tools</div>', unsafe_allow_html=True)
    st.markdown('<div class="tool-row">', unsafe_allow_html=True)
    c1,c2,c3,c4,c5 = st.columns(5)
    click_summary = c1.button("📄 Summaries")
    click_cards   = c2.button("🧠 Flashcards")
    click_quiz    = c3.button("🎯 Quizzes")
    click_mock    = c4.button("📝 Mock Exams")
    click_chat    = c5.button("💬 Ask Zentra")
    st.markdown('</div>', unsafe_allow_html=True)

    if click_chat:
        ss.chat_open = True
        st.rerun()

    # Prepare gathered notes on demand
    def gather_input() -> Tuple[str, List[bytes]]:
        txt, imgs = ensure_notes(pasted, uploaded)
        return txt, imgs

    # State machine: choose tool → choose process → run
    def choose_process_prompt(filename: str):
        box = st.container()
        with box:
            st.markdown('<div class="choice-bar"></div>', unsafe_allow_html=True)
            st.markdown(f"**How should Zentra process your file?** *(for: {filename})*")
            ss.process_choice = st.radio(
                "", ["Text only", "Text + Images/Diagrams"],
                horizontal=False, label_visibility="collapsed", key="process_choice_radio"
            )
        return box

    def start_tool(tool: str):
        ss.pending_tool = tool
        ss.process_choice = ""
        st.rerun()

    if click_summary: start_tool("summary")
    if click_cards:   start_tool("cards")
    if click_quiz:    start_tool("quiz")
    if click_mock:    start_tool("mock")

    out = st.container()

    # ---------- Tool runners ----------
    def run_summary(text: str, imgs: List[bytes]):
        if ss.process_choice == "Text + Images/Diagrams" and imgs:
            prompt = f"Create a crisp, exam-ready summary. Cover every key definition, formula, step, exception.\n\nNotes:\n{text[:8000]}"
            result = ask_vision(prompt, imgs)
        else:
            result = ask_text(f"Create an exam-ready summary with bullet points only. Be complete & concise.\n\nNotes:\n{text[:12000]}")
        out.subheader("✅ Summary")
        out.markdown(result or "_(empty)_")

    def run_cards(text: str, imgs: List[bytes]):
        if ss.process_choice == "Text + Images/Diagrams" and imgs:
            prompt = f"Make 10–18 flashcards. Each card strictly as: 'Q:' line, then 'A:' line. One concept per card.\nNotes:\n{text[:8000]}"
            raw = ask_vision(prompt, imgs)
        else:
            raw = ask_text(f"Make 10–18 flashcards. Each card strictly as: 'Q:' then 'A:'.\nNotes:\n{text[:12000]}")
        out.subheader("🧠 Flashcards")
        cards = []
        for block in raw.split("\n"):
            if block.strip().lower().startswith(("q:", "q ")): cards.append({"q": block.split(":",1)[1].strip(), "a": ""})
            elif block.strip().lower().startswith(("a:", "a ")):
                if cards: cards[-1]["a"] = block.split(":",1)[1].strip()
        if not cards:
            # Fallback simple split
            parts = [p.strip() for p in raw.split("\n\n") if p.strip()]
            for p in parts:
                if "A:" in p: q,a = p.split("A:",1); cards.append({"q":q.replace("Q:","").strip(),"a":a.strip()})
        for i, card in enumerate(cards[:24]):
            with st.expander(f"Q{i+1}. {card['q']}"):
                st.markdown(f"**Answer:** {card['a'] or '_missing_'}")

    def run_quiz(text: str, imgs: List[bytes]):
        if ss.process_choice == "Text + Images/Diagrams" and imgs:
            prompt = f"""Generate a JSON quiz with fields:
{{
 "questions":[
   {{"q":"...", "choices":["A) ...","B) ...","C) ...","D) ..."], "answer":"A", "explanation":"..."}}
 ]
}}
Make 8–14 good MCQs. Cover all key ideas. Keep JSON valid only. Notes:\n{text[:8000]}"""
            raw = ask_vision(prompt, imgs)
        else:
            prompt = f"""Generate a JSON quiz with fields:
{{
 "questions":[
   {{"q":"...", "choices":["A) ...","B) ...","C) ...","D) ..."], "answer":"A", "explanation":"..."}}
 ]
}}
Make 8–14 strong MCQs. JSON only. Notes:\n{text[:12000]}"""
            raw = ask_text(prompt)
        try:
            data = json.loads(raw)
            questions = data.get("questions", [])
        except Exception:
            # fallback: simple 5 MCQs
            questions = []
        out.subheader("🎯 Quiz")
        if not questions:
            st.warning("Quiz generation failed. Try again.")
            return
        with st.form("quiz_form"):
            selections = []
            for i,q in enumerate(questions):
                st.markdown(f"**Q{i+1}. {q.get('q','')}**")
                choices = q.get("choices", [])
                pick = st.radio("", choices, index=None, key=f"q{i}", label_visibility="collapsed")
                selections.append(pick)
                st.markdown("---")
            submitted = st.form_submit_button("Submit Quiz")
        if submitted:
            score = 0
            breakdown = []
            for i,(q,sel) in enumerate(zip(questions, selections)):
                correct = q.get("answer","").strip()
                # normalize "A) ..." → "A"
                if correct and ")" in correct[:3]: correct = correct.split(")")[0].strip()
                chosen = (sel or "").strip()
                chosen_letter = chosen[:1] if chosen else ""
                ok = (chosen_letter.upper() == correct.upper())
                if ok: score += 1
                breakdown.append((i+1, ok, correct, q.get("explanation","")))
            pct = round(100*score/len(questions))
            st.success(f"Score: **{score}/{len(questions)}** ({pct}%)")
            with st.expander("See explanations"):
                for i, ok, corr, exp in breakdown:
                    st.markdown(f"**Q{i}:** {'✅ Correct' if ok else '❌ Wrong'} — answer: **{corr}**")
                    if exp: st.caption(exp)
            ss.history_quiz.append(f"{ss.last_title} — {pct}%")
            st.rerun()

    def run_mock(text: str, imgs: List[bytes]):
        st.subheader("📝 Mock Exam")
        diff = st.radio("Select difficulty", ["Easy","Standard","Hard"], horizontal=True, key="mock_diff")
        if st.button("Generate Mock"):
            # difficulty affects length/rigor
            prompt_base = f"""Create a {diff} mock exam. Return pure JSON:
{{
 "mcq":[{{"q":"...","choices":["A) ...","B) ...","C) ...","D) ..."],"answer":"A","explanation":"..."}} ...],
 "short":[{{"q":"...","answer":"..."}] ,
 "long":[{{"q":"...","rubric":"key points to expect"}}],
 "fill":[{{"q":"...","answer":"..."}}]
}}
Aim total marks to nearest 10 between 40 and 100 depending on content size. Notes:\n{text[:10000]}
"""
            raw = ask_vision(prompt_base, imgs) if (ss.process_choice=="Text + Images/Diagrams" and imgs) else ask_text(prompt_base)
            try:
                exam = json.loads(raw)
            except Exception:
                st.error("Mock creation failed. Try again."); return
            st.session_state["mock_exam"] = exam
            st.session_state["mock_ready"] = True
            st.rerun()

        if st.session_state.get("mock_ready"):
            exam = st.session_state["mock_exam"]
            mcq = exam.get("mcq", [])[:10]
            short = exam.get("short", [])[:3]
            longq = exam.get("long", [])[:1]
            fill = exam.get("fill", [])[:3]
            total_marks = max(40, min(100, 10*((len(mcq)*3 + len(short)*8 + len(longq)*20 + len(fill)*4)//10)))
            st.caption(f"Full exam: MCQ + short + long + fill. **Submit to be graded out of {total_marks}.**")

            with st.form("mock_form"):
                mcq_sel = []
                for i,q in enumerate(mcq):
                    st.markdown(f"**MCQ {i+1}. {q.get('q','')}**")
                    pick = st.radio("", q.get("choices",[]), index=None, key=f"m_mcq_{i}", label_visibility="collapsed")
                    mcq_sel.append(pick)
                for i,q in enumerate(short):
                    st.markdown(f"**Short {i+1}. {q.get('q','')}**")
                    st.text_area("", key=f"m_short_{i}", label_visibility="collapsed")
                for i,q in enumerate(longq):
                    st.markdown(f"**Long {i+1}. {q.get('q','')}**")
                    st.text_area("", key=f"m_long_{i}", height=180, label_visibility="collapsed")
                for i,q in enumerate(fill):
                    st.markdown(f"**Fill {i+1}. {q.get('q','')}**")
                    st.text_input("", key=f"m_fill_{i}", label_visibility="collapsed")

                submitted = st.form_submit_button("Submit Mock")
            if submitted:
                # Score MCQ locally
                mcq_score = 0
                for i,(q,sel) in enumerate(zip(mcq, mcq_sel)):
                    corr = q.get("answer","").strip()
                    if corr and ")" in corr[:3]: corr = corr.split(")")[0].strip()
                    chosen = (sel or "").strip()
                    chosen_letter = chosen[:1] if chosen else ""
                    if chosen_letter.upper() == corr.upper():
                        mcq_score += 3  # 3 marks each

                # Ask LLM to grade constructed answers succinctly
                answers_short = [st.session_state.get(f"m_short_{i}","") for i in range(len(short))]
                answers_long  = [st.session_state.get(f"m_long_{i}","") for i in range(len(longq))]
                answers_fill  = [st.session_state.get(f"m_fill_{i}","") for i in range(len(fill))]

                grading_prompt = {
                    "instruction": "Grade fairly and concisely. Return JSON with fields: short_scores[], long_scores[], fill_scores[], total_non_mcq, comments.",
                    "rubric": exam,
                    "student_answers": {"short":answers_short, "long":answers_long, "fill":answers_fill}
                }
                raw_grade = ask_text(f"Grade the answers based on rubric. JSON only:\n{json.dumps(grading_prompt)[:12000]}")
                try:
                    g = json.loads(raw_grade)
                except Exception:
                    g = {"short_scores":[0]*len(short),"long_scores":[0]*len(longq),"fill_scores":[0]*len(fill),"total_non_mcq":0,"comments":"(grading failed)"}  # fallback

                # Normalize totals to nearest 10 up to 100
                non_mcq = int(g.get("total_non_mcq", 0))
                total = mcq_score + non_mcq
                total = max(0, min(100, 10*round(total/10)))

                st.success(f"Final Score: **{total}/100**")
                with st.expander("Feedback & Key Points"):
                    st.markdown(g.get("comments",""))
                ss.history_mock.append(f"{ss.last_title} — {total}/100")
                # Reset mock state (keep history)
                st.session_state["mock_ready"] = False
                st.rerun()

    # ---------- Decide what to show ----------
    if ss.pending_tool:
        # We only prompt for process choice when a file/image is uploaded; if only pasted text, skip choice.
        has_upload = bool(uploaded) or ss.uploaded_name
        if has_upload:
            choose_process_prompt(ss.uploaded_name or uploaded.name)
            if st.button(f"Continue → {ss.pending_tool.capitalize()}"):
                ss.process_choice = ss.process_choice or "Text only"
                text, imgs = gather_input()
                ss.pending_text = text
                ss.pending_images = imgs
                st.rerun()
        else:
            # Only pasted text — run directly
            text, imgs = gather_input()
            ss.pending_text, ss.pending_images = text, []
            st.rerun()

    if ss.pending_text:
        # Execute the chosen tool now
        text, imgs = ss.pending_text, ss.pending_images
        tool = ss.pending_tool
        ss.pending_tool = ""
        ss.pending_text = ""  # consume

        if tool == "summary":   run_summary(text, imgs)
        elif tool == "cards":   run_cards(text, imgs)
        elif tool == "quiz":    run_quiz(text, imgs)
        elif tool == "mock":    run_mock(text, imgs)

# -------------------- ASK ZENTRA (independent chat) --------------------
with col_chat:
    if ss.chat_open:
        st.markdown("### 💬 Ask Zentra")
        b1, b2 = st.columns(2)
        if b1.button("Close"): ss.chat_open=False; st.rerun()
        if b2.button("Clear"): ss.messages=[]; st.rerun()

        # Chat box
        with st.container():
            st.markdown('<div class="chat-card">', unsafe_allow_html=True)
            # Scrollable chat
            html = ["<div class='chat-box' id='chat-box'>"]
            for m in ss.messages:
                who = "🧑‍🎓 You" if m["role"]=="user" else "🤖 Zentra"
                html.append(f"<div class='chat-msg'><span class='chat-role'><b>{who}:</b></span>{m['content']}</div>")
            html.append("</div><script>var box=document.getElementById('chat-box');box.scrollTop=box.scrollHeight;</script>")
            st.markdown("\n".join(html), unsafe_allow_html=True)
            # Input
            q = st.chat_input("Ask Zentra…")
            if q:
                ss.messages.append({"role":"user","content":q})
                # Independent of uploaded notes by default
                ans = ask_text(q, system="You are Zentra, a helpful study buddy. Be concise, clear, and friendly.")
                ss.messages.append({"role":"assistant","content":ans})
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
