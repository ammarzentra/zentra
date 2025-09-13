# app.py — Zentra FINAL (all tools fixed, polished UI, proper flows)
# NOTE: Set OPENAI_API_KEY in Streamlit Secrets before deploying.

import os, io, base64, tempfile
from typing import List, Tuple
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
/* ---- Background for paywall page ---- */
html, body, [data-testid="stAppViewContainer"]{
  background: radial-gradient(1200px 600px at 10% -10%, #2a2b47 0%, transparent 60%),
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
  background: #1d4ed8; /* deep blue */
  color:#fff; padding:14px 28px;
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
/* Upload panel centered & bigger */
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
/* ---- Results box (everything renders inside) ---- */
.results-box{
  border:1px solid #232b3a; background:#0e1117; border-radius:14px; padding:14px; min-height:140px;
}
/* ---- Chat ---- */
.chat-card{background:#0e1117; border:1px solid #232b3a; border-radius:14px; padding:10px;}
.chat-scroll{max-height:440px; overflow-y:auto; padding:4px 8px;}
.chat-msg{margin:6px 0}
.chat-role{opacity:.7; font-size:12px}
.chat-user{color:#9ecbff}
.chat-ai{color:#c0d5ff}
/* ---- Sidebar polish ---- */
.sidebar-section h3{margin-bottom:6px}
.sidebar-chip{display:inline-block; padding:6px 10px; border-radius:12px; border:1px solid #2c3550; margin:4px 6px 0 0; font-size:12px; opacity:.9}
/* remove stray blank containers / lines */
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
if "history_quiz" not in ss: ss.history_quiz = []  # list of dicts: {"title":..., "ts":..., "score": ...}
if "history_mock" not in ss: ss.history_mock = []
if "notes_text" not in ss: ss.notes_text = ""
if "last_title" not in ss: ss.last_title = "Untitled notes"
if "pending_tool" not in ss: ss.pending_tool = None  # "summary"|"flash"|"quiz"|"mock"
if "process_choice" not in ss: ss.process_choice = None  # "Text only"|"Text + Images/Diagrams"
if "mock_diff" not in ss: ss.mock_diff = "Standard"
if "results_key" not in ss: ss.results_key = 0  # to force results box rerender
if "flash_state" not in ss: ss.flash_state = {}  # idx -> revealed bool

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
    """Send up to 2 images alongside text hint to the vision model."""
    parts = [{"type":"text","text": f"Use images/diagrams + text to answer.\n\nTEXT:\n{text_hint}\n\nTASK:\n{prompt}"}]
    for name, b in images[:2]:
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
def read_file(uploaded) -> Tuple[str, List[Tuple[str, bytes]]]:
    """Return (text, images[]). Note: we do not rasterize PDF pages; if users want images considered,
    they should upload images or select Text+Images to include attached image files too."""
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
        # We cannot reliably extract embedded diagrams from PDFs here without extra libs.
        # If user also uploads supporting images separately, we'll include them.
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

def ensure_notes(pasted, uploaded):
    txt = (pasted or "").strip()
    imgs: List[Tuple[str, bytes]] = []
    if uploaded:
        t, ii = read_file(uploaded)
        if t: txt = (txt + "\n" + t).strip() if txt else t
        if ii: imgs = ii
        ss.last_title = uploaded.name
    if len(txt) < 5 and not imgs:
        st.warning("Your notes look empty. Paste your notes or upload a readable PDF/DOCX (image-only PDFs need Text + Images).")
        st.stop()
    ss.notes_text = txt
    return txt, imgs

def adaptive_quiz_count(txt: str) -> int:
    return max(4, min(16, len(txt.split()) // 180))

def rounded_score_from_len(txt: str) -> int:
    """Pick a score ceiling in multiples of 10 based on notes size."""
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

    # Dev login button (works without JS too)
    if st.button("🚪 Dev Login (Temporary)"):
        ss.dev_unlocked = True
        st.rerun()

    # small listener to support the link in paywall
    st.components.v1.html("""
    <script>
    window.addEventListener("message",(e)=>{
      if(e.data && e.data.type==="devLogin"){
        const streamlitDoc = window.parent.document;
        const btns=[...streamlitDoc.querySelectorAll('button')];
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
# SIDEBAR (Collapsible by Streamlit)
# =========================
with st.sidebar:
    st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
    st.markdown("### 🌟 Why students love Zentra")
    st.write("Shrink long notes into tight summaries, drill key ideas with flashcards, and test yourself with quizzes & mocks that actually teach — all in one clean workspace.")
    st.markdown('<span class="sidebar-chip">Active recall</span><span class="sidebar-chip">Structured practice</span><span class="sidebar-chip">Autograded mocks</span><span class="sidebar-chip">On-demand tutor</span>', unsafe_allow_html=True)

    st.markdown("### 📂 History")
    # Per-item delete
    if ss.history_quiz:
        st.caption("Recent Quizzes")
        for i, item in enumerate(reversed(ss.history_quiz[-8:])):
            cols = st.columns([5,1])
            with cols[0]:
                st.write(f"• {item.get('title','Quiz')} — {item.get('score','—')}")
            with cols[1]:
                if st.button("🗑️", key=f"del_q_{i}"):
                    # remove by identity (pop last occurrences first)
                    original = list(ss.history_quiz)
                    # map back to index in original
                    # simplest: remove first matching from end
                    for j in range(len(original)-1, -1, -1):
                        if original[j] == item:
                            ss.history_quiz.pop(j)
                            break
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
                            ss.history_mock.pop(j)
                            break
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
    # Upload card (centered feel via wide column + inner card)
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

    # RESULTS AREA (single box; all outputs render here)
    results = st.container()
    results.markdown(f'<div class="results-box" id="results-box-{ss.results_key}">', unsafe_allow_html=True)

    # ---------- PROCESS FLOW ----------
    # 1) When a tool is clicked, hold the action, show "process choice" first.
    if go_summary: ss.pending_tool, ss.process_choice = "summary", None; st.rerun()
    if go_cards:   ss.pending_tool, ss.process_choice = "flash", None; st.rerun()
    if go_quiz:    ss.pending_tool, ss.process_choice = "quiz", None; st.rerun()
    if go_mock:    ss.pending_tool, ss.process_choice = "mock", None; st.rerun()

    # Helper to gather notes and images
    def collect_inputs():
        text, imgs = ensure_notes(pasted, uploaded)
        # If the uploaded file was image(s), imgs will be populated.
        # If PDF/Docx but has embedded images, we can't rasterize here.
        return text, imgs

    # 2) Show process-choice modal inline ONLY when a tool is pending.
    #    Then "Continue" -> run the selected tool, render inside results box.
    if ss.pending_tool:
        with st.expander("How should Zentra process your file?", expanded=True):
            ss.process_choice = st.radio(
                "",
                options=["Text only", "Text + Images/Diagrams"],
                index=0,
                horizontal=True,
                label_visibility="collapsed"
            )
            cont_cols = st.columns([1,1,6])
            with cont_cols[0]:
                continue_run = st.button("Continue", type="primary", key="proc_go")
            with cont_cols[1]:
                cancel_run = st.button("Cancel", key="proc_cancel")

        if cancel_run:
            ss.pending_tool, ss.process_choice = None, None
            st.rerun()

        if continue_run:
            text, imgs = collect_inputs()
            include_images = (ss.process_choice == "Text + Images/Diagrams")

            def run_summary():
                prompt = f"""Summarize the following notes into **clean, exam-ready bullet points**.
Cover definitions, laws/theorems, key steps, formulas, and 'must-know' facts. Be tight and complete.
NOTES:
{text}"""
                out = ask_vision(prompt, imgs, text) if (include_images and imgs) else ask_llm(prompt)
                results.subheader("✅ Summary")
                results.markdown(out or "_(no content)_")

            def run_flashcards():
                prompt = f"""Create high-quality flashcards that **cover all key points**.
Return each card as:
**Q:** …
**A:** …
Do not include answers until revealed.
NOTES:
{text}"""
                raw = ask_vision(prompt, imgs, text) if (include_images and imgs) else ask_llm(prompt)
                # Parse as simple Q/A pairs (split by lines starting with **Q:**)
                cards = []
                for chunk in raw.split("\n"):
                    if chunk.strip().startswith("**Q:**"):
                        q = chunk.strip().replace("**Q:**","").strip()
                        cards.append({"q": q, "a": ""})
                    elif chunk.strip().startswith("**A:**"):
                        a = chunk.strip().replace("**A:**","").strip()
                        if cards:
                            cards[-1]["a"] = a
                if not cards:  # fallback: show raw
                    results.subheader("🧠 Flashcards")
                    results.markdown(raw or "_(no content)_")
                else:
                    results.subheader("🧠 Flashcards")
                    for idx, card in enumerate(cards):
                        key_q = f"flash_reveal_{idx}"
                        if key_q not in ss.flash_state:
                            ss.flash_state[key_q] = False
                        cols = results.columns([7,2])
                        with cols[0]:
                            st.markdown(f"**Q{idx+1}:** {card['q']}")
                            if ss.flash_state[key_q]:
                                st.markdown(f"**A:** {card['a']}")
                        with cols[1]:
                            if not ss.flash_state[key_q]:
                                if st.button("Reveal", key=f"reveal_{idx}"):
                                    ss.flash_state[key_q] = True
                                    st.rerun()
                            else:
                                if st.button("Hide", key=f"hide_{idx}"):
                                    ss.flash_state[key_q] = False
                                    st.rerun()

            def run_quiz():
                n = adaptive_quiz_count(text)
                prompt = f"""Create {n} multiple-choice questions (A–D). 
Return as numbered list with question and four options A–D.
Also include the **Answer Key** at the end in the format: 
Answer Key: 1) B, 2) D, ...
Focus on full coverage of the notes.
NOTES:
{text}"""
                raw = ask_vision(prompt, imgs, text) if (include_images and imgs) else ask_llm(prompt)
                # Render quiz with radio inputs + score at the end
                results.subheader("🎯 Quiz")
                with results.form("quiz_form", clear_on_submit=False):
                    st.markdown(raw)
                    st.markdown("---")
                    st.caption("Your Answers")
                    answers = []
                    for i in range(n):
                        ans = st.radio(f"Q{i+1}", ["A","B","C","D"], key=f"quiz_ans_{i}", horizontal=True)
                        answers.append(ans)
                    submitted = st.form_submit_button("Submit Quiz")
                    if submitted:
                        # Extract answer key from raw
                        key_line = ""
                        for line in raw.splitlines()[::-1]:
                            if "Answer Key" in line:
                                key_line = line
                                break
                        correct = []
                        if key_line:
                            # parse "Answer Key: 1) B, 2) D, ..."
                            import re
                            pairs = re.findall(r"(\d+)\)\s*([ABCD])", key_line)
                            correct = [p[1] for p in sorted(pairs, key=lambda x:int(x[0]))]
                        # Score
                        score = 0
                        detail = []
                        for i in range(min(len(answers), len(correct))):
                            ok = answers[i] == correct[i]
                            score += 1 if ok else 0
                            detail.append(f"Q{i+1}: {'✅' if ok else '❌'} (Your: {answers[i]} | Ans: {correct[i]})")
                        score_str = f"{score}/{len(correct)} correct"
                        st.success(f"Score: {score_str}")
                        st.markdown("\n".join(detail))
                        ss.history_quiz.append({"title": ss.last_title, "score": score_str})

            def run_mock():
                # Ask difficulty first (within the flow)
                with results.expander("Select difficulty", expanded=True):
                    ss.mock_diff = st.radio("", ["Easy","Standard","Hard"], horizontal=True, index=["Easy","Standard","Hard"].index(ss.mock_diff), label_visibility="collapsed")
                    go = st.button("Create Mock", type="primary", key="mock_go_inner")
                if not go:
                    return
                # Compose mock
                total_max = rounded_score_from_len(text)
                prompt = f"""Create a **{ss.mock_diff}** mock exam from the notes with these sections:
1) MCQs — 5 questions (options A–D)
2) Short-answer — 2 questions
3) Long-answer (essay) — 1 question
4) Fill-in — 2 questions

Provide a marking rubric with points per section adding up to **{total_max}** total.
At the end, include the model answers / answer key.

Return in clear, numbered Markdown.
NOTES:
{text}"""
                raw = ask_vision(prompt, imgs, text) if (include_images and imgs) else ask_llm(prompt)
                results.subheader(f"📝 Mock Exam ({ss.mock_diff})")
                st.markdown(raw)

                # Answer inputs
                with results.form("mock_form", clear_on_submit=False):
                    st.markdown("---")
                    st.caption("Your Answers")
                    mcq_ans = [st.radio(f"MCQ {i+1}", ["A","B","C","D"], key=f"mock_mcq_{i}", horizontal=True) for i in range(5)]
                    short_ans = [st.text_area(f"Short Answer {i+1}", key=f"mock_short_{i}") for i in range(2)]
                    long_ans = st.text_area("Long Answer (Essay)", key="mock_long")
                    fill_ans = [st.text_input(f"Fill in {i+1}", key=f"mock_fill_{i}") for i in range(2)]
                    submit = st.form_submit_button("Submit Mock for Grading")
                    if submit:
                        grading = f"""You are Zentra. Grade the student's mock fairly and strictly using the provided marking rubric.
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
                        # Extract first line with total score if present
                        first_line = result.splitlines()[0] if result else "Scored"
                        ss.history_mock.append({"title": ss.last_title, "score": first_line})

            # Run the appropriate tool and render all output INSIDE the results box
            if ss.pending_tool == "summary":
                run_summary()
            elif ss.pending_tool == "flash":
                run_flashcards()
            elif ss.pending_tool == "quiz":
                run_quiz()
            elif ss.pending_tool == "mock":
                run_mock()

            # clear pending state + bump results key to avoid stray blank boxes
            ss.pending_tool, ss.process_choice = None, None
            ss.results_key += 1
            st.rerun()

    # close results box wrapper
    results.markdown('</div>', unsafe_allow_html=True)

# ---------- CHAT ----------
with col_chat:
    if ss.chat_open:
        st.markdown("### 💬 Ask Zentra")
        ctrl1, ctrl2, ctrl3 = st.columns(3)
        with ctrl1:
            if st.button("Close"):
                ss.chat_open = False; st.rerun()
        with ctrl2:
            if st.button("Clear"):
                ss.messages = []; st.rerun()
        with ctrl3:
            st.write("")  # spacer

        # chat scroll area
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
            # **Independent tutor** (do not automatically explain uploaded PDF unless user asks)
            try:
                reply = ask_llm(f"You are **Zentra**. Answer the user's question clearly and briefly."
                                f" Only reference the user's notes IF they explicitly mention them."
                                f"\n\nUSER: {user_q}")
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
            # reset input
            st.session_state.chat_input_text = ""
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        # keep column clean (no stray empty box)
        pass
