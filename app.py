# app.py — Zentra (final, polished, all-in-one)
# - Paywall with clean background + pro subscribe button + dev login
# - Fancy collapsible sidebar + history with delete
# - Upload area centered; no extra boxes/tips
# - Text vs Text+Images choice wired to backend (PDF diagrams considered)
# - Summaries / Flashcards / Quizzes / Mock Exams: interactive + graded
# - Ask Zentra: proper chatbox, independent of notes (toggle available)

import os, io, base64, tempfile, math
from typing import List, Tuple, Dict, Any
from dataclasses import dataclass
from PIL import Image
import streamlit as st
from openai import OpenAI

# --------------------------- PAGE CONFIG ---------------------------
st.set_page_config(
    page_title="Zentra — Your Study Buddy",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --------------------------- GLOBAL STYLE --------------------------
st.markdown("""
<style>
/* reset cruft */
a[class*="viewerBadge"], div[class*="viewerBadge"], #ViewerBadgeContainer{display:none!important;}
footer{visibility:hidden;height:0}
.block-container{padding-top:0.5rem; padding-bottom:3rem; max-width:1200px;}

/* gradient app bg (also for paywall empty space) */
html, body, [data-testid="stAppViewContainer"]{
  background:
    radial-gradient(1200px 600px at -10% -10%, rgba(45,74,255,.12), transparent 60%),
    radial-gradient(1000px 500px at 110% -10%, rgba(105,0,255,.12), transparent 60%),
    linear-gradient(180deg, #0a0e16, #0a0e16);
}

/* HERO */
.hero{
  background: linear-gradient(90deg,#6f31ff 0%,#2a7dff 100%);
  border-radius: 18px; color:#fff; padding:26px 28px; margin:18px 0 10px;
  box-shadow: 0 8px 30px rgba(0,0,0,.35);
}
.hero h1{margin:0; font-size:34px; font-weight:800;}
.hero p{margin:6px 0 0; opacity:.95}

/* PAYWALL CARD */
.paywrap{display:flex; align-items:center; justify-content:center; padding:32px 10px;}
.paycard{
  width: min(860px, 92vw);
  background: linear-gradient(170deg, rgba(40,70,190,.35), rgba(30,40,70,.15));
  border: 1px solid rgba(255,255,255,.08);
  border-radius: 22px; padding: 34px 30px; color:#e9eefc;
  box-shadow: 0 16px 60px rgba(0,0,0,.45);
}
.paytitle{font-size:42px; font-weight:900; letter-spacing:.3px; margin:0 0 8px;}
.paystrap{display:flex; gap:12px; flex-wrap:wrap; align-items:center; opacity:.95; margin-bottom:18px;}
.badge{border:1px solid rgba(255,255,255,.18); padding:6px 10px; border-radius:999px; font-size:13px; background:rgba(255,255,255,.06);}
.list{background: rgba(5,10,20,.45); border:1px solid rgba(255,255,255,.08); border-radius:18px; padding:18px 18px; margin:16px 0 22px;}
.list li{margin:8px 0;}

/* Subscribe button — strong, dark, credible */
.primary-btn{
  background: linear-gradient(180deg,#2d7cff,#1b54f2);
  border: 1px solid #0e38b8;
  color:#fff; font-weight:800; letter-spacing:.2px;
  padding:14px 22px; border-radius:12px; text-decoration:none; display:inline-block;
  box-shadow: 0 8px 26px rgba(29,88,255,.28);
  transition: transform .04s ease-in-out, box-shadow .2s;
}
.primary-btn:hover{ transform: translateY(-1px); box-shadow: 0 10px 30px rgba(29,88,255,.38); }

/* secondary button */
.secondary-btn{
  background: transparent; border:1px solid rgba(255,255,255,.25); color:#e9eefc;
  padding:12px 18px; border-radius:12px; text-decoration:none; display:inline-block;
}

/* Upload block */
.upload-card{
  background:#0e1117; border:1px solid #263147; border-radius:16px; padding:12px 14px;
}

/* tool buttons */
.tool-row .stButton>button{
  width:100%; border-radius:12px; padding:12px 16px; font-weight:800;
  color:#e7ecfb; background:#101726; border:1px solid #2b3a54;
}
.tool-row .stButton>button:hover{background:#152037; border-color:#3b4f77}

/* Output area fixed so layout doesn't jump */
.output{
  background:#0e1117; border:1px solid #23314c; border-radius:16px; padding:16px; min-height:160px;
}

/* Chat */
.chatbox{max-height:420px; overflow-y:auto; padding:14px; background:#0e1117;
  border:1px solid #23314c; border-radius:16px;}
.msg{margin:.3rem 0;}
.msg .from{opacity:.7; margin-right:.35rem}

/* Sidebar fancy card */
.sb-card{
  background:#0f1422; border:1px solid #26324b; border-radius:14px; padding:14px; margin-bottom:10px;
}
.sb-title{font-weight:900; font-size:18px; display:flex; gap:.5rem; align-items:center;}
.sb-chip{font-size:12px; padding:2px 8px; border-radius:999px; background:#131b2d; border:1px solid #2b3a54;}

/* radio line under process bar */
.process-bar{border:1px solid #2b3a54; border-radius:12px; padding:8px 10px; margin:10px 0 6px; background:#0e1117;}
</style>
""", unsafe_allow_html=True)

# --------------------------- STATE ---------------------------
ss = st.session_state
ss.setdefault("dev_unlocked", False)
ss.setdefault("chat_open", False)
ss.setdefault("messages", [])
ss.setdefault("history_quiz", [])
ss.setdefault("history_mock", [])
ss.setdefault("notes_text", "")
ss.setdefault("last_title", "Untitled")
ss.setdefault("pending_tool", None)          # "summary","cards","quiz","mock"
ss.setdefault("process_choice", None)        # "text" or "vision"
ss.setdefault("uploaded_blob", None)         # raw bytes of last upload
ss.setdefault("uploaded_name", None)
ss.setdefault("extracted_images", [])        # cached images from last upload (PIL)
ss.setdefault("use_notes_in_chat", False)

# --------------------------- OPENAI ---------------------------
def _client() -> OpenAI:
    key = st.secrets.get("OPENAI_API_KEY")
    if not key:
        st.error("Missing OPENAI_API_KEY in Streamlit secrets.")
        st.stop()
    os.environ["OPENAI_API_KEY"] = key
    return OpenAI()

MODEL_TEXT = "gpt-4o-mini"
MODEL_VISION = "gpt-4o-mini"

def llm_text(prompt: str, system: str = "You are Zentra, a precise and supportive study buddy. Be concise and clear.") -> str:
    r = _client().chat.completions.create(
        model=MODEL_TEXT,
        messages=[{"role":"system","content":system},{"role":"user","content":prompt}],
        temperature=0.35
    )
    return (r.choices[0].message.content or "").strip()

def llm_vision(prompt: str, images_b64: List[str]) -> str:
    content: List[Dict[str,Any]] = [{"type":"text","text":prompt}]
    for b64 in images_b64[:8]:  # cap to avoid huge requests
        content.append({"type":"image_url","image_url":{"url":f"data:image/png;base64,{b64}"}})
    r = _client().chat.completions.create(
        model=MODEL_VISION,
        messages=[{"role":"user","content":content}],
        temperature=0.35
    )
    return (r.choices[0].message.content or "").strip()

# --------------------------- FILE PARSE ---------------------------
def read_file(uploaded) -> Tuple[str, List[Image.Image]]:
    """Return text and extracted images (PIL)."""
    if not uploaded: return "", []
    name = uploaded.name.lower()
    data = uploaded.read()
    ss.uploaded_blob = data
    ss.uploaded_name = uploaded.name
    text = ""
    imgs: List[Image.Image] = []

    if name.endswith(".txt"):
        text = data.decode("utf-8","ignore")

    elif name.endswith(".pdf"):
        # Text via pypdf
        try:
            from pypdf import PdfReader
            pdf = PdfReader(io.BytesIO(data))
            text = "\n".join([(p.extract_text() or "") for p in pdf.pages])
            # Try to extract images from XObjects (no poppler needed)
            for page in pdf.pages:
                try:
                    res = page["/Resources"]
                    if "/XObject" in res:
                        xobjs = res["/XObject"].get_object()
                        for obj in xobjs:
                            xobj = xobjs[obj]
                            if xobj.get("/Subtype") == "/Image":
                                size = (xobj.get("/Width"), xobj.get("/Height"))
                                data_img = xobj.get_data()
                                color_space = xobj.get("/ColorSpace")
                                mode = "RGB" if color_space in ["/DeviceRGB", "/ICCBased"] else "P"
                                try:
                                    img = Image.frombytes(mode, size, data_img)
                                except Exception:
                                    # fallback via PIL open
                                    img = Image.open(io.BytesIO(data_img))
                                imgs.append(img.convert("RGB"))
                except Exception:
                    pass
        except Exception:
            text = ""

    elif name.endswith(".docx"):
        try:
            import docx2txt
            with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
                tmp.write(data); tmp.flush()
                text = docx2txt.process(tmp.name)
        except Exception:
            text = ""

    elif name.endswith((".png",".jpg",".jpeg")):
        try:
            img = Image.open(io.BytesIO(data)).convert("RGB")
            imgs.append(img)
        except Exception:
            pass
    else:
        text = data.decode("utf-8","ignore")

    return (text or "").strip(), imgs

def images_to_b64(imgs: List[Image.Image]) -> List[str]:
    out = []
    for im in imgs:
        buf = io.BytesIO()
        im.save(buf, format="PNG")
        out.append(base64.b64encode(buf.getvalue()).decode("utf-8"))
    return out

# --------------------------- PAYWALL ---------------------------
def show_paywall():
    st.markdown("""
<div class="paywrap">
  <div class="paycard">
    <div class="paytitle">⚡ Zentra — AI Study Buddy</div>
    <div class="paystrap">
      <span>Unlock your Study Buddy for <b>$5.99/month</b></span>
      <span class="badge">3-day free trial</span>
      <span class="badge">Cancel anytime</span>
    </div>
    <div class="list">
      <ul>
        <li>📄 Smart Summaries → exam-ready notes</li>
        <li>🧠 Flashcards → active recall Q/A</li>
        <li>🎯 Quizzes → MCQs with instant scoring & explanations</li>
        <li>📝 Mock Exams → MCQ + short + long + fill-in, graded with feedback</li>
        <li>💬 Ask Zentra → your on-demand tutor</li>
      </ul>
    </div>
    <div style="display:flex; gap:12px; align-items:center;">
      <a class="primary-btn" href="https://zentraai.lemonsqueezy.com/buy/XXXXXXXX" target="_blank">Subscribe Now</a>
      <a class="secondary-btn" href="https://zentraai.lemonsqueezy.com/buy/XXXXXXXX" target="_blank">Secure checkout</a>
    </div>
    <div class="list" style="margin-top:18px;">
      <b>How Zentra helps you</b>
      <ul>
        <li>Cut revision time with concise notes that actually cover exam points</li>
        <li>Practice targeted quizzes & sit graded mocks to spot weak topics</li>
        <li>Ask anything, anytime — like a friendly tutor on demand</li>
      </ul>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

    if st.button("🚪 Dev Login (Temp)"):
        ss.dev_unlocked = True
        st.experimental_rerun()

# --------------------------- HELPERS ---------------------------
def ensure_notes(pasted, uploaded):
    txt = (pasted or "").strip()
    imgs: List[Image.Image] = []

    if uploaded:
        text_file, images = read_file(uploaded)
        if text_file:
            txt = (txt + "\n" + text_file).strip() if txt else text_file
        if images:
            imgs = images
        ss.last_title = uploaded.name

    ss.notes_text = txt
    ss.extracted_images = imgs

def start_request(tool: str):
    """Begin a request: ask for process choice if a file is uploaded with images/potential diagrams; else run directly."""
    ss.pending_tool = tool
    # If no upload and only pasted notes -> no process choice needed
    if not ss.uploaded_blob:
        ss.process_choice = "text"
    else:
        # if we have extracted images, let user choose; else force text
        ss.process_choice = None if (ss.extracted_images) else "text"

def continue_request():
    """Run the pending tool using the selected process choice."""
    if not ss.pending_tool: return
    choice = ss.process_choice or "text"
    text = ss.notes_text
    imgs = ss.extracted_images if choice == "vision" else []

    # unify prompt helper
    def call_smart(prompt_text: str) -> str:
        if choice == "vision" and imgs:
            return llm_vision(prompt_text, images_to_b64(imgs))
        else:
            return llm_text(prompt_text)

    out = st.container()
    with out:
        if ss.pending_tool == "summary":
            with st.spinner("Generating summary…"):
                prompt = f"Summarize into clear exam-ready bullet points. Cover key definitions, formulas, steps, and examples.\n\nNOTES:\n{text[:20000]}"
                res = call_smart(prompt)
            st.subheader("✅ Summary"); st.markdown(res or "_(empty)_")

        elif ss.pending_tool == "cards":
            with st.spinner("Creating flashcards…"):
                prompt = ("Create concise Q/A flashcards from these notes. "
                          "Return JSON with a list `cards`, where each item has `q` and `a`. "
                          "8–16 cards. Keep answers short.")
                res = call_smart(prompt + f"\n\nNOTES:\n{text[:20000]}")
            cards: List[Dict[str,str]] = []
            try:
                import json
                cards = json.loads(res if res.strip().startswith("{") else
                                   res[res.find("{"): res.rfind("}")+1])["cards"]
            except Exception:
                # fallback split
                for chunk in res.split("\n\n"):
                    if ":" in chunk:
                        q = chunk.split("\n")[0]
                        a = "\n".join(chunk.split("\n")[1:])
                        cards.append({"q":q.strip(), "a":a.strip()})
            st.subheader("🧠 Flashcards")
            for i, c in enumerate(cards[:20]):
                key = f"reveal_{i}"
                col1, col2 = st.columns([4,1])
                with col1: st.markdown(f"**Q{i+1}.** {c.get('q','')}")
                with col2:
                    if st.button("Reveal", key=key):
                        ss[key] = True
                if ss.get(key): st.info(c.get("a",""))

        elif ss.pending_tool == "quiz":
            with st.spinner("Building quiz…"):
                qn = max(6, min(16, len(text.split())//160))
                prompt = (f"Create {qn} multiple-choice questions (A–D) from the notes. "
                          "Return strict JSON: {\"questions\":[{\"q\":\"...\",\"choices\":[\"A) ...\",\"B) ...\",\"C) ...\",\"D) ...\"],\"answer\":\"A\",\"explanation\":\"...\"}, ...]}")
                res = call_smart(prompt + f"\n\nNOTES:\n{text[:20000]}")
            import json
            questions = []
            try:
                j = json.loads(res if res.strip().startswith("{") else res[res.find("{"):res.rfind("}")+1])
                questions = j["questions"]
            except Exception:
                st.error("Couldn't parse quiz. Try again.")
                questions = []

            st.subheader("🎯 Quiz")
            answers = []
            for i, q in enumerate(questions):
                st.markdown(f"**Q{i+1}. {q['q']}**")
                picked = st.radio("", ["A","B","C","D"], horizontal=True, key=f"quiz_{i}")
                answers.append(picked)

            if st.button("Submit Quiz"):
                correct = 0
                wrongs = []
                for i, q in enumerate(questions):
                    if answers[i] == q["answer"]:
                        correct += 1
                    else:
                        wrongs.append((i,q))
                score = round((correct/len(questions))*100)
                st.success(f"Score: **{score}** / 100")
                if wrongs:
                    with st.expander("Review mistakes"):
                        for i,q in wrongs:
                            st.markdown(f"- **Q{i+1}** Correct: **{q['answer']}**  \nExplanation: {q.get('explanation','')}")
                ss.history_quiz.append(f"{ss.last_title} — {score}/100")

        elif ss.pending_tool == "mock":
            st.subheader("📝 Mock Exam")
            diff = st.radio("Select difficulty", ["Easy","Standard","Hard"], horizontal=True)
            if st.button("Prepare mock"):
                with st.spinner("Preparing mock…"):
                    target_total = 60 if diff=="Easy" else (80 if diff=="Standard" else 100)
                    prompt = (
                        "Create a mock exam with: 6 MCQs (A–D), 2 short-answer, 1 long-answer, 2 fill-in.\n"
                        "Return strict JSON:\n"
                        "{ \"mcq\":[{\"q\":\"...\",\"choices\":[\"A) ...\",\"B) ...\",\"C) ...\",\"D) ...\"],\"answer\":\"B\",\"explanation\":\"...\"}, ...],"
                        "  \"short\":[{\"q\":\"...\",\"answer\":\"...\"}, ...],"
                        "  \"long\":[{\"q\":\"...\",\"answer\":\"...\"}],"
                        "  \"fill\":[{\"q\":\"...\",\"answer\":\"...\"}, ...] }"
                    )
                    res = call_smart(prompt + f"\n\nNOTES:\n{text[:20000]}")
                import json
                try:
                    mk = json.loads(res if res.strip().startswith("{") else res[res.find("{"):res.rfind("}")+1])
                except Exception:
                    st.error("Couldn't parse mock. Try again.")
                    return

                with st.form("mock_form"):
                    st.caption("Answer all sections below, then submit for grading.")
                    picks = []
                    for i, q in enumerate(mk.get("mcq",[])[:12]):
                        st.markdown(f"**MCQ {i+1}. {q['q']}**")
                        picks.append(st.radio("", ["A","B","C","D"], horizontal=True, key=f"mk_mcq_{i}"))

                    s_ans = []
                    for i, q in enumerate(mk.get("short",[])[:4]):
                        s_ans.append(st.text_area(f"Short {i+1}: {q['q']}", key=f"mk_short_{i}"))

                    l_ans = []
                    for i, q in enumerate(mk.get("long",[])[:2]):
                        l_ans.append(st.text_area(f"Long {i+1}: {q['q']}", key=f"mk_long_{i}"))

                    f_ans = []
                    for i, q in enumerate(mk.get("fill",[])[:6]):
                        f_ans.append(st.text_input(f"Fill-in {i+1}: {q['q']}", key=f"mk_fill_{i}"))

                    submitted = st.form_submit_button("Submit Mock")
                    if submitted:
                        # Compute scale based on size of mock
                        total_items = len(picks) + len(s_ans) + len(l_ans) + len(f_ans)
                        scale = min(100, max(40, math.ceil(total_items/2)*10))  # multiple of 10, reasonable range

                        # MCQ auto-score
                        correct = 0
                        for i, q in enumerate(mk["mcq"]):
                            if i < len(picks) and picks[i] == q["answer"]:
                                correct += 1
                        mcq_score = round((correct/max(1,len(mk["mcq"][:len(picks)])))* (scale*0.4))

                        # Rest via LLM grading
                        grading_prompt = f"""
You are a strict but fair examiner.
Grade SHORT, LONG, FILL answers against the official answers.
Return JSON: {{"short":{{"score":X,"feedback":"..."}}, "long":{{"score":Y,"feedback":"..."}}, "fill":{{"score":Z,"feedback":"..."}}, "overall_feedback":"..."}}.
The maximum combined score (short+long+fill) should be {scale - mcq_score}.
OFFICIAL ANSWERS:
SHORT: {mk.get("short",[])}
LONG: {mk.get("long",[])}
FILL: {mk.get("fill",[])}
STUDENT:
SHORT: {s_ans}
LONG: {l_ans}
FILL: {f_ans}
"""
                        try:
                            import json
                            g = llm_text(grading_prompt, system="Grade fairly. Be concise.")
                            gjson = json.loads(g if g.strip().startswith("{") else g[g.find("{"):g.rfind("}")+1])
                        except Exception:
                            gjson = {"short":{"score": int((scale-mcq_score)*0.3), "feedback":"—"},
                                     "long":{"score": int((scale-mcq_score)*0.5), "feedback":"—"},
                                     "fill":{"score": int((scale-mcq_score)*0.2), "feedback":"—"},
                                     "overall_feedback":"—"}

                        total = mcq_score + gjson["short"]["score"] + gjson["long"]["score"] + gjson["fill"]["score"]
                        total = min(scale, total)
                        st.success(f"Final Score: **{total} / {scale}**")
                        with st.expander("Breakdown & Feedback", expanded=True):
                            st.write(f"MCQ: {mcq_score}")
                            st.write(f"Short: {gjson['short']['score']} — {gjson['short']['feedback']}")
                            st.write(f"Long: {gjson['long']['score']} — {gjson['long']['feedback']}")
                            st.write(f"Fill-in: {gjson['fill']['score']} — {gjson['fill']['feedback']}")
                            st.write(f"Overall: {gjson.get('overall_feedback','')}")
                        ss.history_mock.append(f"{ss.last_title} — {total}/{scale}")

    # reset pending
    ss.pending_tool = None
    ss.process_choice = None


# --------------------------- APP ---------------------------
if not ss.dev_unlocked:
    show_paywall()
    st.stop()

# --------- HERO ---------
st.markdown('<div class="hero"><h1>⚡ Zentra — Your Study Buddy</h1><p>Smarter notes → Better recall → Higher scores.</p></div>', unsafe_allow_html=True)

# --------- SIDEBAR (fancy + history + delete) ---------
with st.sidebar:
    st.markdown('<div class="sb-card"><div class="sb-title">🧰 Zentra Toolkit <span class="sb-chip">study smarter</span></div><div style="opacity:.9; margin-top:6px;">Turn your notes into a complete toolkit: summaries, flashcards, quizzes, mocks, and a tutor — all in one place.</div></div>', unsafe_allow_html=True)
    with st.expander("💡 How Zentra helps you"):
        st.markdown("- Cut revision time with **concise notes** that still cover the exam.\n- Drill with **smart quizzes** and get instant explanations.\n- Sit **graded mock exams** and learn exactly what to fix.\n- Ask anything, anytime — like a personal tutor.")
    st.markdown("### 🗂 History")
    st.caption("Recent Quizzes:"); st.write(ss.history_quiz or "—")
    st.caption("Recent Mock Exams:"); st.write(ss.history_mock or "—")
    colA, colB = st.columns(2)
    if colA.button("Clear quizzes"):
        ss.history_quiz = []
    if colB.button("Clear mocks"):
        ss.history_mock = []
    st.markdown("---")
    st.caption("AI-generated help. Verify before exams.")

# --------- MAIN LAYOUT ---------
col_main, col_chat = st.columns([3, 1.35], gap="large")

with col_main:
    st.markdown("### 📁 Upload Your Notes")
    up_left, _ = st.columns([3,1])
    with up_left:
        uploaded = st.file_uploader("Drag and drop file here", type=["pdf","docx","txt","png","jpg","jpeg"], label_visibility="collapsed")
        pasted = st.text_area("Paste your notes here…", height=180, label_visibility="collapsed")

    # Prepare state from inputs
    if uploaded or pasted:
        ensure_notes(pasted, uploaded)

    # Tool buttons
    st.markdown("### ✨ Study Tools")
    st.markdown('<div class="tool-row">', unsafe_allow_html=True)
    c1,c2,c3,c4,c5 = st.columns(5)
    go_summary = c1.button("📄 Summaries", help="Exam-ready bullets.")
    go_cards   = c2.button("🧠 Flashcards", help="Active recall Q/A (tap to reveal).")
    go_quiz    = c3.button("🎯 Quizzes", help="MCQs with instant scoring & explanations.")
    go_mock    = c4.button("📝 Mock Exams", help="Full exam: MCQ + short + long + fill. Graded.")
    open_chat  = c5.button("💬 Ask Zentra", help="Tutor on demand.")
    st.markdown('</div>', unsafe_allow_html=True)

    # Start requests (defer execution until we have process choice)
    if go_summary: start_request("summary")
    if go_cards:   start_request("cards")
    if go_quiz:    start_request("quiz")
    if go_mock:    start_request("mock")
    if open_chat:  ss.chat_open = True

    # If a process choice is needed, ask it (without shifting layout)
    if ss.pending_tool and ss.process_choice is None:
        st.markdown('<div class="process-bar">', unsafe_allow_html=True)
        st.markdown(f"**How should Zentra process your file?**  _(for: {ss.uploaded_name})_")
        colx, coly = st.columns([1,3])
        with coly:
            pick = st.radio("", ["Text only", "Text + Images/Diagrams"], horizontal=True, index=0, label_visibility="collapsed")
        st.markdown('</div>', unsafe_allow_html=True)
        if st.button(f"Continue → {ss.pending_tool.capitalize()}"):
            ss.process_choice = "vision" if pick.startswith("Text +") else "text"
            st.experimental_rerun()

    # Output container — fixed position so UI doesn’t jump down
    with st.container():
        st.markdown('<div class="output">', unsafe_allow_html=True)
        if ss.pending_tool and ss.process_choice:  # run the tool now
            continue_request()
        else:
            st.caption("Results will appear here.")
        st.markdown('</div>', unsafe_allow_html=True)

# --------- CHAT ---------
with col_chat:
    if ss.chat_open:
        st.markdown("### 💬 Ask Zentra")
        topc1, topc2 = st.columns(2)
        if topc1.button("Close"): ss.chat_open=False; st.experimental_rerun()
        if topc2.button("Clear"): ss.messages=[]; st.experimental_rerun()
        ss.use_notes_in_chat = st.toggle("Use my notes context", value=False, help="Off by default so chat stays independent of uploaded files.")

        # Chat history box
        chat_html = '<div class="chatbox" id="chatbox">'
        for m in ss.messages:
            who = "🧑‍🎓 You" if m["role"]=="user" else "🤖 Zentra"
            chat_html += f'<div class="msg"><span class="from">{who}:</span>{m["content"]}</div>'
        chat_html += "</div><script>var b=document.getElementById('chatbox'); if(b){b.scrollTop=b.scrollHeight;}</script>"
        st.markdown(chat_html, unsafe_allow_html=True)

        q = st.chat_input("Ask Zentra…")
        if q:
            ss.messages.append({"role":"user","content":q})
            try:
                if ss.use_notes_in_chat and ss.notes_text:
                    ans = llm_text(f"Use the NOTES as extra context. If the user's question is unrelated, ignore the notes.\n\nNOTES:\n{ss.notes_text[:12000]}\n\nUSER: {q}")
                else:
                    ans = llm_text(q, system="You are Zentra, a helpful study tutor. Answer clearly and briefly unless asked for detail.")
            except Exception as e:
                ans = f"Error: {e}"
            ss.messages.append({"role":"assistant","content":ans})
            st.experimental_rerun()
