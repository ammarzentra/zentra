# app.py — Zentra POLISHED FINAL (all tools stable, pro UI, proper flows)
# NOTE: Put OPENAI_API_KEY into Streamlit Secrets before deploying:
# [Settings] → [Secrets] → {"OPENAI_API_KEY":"sk-..."}
# This build keeps your current visuals but fixes: ghost boxes, tool flows, chatbox,
# results rendering, Mock difficulty flow, and button styling. It also attempts to
# consider diagrams when "Text + Images/Diagrams" is chosen (best-effort).

import os, io, base64, tempfile, re, time
from typing import List, Tuple, Optional
import streamlit as st
from openai import OpenAI

# =========================
# PAGE CONFIG + GLOBAL CSS
# =========================
st.set_page_config(
    page_title="Zentra — AI Study Buddy",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
/* ---- Global cleanup ---- */
a[class*="viewerBadge"], div[class*="viewerBadge"], #ViewerBadgeContainer{display:none!important;}
footer{visibility:hidden;height:0}
.block-container{padding-top:0.6rem; padding-bottom:3rem; max-width:1200px;}
/* ---- Background ---- */
html, body, [data-testid="stAppViewContainer"]{
  background:
    radial-gradient(1200px 600px at 12% -10%, #2a2b47 0%, transparent 60%),
    radial-gradient(900px 400px at 110% 10%, #1b2649 0%, transparent 55%),
    linear-gradient(180deg, #0b0f1a 0%, #0a0d17 100%) !important;
}
/* ---- Paywall card ---- */
.paywall{
  background: rgba(17, 20, 32, 0.88);
  border: 1px solid #2c3550;
  border-radius: 22px; padding: 40px 28px; color:#e8ecf7;
  text-align:center; margin:40px auto; max-width:820px;
  box-shadow: 0 20px 50px rgba(0,0,0,.40);
}
.paywall h1{margin:0; font-size:48px; font-weight:900; letter-spacing:.3px;}
.paywall p{margin:12px auto 18px; font-size:17px; opacity:.95; max-width:650px}
.pill{
  display:inline-block; padding:6px 12px; border-radius:999px;
  border:1px solid #3a4466; background:#12182a; font-size:13px; opacity:.95; margin-bottom:8px;
}
.features{text-align:left; margin:16px auto 6px; display:inline-block; font-size:15px; line-height:1.45; max-width:640px}
.features li{margin:6px 0;}
/* Professional, dark, strong subscribe CTA (not glossy) */
.subscribe-btn{
  background:#1d4ed8; color:#fff; padding:14px 28px;
  border-radius:12px; text-decoration:none;
  font-size:18px; font-weight:800; letter-spacing:.2px;
  display:inline-block; transition: transform .06s ease, background .2s ease;
  border: 1px solid #2a55d8;
}
.subscribe-btn:hover{ background:#1842b7; transform: translateY(-1px); }
/* Dev login link */
.dev-link{display:block; margin-top:12px; font-size:13px; opacity:.75}

/* ---- In-app hero ---- */
.hero{
  background: linear-gradient(90deg,#6a11cb 0%,#2575fc 100%);
  border-radius: 18px; color: #fff; text-align:center;
  padding: 26px 18px; margin: 6px 0 12px;
  box-shadow: 0 8px 30px rgba(0,0,0,.25);
}
.hero h1{margin:0; font-size:40px; font-weight:900; letter-spacing:.3px;}
.hero p{margin:6px 0 0; opacity:.92}

/* ---- Sections ---- */
.section-title{font-weight:900;font-size:22px;margin:10px 0 14px;}

/* Upload panel */
.upload-card{
  background:#0e1117; border:1px solid #232b3a; border-radius:16px; padding:16px; margin-bottom:10px;
}
.upload-title{font-weight:800; font-size:18px; margin-bottom:6px}
textarea[aria-label="Paste your notes here…"]{min-height:180px}

/* ---- Tools row ---- */
.tool-row .stButton>button{
  width:100%; border-radius:12px; border:1px solid #2b2f3a;
  padding:10px; background:#10141e; color:#e8ecf7; font-weight:800;
}
.tool-row .stButton>button:hover{background:#141a27; border-color:#3a4252;}

/* ---- Results area (single, stable) ---- */
.results-box{
  border:1px solid #232b3a; background:#0e1117; border-radius:14px; padding:14px; min-height:160px;
}

/* ---- Inline modal (process-choice) ---- */
.modal-card{
  margin-top:12px; padding:14px; border-radius:12px;
  border:1px solid #283149; background:#0d1118;
}
.modal-actions{display:flex; gap:10px; align-items:center; margin-top:8px;}
.modal-primary{
  background:#1d4ed8; border:1px solid #2a55d8; color:#fff; padding:8px 14px; border-radius:10px; font-weight:800;
}
.modal-primary:hover{ background:#1842b7 }
.modal-ghost{
  background:#10141e; border:1px solid #2b2f3a; color:#e8ecf7; padding:8px 14px; border-radius:10px; font-weight:700;
}
.modal-ghost:hover{ background:#141a27 }

/* ---- Chat ---- */
.chat-card{background:#0e1117; border:1px solid #232b3a; border-radius:14px; padding:10px;}
.chat-scroll{max-height:460px; overflow-y:auto; padding:4px 8px;}
.chat-msg{margin:6px 0}
.chat-role{opacity:.7; font-size:12px}
.chat-user{color:#9ecbff}
.chat-ai{color:#c0d5ff}

/* ---- Sidebar polish ---- */
.sidebar-section h3{margin-bottom:6px}
.sidebar-chip{display:inline-block; padding:6px 10px; border-radius:12px; border:1px solid #2c3550; margin:4px 6px 0 0; font-size:12px; opacity:.9}

/* remove stray blank containers / lines (ghost boxes) */
[data-testid="stVerticalBlock"] > div:empty{display:none}
hr{border: none; border-top: 1px solid #222a3a; margin: 10px 0;}
</style>
""", unsafe_allow_html=True)

# =========================
# STATE
# =========================
ss = st.session_state
if "dev_unlocked" not in ss: ss.dev_unlocked = False
if "chat_open" not in ss: ss.chat_open = False
if "messages" not in ss: ss.messages = []
if "history_quiz" not in ss: ss.history_quiz = []  # list of dicts: {"title":..., "score": ...}
if "history_mock" not in ss: ss.history_mock = []
if "notes_text" not in ss: ss.notes_text = ""
if "last_title" not in ss: ss.last_title = "Untitled notes"
if "pending_tool" not in ss: ss.pending_tool = None         # "summary"|"flash"|"quiz"|"mock"
if "process_choice" not in ss: ss.process_choice = None     # "Text only"|"Text + Images/Diagrams"
if "mock_diff" not in ss: ss.mock_diff = "Standard"
if "flash_state" not in ss: ss.flash_state = {}             # idx -> revealed bool
if "results_nonce" not in ss: ss.results_nonce = 0          # force refresh of results container

# =========================
# OPENAI CLIENT
# =========================
def _client() -> OpenAI:
    key = st.secrets.get("OPENAI_API_KEY")
    if not key:
        st.error("Missing OPENAI_API_KEY in Streamlit Secrets.")
        st.stop()
    os.environ["OPENAI_API_KEY"] = key
    return OpenAI()

MODEL_TEXT = "gpt-4o-mini"
MODEL_VISION = "gpt-4o-mini"

def ask_llm(prompt: str, system="You are Zentra, a precise and supportive study buddy. Be concise and clear."):
    r = _client().chat.completions.create(
        model=MODEL_TEXT,
        messages=[{"role":"system","content":system},{"role":"user","content":prompt}],
        temperature=0.4,
    )
    return r.choices[0].message.content.strip()

def ask_vision(prompt: str, images: List[Tuple[str, bytes]], text_hint: str):
    """Send up to 3 images alongside text hint to the vision model."""
    parts = [{"type":"text","text": f"Use images/diagrams + text to answer.\n\nTEXT:\n{text_hint}\n\nTASK:\n{prompt}"}]
    for name, b in images[:3]:
        b64 = base64.b64encode(b).decode()
        mime = "image/png" if name.lower().endswith(".png") else "image/jpeg"
        parts.append({"type":"image_url","image_url":{"url": f"data:{mime};base64,{b64}"}})
    r = _client().chat.completions.create(
        model=MODEL_VISION,
        messages=[{"role":"user","content":parts}],
        temperature=0.4
    )
    return r.choices[0].message.content.strip()

# =========================
# FILE HANDLING
# =========================
def _try_pdf_to_images(pdf_bytes: bytes, max_pages: int = 2) -> List[Tuple[str, bytes]]:
    """
    Best-effort: convert first N pages of a PDF to images for diagram-aware mode.
    Requires pdf2image + poppler in deployment; if unavailable, we safely no-op.
    """
    images: List[Tuple[str, bytes]] = []
    try:
        from pdf2image import convert_from_bytes
        pil_imgs = convert_from_bytes(pdf_bytes, first_page=1, last_page=max_pages, dpi=180)
        for i, im in enumerate(pil_imgs, 1):
            buf = io.BytesIO()
            im.save(buf, format="JPEG", quality=85)
            images.append((f"page_{i}.jpg", buf.getvalue()))
    except Exception:
        pass
    return images

def read_file(uploaded, want_images: bool) -> Tuple[str, List[Tuple[str, bytes]]]:
    """Return (text, images[])."""
    if not uploaded: return "", []
    name = uploaded.name.lower()
    data = uploaded.read()
    text = ""
    images: List[Tuple[str, bytes]] = []
    if name.endswith(".txt"):
        text = data.decode("utf-8", "ignore")
    elif name.endswith(".pdf"):
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data))
            pages = []
            for p in reader.pages:
                pages.append(p.extract_text() or "")
            text = "\n".join(pages)
        except Exception:
            text = ""
        if want_images:
            images.extend(_try_pdf_to_images(data, max_pages=2))
    elif name.endswith(".docx"):
        try:
            import docx2txt
            with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
                tmp.write(data); tmp.flush()
                text = docx2txt.process(tmp.name)
        except Exception:
            text = ""
    elif name.endswith((".png",".jpg",".jpeg")):
        images.append((uploaded.name, data))
    else:
        text = data.decode("utf-8", "ignore")
    return (text or "").strip(), images

def ensure_notes(pasted: str, uploaded, include_images: bool) -> Tuple[str, List[Tuple[str, bytes]]]:
    txt = (pasted or "").strip()
    imgs: List[Tuple[str, bytes]] = []
    if uploaded:
        t, ii = read_file(uploaded, include_images)
        if t: txt = (txt + "\n" + t).strip() if txt else t
        if ii: imgs = ii
        ss.last_title = uploaded.name
    if len(txt) < 5 and not imgs:
        st.warning("Your notes look empty. Paste your notes or upload a readable PDF/DOCX. For diagrams, choose **Text + Images/Diagrams**.")
        st.stop()
    ss.notes_text = txt
    return txt, imgs

def adaptive_quiz_count(txt: str) -> int:
    return max(4, min(16, len(txt.split()) // 180))

def rounded_score_from_len(txt: str) -> int:
    words = max(1, len(txt.split()))
    if words < 300: return 30
    if words < 700: return 50
    if words < 1200: return 70
    if words < 2000: return 90
    return 100

# =========================
# PAYWALL (TEMP DEV LOGIN)
# =========================
if not ss.dev_unlocked:
    st.markdown(f"""
    <div class="paywall">
      <div class="pill">7-day free trial • Cancel anytime</div>
      <h1>Zentra — AI Study Buddy</h1>
      <p>Turn messy notes into laser-focused study materials, quizzes that actually teach, and graded mock exams — plus an on-demand tutor.</p>
      <a class="subscribe-btn" href="https://zentraai.lemonsqueezy.com/buy/XXXXXXXX" target="_blank">Subscribe — $5.99 / month</a>
      <a class="dev-link" href="#" onclick="window.parent.postMessage({{type:'devLogin'}}, '*'); return false;">(Dev login for testing)</a>
      <div class="features">
        <ul>
          <li>📄 Summaries — exam-ready bullets that cover what matters</li>
          <li>🧠 Flashcards — reveal answers only when you’re ready</li>
          <li>🎯 Quizzes — auto-scored, instant explanations</li>
          <li>📝 Mock Exams — MCQ + short + long + fill-in, graded with feedback</li>
          <li>💬 Ask Zentra — your subject-agnostic tutor, any topic</li>
        </ul>
      </div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("🚪 Dev Login (Temporary)"):
        ss.dev_unlocked = True
        st.rerun()

    st.components.v1.html("""
    <script>
    window.addEventListener("message",(e)=>{
      if(e.data && e.data.type==="devLogin"){
        const doc = window.parent.document;
        const btns=[...doc.querySelectorAll('button')];
        const dev=btns.find(b=>b.innerText.includes("Dev Login"));
        if(dev){dev.click();}
      }
    });
    </script>
    """, height=0)
    st.stop()

# =========================
# HERO (Inside App)
# =========================
st.markdown('<div class="hero"><h1>⚡ Zentra — AI Study Buddy</h1><p>Smarter notes → Better recall → Higher scores.</p></div>', unsafe_allow_html=True)

# =========================
# SIDEBAR
# =========================
with st.sidebar:
    st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
    st.markdown("### 🌟 Why students love Zentra")
    st.write("Shrink long notes into tight summaries, drill key ideas with flashcards, and test yourself with quizzes & mocks that actually teach — all in one clean workspace.")
    st.markdown('<span class="sidebar-chip">Active recall</span><span class="sidebar-chip">Structured practice</span><span class="sidebar-chip">Autograded mocks</span><span class="sidebar-chip">On-demand tutor</span>', unsafe_allow_html=True)

    st.markdown("### 📂 History")
    if ss.history_quiz:
        st.caption("Recent Quizzes")
        for i, item in enumerate(reversed(ss.history_quiz[-8:])):
            cols = st.columns([5,1])
            with cols[0]:
                st.write(f"• {item.get('title','Quiz')} — {item.get('score','—')}")
            with cols[1]:
                if st.button("🗑️", key=f"del_q_{i}"):
                    original = list(ss.history_quiz)
                    for j in range(len(original)-1, -1, -1):
                        if original[j] == item:
                            ss.history_quiz.pop(j); break
                    st.rerun()
    else:
        st.caption("Recent Quizzes"); st.write("—")

    if ss.history_mock:
        st.caption("Recent Mock Exams")
        for i, item in enumerate(reversed(ss.history_mock[-8:])):
            cols = st.columns([5,1])
            with cols[0]:
                st.write(f"• {item.get('title','Mock')} — {item.get('score','—')}")
            with cols[1]:
                if st.button("🗑️", key=f"del_m_{i}"):
                    original = list(ss.history_mock)
                    for j in range(len(original)-1, -1, -1):
                        if original[j] == item:
                            ss.history_mock.pop(j); break
                    st.rerun()
    else:
        st.caption("Recent Mock Exams"); st.write("—")

    st.markdown("---")
    if st.button("Clear All History"):
        ss.history_quiz = []
        ss.history_mock = []
        st.rerun()
    st.caption("Disclaimer: AI-generated. Verify before exams.")
    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# LAYOUT: Main + Chat
# =========================
col_main, col_chat = st.columns([3, 1.35], gap="large")

# ---------- MAIN ----------
with col_main:
    # Upload card
    st.markdown('<div class="upload-card">', unsafe_allow_html=True)
    st.markdown('<div class="upload-title">📁 Upload Your Notes</div>', unsafe_allow_html=True)
    up_left, up_right = st.columns([3,2], vertical_alignment="bottom")
    with up_left:
        uploaded = st.file_uploader("Upload file", type=["pdf","docx","txt","png","jpg","jpeg"], label_visibility="collapsed")
        pasted = st.text_area("Paste your notes here…", height=180, label_visibility="collapsed")
    with up_right:
        st.caption("Choose a tool below. If your file has diagrams, select **Text + Images/Diagrams** when prompted.")
    st.markdown('</div>', unsafe_allow_html=True)

    # Tools row
    st.markdown('<div class="section-title">✨ Study Tools</div>', unsafe_allow_html=True)
    st.markdown('<div class="tool-row">', unsafe_allow_html=True)
    c1, c2, c3, c4, c5 = st.columns(5)
    go_summary = c1.button("📄 Summaries", key="go_summary")
    go_cards   = c2.button("🧠 Flashcards", key="go_cards")
    go_quiz    = c3.button("🎯 Quizzes",    key="go_quiz")
    go_mock    = c4.button("📝 Mock Exams", key="go_mock")
    open_chat  = c5.button("💬 Ask Zentra", key="go_chat")
    st.markdown('</div>', unsafe_allow_html=True)

    if open_chat:
        ss.chat_open = True
        st.rerun()

    # SINGLE results placeholder (no ghost boxes). We always write into this.
    results_placeholder = st.empty()

    # Helper to open results container fresh
    def open_results():
        with results_placeholder.container():
            st.markdown(f'<div class="results-box" id="results-{ss.results_nonce}">', unsafe_allow_html=True)
            return st  # use the returned context (same container)

    # ---------- PROCESS ENTRY ----------
    if go_summary: ss.pending_tool, ss.process_choice = "summary", None; ss.results_nonce += 1; st.rerun()
    if go_cards:   ss.pending_tool, ss.process_choice = "flash",   None; ss.results_nonce += 1; st.rerun()
    if go_quiz:    ss.pending_tool, ss.process_choice = "quiz",    None; ss.results_nonce += 1; st.rerun()
    if go_mock:    ss.pending_tool, ss.process_choice = "mock",    None; ss.results_nonce += 1; st.rerun()

    # ------------- PROCESS CHOICE (Modal-style card) -------------
    if ss.pending_tool:
        with open_results():
            st.markdown('<div class="modal-card">', unsafe_allow_html=True)
            st.markdown("**How should Zentra process your file?**")
            ss.process_choice = st.radio(
                " ",
                options=["Text only", "Text + Images/Diagrams"],
                index=0,
                horizontal=True,
                label_visibility="collapsed"
            )
            colA, colB = st.columns([1,1])
            cont = colA.button("Continue", key="proc_continue", help="Use the selected processing mode.", use_container_width=True)
            canc = colB.button("Cancel",   key="proc_cancel",   use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        if canc:
            ss.pending_tool = None
            ss.process_choice = None
            st.rerun()

        if cont:
            include_images = (ss.process_choice == "Text + Images/Diagrams")
            text, imgs = ensure_notes(pasted, uploaded, include_images)

            # ------- TOOL RUNNERS (always render INSIDE results box) -------
            def run_summary():
                with open_results():
                    st.subheader("✅ Summary")
                    with st.spinner("Generating summary…"):
                        prompt = f"""Summarize the following notes into **clean, exam-ready bullet points**.
Cover definitions, laws/theorems, key steps, formulas, and 'must-know' facts. Be tight and complete.
NOTES:
{text}"""
                        out = ask_vision(prompt, imgs, text) if (include_images and imgs) else ask_llm(prompt)
                    st.markdown(out or "_(no content)_")

            def run_flashcards():
                with open_results():
                    st.subheader("🧠 Flashcards")
                    with st.spinner("Creating flashcards…"):
                        prompt = f"""Create high-quality flashcards that **cover all key points**.
Return each card as two lines:
**Q:** …
**A:** …
NOTES:
{text}"""
                        raw = ask_vision(prompt, imgs, text) if (include_images and imgs) else ask_llm(prompt)

                    # Parse Q/A pairs robustly
                    cards = []
                    q, a = None, None
                    for line in raw.splitlines():
                        s = line.strip()
                        if s.startswith("**Q:**"):
                            if q and a is not None:
                                cards.append({"q": q, "a": a})
                            q = s.replace("**Q:**", "").strip()
                            a = None
                        elif s.startswith("**A:**"):
                            a = s.replace("**A:**", "").strip()
                    if q and a is not None:
                        cards.append({"q": q, "a": a})

                    if not cards:
                        st.markdown(raw or "_(no content)_")
                    else:
                        for idx, card in enumerate(cards):
                            key_q = f"flash_{ss.results_nonce}_{idx}"
                            if key_q not in ss.flash_state:
                                ss.flash_state[key_q] = False
                            box = st.container(border=True)
                            with box:
                                st.markdown(f"**Q{idx+1}:** {card['q']}")
                                if ss.flash_state[key_q]:
                                    st.markdown(f"**A:** {card['a']}")
                                c1, c2 = st.columns([1,1])
                                if not ss.flash_state[key_q]:
                                    if c1.button("Reveal", key=f"reveal_{key_q}"):
                                        ss.flash_state[key_q] = True
                                        st.rerun()
                                else:
                                    if c1.button("Hide", key=f"hide_{key_q}"):
                                        ss.flash_state[key_q] = False
                                        st.rerun()
                                c2.caption("Tip: Test yourself before revealing.")

            def run_quiz():
                with open_results():
                    n = adaptive_quiz_count(text)
                    st.subheader("🎯 Quiz")
                    with st.spinner("Building quiz…"):
                        prompt = f"""Create {n} multiple-choice questions (A–D).
Return numbered questions with options A–D.
At the end include an **Answer Key** exactly in this format on a single line:
Answer Key: 1) B, 2) D, 3) A, ...
Cover the entire notes fairly.
NOTES:
{text}"""
                        raw = ask_vision(prompt, imgs, text) if (include_images and imgs) else ask_llm(prompt)

                    quiz_body = st.container()
                    quiz_body.markdown(raw)

                    st.markdown("---")
                    st.caption("Your Answers")
                    with st.form(f"quiz_form_{ss.results_nonce}", clear_on_submit=False):
                        answers = []
                        for i in range(n):
                            ans = st.radio(f"Q{i+1}", ["A","B","C","D"], key=f"quiz_{ss.results_nonce}_{i}", horizontal=True)
                            answers.append(ans)
                        submitted = st.form_submit_button("Submit Quiz")
                    if submitted:
                        # parse key
                        key_line = ""
                        for line in raw.splitlines()[::-1]:
                            if "Answer Key" in line:
                                key_line = line
                                break
                        correct = []
                        if key_line:
                            pairs = re.findall(r"(\d+)\)\s*([ABCD])", key_line)
                            pairs = sorted(((int(i), c) for (i, c) in pairs), key=lambda x:x[0])
                            correct = [c for (_, c) in pairs]
                        score = 0
                        detail = []
                        total = min(len(answers), len(correct))
                        for i in range(total):
                            ok = answers[i] == correct[i]
                            if ok: score += 1
                            detail.append(f"Q{i+1}: {'✅' if ok else '❌'} — Your: {answers[i]} • Ans: {correct[i]}")
                        score_str = f"{score}/{total} correct"
                        st.success(f"Score: {score_str}")
                        st.markdown("\n".join(detail))
                        ss.history_quiz.append({"title": ss.last_title, "score": score_str})

            def run_mock():
                with open_results():
                    st.subheader("📝 Mock Exam")
                    with st.expander("Select difficulty", expanded=True):
                        ss.mock_diff = st.radio(
                            " ",
                            ["Easy","Standard","Hard"],
                            index=["Easy","Standard","Hard"].index(ss.mock_diff),
                            horizontal=True,
                            label_visibility="collapsed",
                            key=f"mock_diff_{ss.results_nonce}"
                        )
                        go = st.button("Create Mock", type="primary", key=f"mock_go_{ss.results_nonce}")
                    if not go:
                        return

                    total_max = rounded_score_from_len(text)
                    with st.spinner("Composing mock…"):
                        prompt = f"""Create a **{ss.mock_diff}** mock exam from the notes with these sections:
1) MCQs — 5 questions (options A–D)
2) Short-answer — 2 questions
3) Long-answer (essay) — 1 question
4) Fill-in — 2 questions

Provide a marking rubric with points per section adding up to **{total_max}** total.
At the very end include "Answer Key" and model solutions.

Return in clear, numbered Markdown.
NOTES:
{text}"""
                        raw = ask_vision(prompt, imgs, text) if (include_images and imgs) else ask_llm(prompt)

                    st.markdown(raw)

                    # Answer inputs
                    st.markdown("---")
                    st.caption("Your Answers")
                    with st.form(f"mock_form_{ss.results_nonce}", clear_on_submit=False):
                        mcq_ans  = [st.radio(f"MCQ {i+1}", ["A","B","C","D"], key=f"mock_mcq_{ss.results_nonce}_{i}", horizontal=True) for i in range(5)]
                        short_ans= [st.text_area(f"Short Answer {i+1}", key=f"mock_short_{ss.results_nonce}_{i}") for i in range(2)]
                        long_ans =  st.text_area("Long Answer (Essay)", key=f"mock_long_{ss.results_nonce}")
                        fill_ans = [st.text_input(f"Fill in {i+1}", key=f"mock_fill_{ss.results_nonce}_{i}") for i in range(2)]
                        submit   = st.form_submit_button("Submit Mock for Grading")
                    if submit:
                        with st.spinner("Grading…"):
                            grading = f"""You are Zentra. Grade the student's mock strictly using the provided rubric.
Total points must be an integer and a multiple of 10 with max {total_max}.
Provide:
- Total Score (e.g., 60/70)
- Section Breakdown (points per section)
- Strengths (bullets)
- Weaknesses (bullets)
- Actionable Tips (bullets)
- Corrected Answers / Model Outline for non-MCQ

STUDENT ANSWERS:
MCQ: {mcq_ans}
Short: {short_ans}
Long: {long_ans}
Fill: {fill_ans}

NOTES:
{text}

MOCK + RUBRIC + ANSWER KEY:
{raw}
"""
                            result = ask_llm(grading)
                        st.success("✅ Mock Graded")
                        st.markdown(result)
                        first_line = result.splitlines()[0] if result else "Scored"
                        ss.history_mock.append({"title": ss.last_title, "score": first_line})

            # Dispatch
            if ss.pending_tool == "summary":
                run_summary()
            elif ss.pending_tool == "flash":
                run_flashcards()
            elif ss.pending_tool == "quiz":
                run_quiz()
            elif ss.pending_tool == "mock":
                run_mock()

            # Reset pending state
            ss.pending_tool = None
            ss.process_choice = None

# ---------- CHAT ----------
with col_chat:
    if ss.chat_open:
        st.markdown("### 💬 Ask Zentra")
        ctrl1, ctrl2, _ = st.columns(3)
        with ctrl1:
            if st.button("Close"):
                ss.chat_open = False; st.rerun()
        with ctrl2:
            if st.button("Clear"):
                ss.messages = []; st.rerun()

        # chat scroll area (confined to card)
        st.markdown('<div class="chat-card">', unsafe_allow_html=True)
        chat_html = '<div class="chat-scroll" id="chat-scroll">'
        for m in ss.messages:
            role = '🧑‍🎓 <span class="chat-user">You</span>' if m["role"]=="user" else '🤖 <span class="chat-ai">Zentra</span>'
            chat_html += f'<div class="chat-msg"><div class="chat-role">{role}</div><div>{m["content"]}</div></div>'
        chat_html += "</div>"
        st.markdown(chat_html, unsafe_allow_html=True)

        # input (shows typed text visibly)
        user_q = st.text_input("Type your message and press Enter", key="chat_input_text")
        if user_q:
            ss.messages.append({"role":"user","content":user_q})
            try:
                reply = ask_llm(
                    "You are **Zentra**. Answer the user's question clearly and briefly. "
                    "Do not use uploaded notes unless the user explicitly references them.\n\n"
                    f"USER: {user_q}"
                )
            except Exception as e:
                reply = f"Sorry, error: {e}"
            ss.messages.append({"role":"assistant","content":reply})
            # auto-scroll
            st.components.v1.html("""
            <script>
              const box = parent.document.querySelector('#chat-scroll');
              if (box) { box.scrollTop = box.scrollHeight; }
            </script>
            """, height=0)
            st.session_state.chat_input_text = ""
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
