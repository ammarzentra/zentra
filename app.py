# app.py — Zentra (final DAN build)
# - Clean paywall (3-day trial), Dev Login (temp)
# - Fancy collapsible sidebar
# - Big centered upload + paste area
# - Tooltips on buttons
# - “Process as: Text only vs Text + Images/Diagrams” flow BEFORE running any tool
# - Summaries / Flashcards / Quizzes / Mock Exams:
#     * Quizzes render MCQs with inputs + scoring & explanations
#     * Mock asks difficulty, renders full exam with inputs, grades 0–100 + feedback
# - Ask Zentra chat: fixed-height scroll, no layout drift

import os, io, json, base64, tempfile
from typing import List, Tuple, Optional
import streamlit as st
from openai import OpenAI

# =========================
# PAGE CONFIG & GLOBAL CSS
# =========================
st.set_page_config(
    page_title="Zentra — Your Study Buddy",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
/* --- Reset cruft --- */
a[class*="viewerBadge"], div[class*="viewerBadge"], #ViewerBadgeContainer{display:none!important;}
footer{visibility:hidden;height:0}
.block-container{padding-top:.8rem; padding-bottom:3rem; max-width:1200px;}

/* --- Paywall --- */
.paywrap{display:flex; justify-content:center; margin-top:32px;}
.paywall{
  width: 880px; max-width: 95%;
  background: radial-gradient(1200px 500px at 50% -200px,#7c4dff 0%, #1b2a4a 40%, #0e1421 100%);
  border: 1px solid rgba(255,255,255,.08);
  border-radius: 18px; padding: 44px 36px; color:#eaf0ff;
  box-shadow: 0 12px 36px rgba(0,0,0,.40);
}
.paywall h1{margin:0 0 8px 0; font-size:44px; font-weight:900; letter-spacing:.2px;}
.paywall p.sub{margin:0 0 22px; font-size:16px; opacity:.9}
.paygrid{display:grid; grid-template-columns: 1fr 380px; gap:24px; align-items:start;}
.paycard{
  background: rgba(255,255,255,.03);
  border: 1px solid rgba(255,255,255,.06);
  border-radius:14px; padding:18px 18px;
}
.paycard ul{padding-left:20px; margin:10px 0;}
.paycard li{margin:8px 0;}
.btnrow{display:flex; gap:12px; align-items:center; margin-top:8px;}
.btn-sub{
  background: linear-gradient(180deg,#ffd257 0%,#ffb700 100%);
  color:#1c1c1c; padding:12px 22px; font-weight:800; border-radius:12px;
  text-decoration:none; display:inline-block; border:0; box-shadow: 0 4px 0 #c69200;
}
.btn-sub:hover{transform:translateY(-1px)}
.badge{font-size:12px; padding:5px 10px; border-radius:999px; border:1px solid rgba(255,255,255,.18);}

/* --- In-app HERO --- */
.hero{
  background: linear-gradient(90deg,#6a11cb 0%,#2575fc 100%);
  border-radius:16px; color:#fff; text-align:center;
  padding:24px; margin: 8px 0 16px;
  box-shadow: inset 0 -2px 0 rgba(255,255,255,.15);
}
.hero h1{margin:0; font-size:32px; font-weight:900;}
.hero p{margin:6px 0 0; opacity:.95}

/* --- Upload area --- */
.card{
  background:#101623; border:1px solid #223146;
  border-radius:14px; padding:16px;
}
.label{font-weight:800; font-size:20px; margin:8px 0 12px;}
textarea, .stTextArea textarea{min-height:190px!important}

/* --- Tool buttons --- */
.tool-row .stButton>button{
  width:100%; border-radius:12px; border:1px solid #2b2f3a;
  padding:10px 12px; background:#0e1421; color:#e8ecf7; font-weight:800;
}
.tool-row .stButton>button:hover{background:#121a2b; border-color:#3a4252;}

/* --- Choice bar (process text vs images) --- */
.choice{
  background:#0f1420; border:1px solid #243047; color:#dbe2f1;
  border-radius:14px; padding:14px 16px; margin-top:12px;
}

/* --- Chat --- */
.chat-wrap{border:1px solid #223146; border-radius:14px; background:#0f1420; padding:10px;}
.chat-box{max-height:420px; overflow-y:auto; padding:2px 6px;}
.chat-msg{margin:6px 0;}
.chat-role{opacity:.8; font-weight:700; margin-right:6px}

/* --- Sidebar polish --- */
.sidebar-card{
  background:#0f1420; border:1px solid #243047; color:#dbe2f1;
  border-radius:14px; padding:14px; margin-bottom:10px;
}
.sidebar-title{font-weight:900; font-size:18px; display:flex; gap:6px; align-items:center;}
.sidebar-small{opacity:.85; font-size:13px;}

/* --- Fix chat input phantom spacing --- */
.block-container div[data-testid="stChatInput"]{margin-top:6px;}
</style>
""", unsafe_allow_html=True)

# =================
# SESSION DEFAULTS
# =================
ss = st.session_state
ss.setdefault("dev_unlocked", False)
ss.setdefault("chat_open", True)
ss.setdefault("messages", [])
ss.setdefault("history_quiz", [])
ss.setdefault("history_mock", [])
ss.setdefault("notes_text", "")
ss.setdefault("last_title", "Untitled notes")
# flow for pre-tool choice
ss.setdefault("pending_tool", None)           # "summary" | "cards" | "quiz" | "mock"
ss.setdefault("process_choice", None)         # "text" | "vision"
ss.setdefault("temp_text", "")
ss.setdefault("temp_images", [])

# ============
# OPENAI HELPER
# ============
def _client() -> OpenAI:
    key = st.secrets.get("OPENAI_API_KEY")
    if not key:
        st.error("Missing OPENAI_API_KEY in Streamlit Secrets.")
        st.stop()
    os.environ["OPENAI_API_KEY"] = key
    return OpenAI()

MODEL = "gpt-4o-mini"

def ask_llm_text(prompt: str, system="You are Zentra, a precise and supportive study buddy. Be concise, exam-focused, and clear.") -> str:
    r = _client().chat.completions.create(
        model=MODEL,
        messages=[{"role":"system","content":system},{"role":"user","content":prompt}],
        temperature=0.4,
    )
    return (r.choices[0].message.content or "").strip()

# ====================
# FILE PARSE & HELPERS
# ====================
def read_file(uploaded) -> Tuple[str, List[Tuple[str, bytes]]]:
    if not uploaded: return "", []
    name = uploaded.name.lower()
    data = uploaded.read()
    text, images = "", []
    if name.endswith(".txt"):
        text = data.decode("utf-8","ignore")
    elif name.endswith(".pdf"):
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data))
            text = "\n".join([(p.extract_text() or "") for p in reader.pages])
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
        images.append((uploaded.name, data))
    else:
        try:
            text = data.decode("utf-8","ignore")
        except Exception:
            text = ""
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
        st.warning("Your notes look empty. Paste text or upload a readable file.")
        st.stop()
    ss.notes_text = txt
    return txt, imgs

def adaptive_quiz_count(txt: str) -> int:
    return max(3, min(20, len(txt.split()) // 180))

# =================================
# PAYWALL (until LS is fully live)
# =================================
if not ss.dev_unlocked:
    st.markdown("""
    <div class="paywrap"><div class="paywall">
      <h1>⚡ Zentra — AI Study Buddy</h1>
      <p class="sub">Unlock your personal AI buddy for <b>$5.99/month</b> • <span class="badge">3-day free trial</span> • Cancel anytime</p>

      <div class="paygrid">
        <div class="paycard">
          <ul>
            <li>📄 Smart Summaries → exam-ready notes</li>
            <li>🧠 Flashcards → active recall Q/A (tap to reveal)</li>
            <li>🎯 Quizzes → MCQs with instant scoring & explanations</li>
            <li>📝 Mock Exams → MCQ + short + long + fill-in, graded with feedback</li>
            <li>💬 Ask Zentra → your on-demand tutor</li>
          </ul>
          <div class="btnrow">
            <a class="btn-sub" href="https://zentraai.lemonsqueezy.com/buy/XXXXXXXX" target="_blank">Subscribe Now</a>
            <span class="badge">Secure checkout</span>
          </div>
        </div>

        <div class="paycard">
          <b>How Zentra helps you</b>
          <ul>
            <li>Upload notes or PDFs (even with diagrams)</li>
            <li>Auto-generated summaries & flashcards</li>
            <li>Drill with quizzes & sit graded mocks</li>
            <li>Target weak topics with clear feedback</li>
            <li>Learn faster → recall more → score higher</li>
          </ul>
        </div>
      </div>
    </div></div>
    """, unsafe_allow_html=True)

    # Temporary dev unlock button (remove after Lemon Squeezy approves)
    if st.button("🚪 Dev Login (Temp)"):
        ss.dev_unlocked = True
        st.rerun()
    st.stop()

# ======================
# SIDEBAR (collapsible)
# ======================
with st.sidebar:
    st.markdown('<div class="sidebar-card"><div class="sidebar-title">🧰 Zentra Toolkit</div><div class="sidebar-small">Turn your notes into a complete toolkit: summaries, flashcards, quizzes, mocks, and a tutor — all in one place.</div></div>', unsafe_allow_html=True)
    with st.expander("💡 How Zentra helps you", True):
        st.markdown("- Turn notes into **summaries & flashcards**\n- Drill with **quizzes** and get instant **feedback**\n- Sit **mock exams** with grading & tips\n- Ask Zentra anything, anytime")
    st.markdown("### 🗂️ History")
    st.caption("Recent Quizzes:"); st.write(ss.history_quiz or "—")
    st.caption("Recent Mock Exams:"); st.write(ss.history_mock or "—")
    st.markdown("---")
    st.caption("⚠️ AI-generated help. Verify before exams.")

# ==========
# HERO
# ==========
st.markdown('<div class="hero"><h1>⚡ Zentra — Your Study Buddy</h1><p>Smarter notes → Better recall → Higher scores.</p></div>', unsafe_allow_html=True)

# ====================
# MAIN LAYOUT (2-cols)
# ====================
col_main, col_chat = st.columns([3, 1.35], gap="large")

# ----------------
# MAIN: uploader + tools
# ----------------
with col_main:
    st.markdown('<div class="label">📁 Upload Your Notes</div>', unsafe_allow_html=True)
    upc1, upc2 = st.columns([3,2], vertical_alignment="bottom")
    with upc1:
        with st.container():
            st.markdown('<div class="card">', unsafe_allow_html=True)
            uploaded = st.file_uploader("Drag and drop file here", type=["pdf","docx","txt","png","jpg","jpeg"], label_visibility="collapsed")
            pasted = st.text_area("Paste your notes here…", height=180, label_visibility="collapsed")
            st.markdown('</div>', unsafe_allow_html=True)
    with upc2:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("**Tip:** You can paste plain notes or upload a file. If your PDF includes diagrams, choose *Text + Images* when prompted.")
        st.markdown('</div>', unsafe_allow_html=True)

    # ---- Study tool buttons ----
    st.markdown('<div class="label" style="margin-top:14px">✨ Study Tools</div>', unsafe_allow_html=True)
    st.markdown('<div class="tool-row">', unsafe_allow_html=True)
    c1, c2, c3, c4, c5 = st.columns(5)
    go_summary = c1.button("📄 Summaries", help="Turn your notes into concise, exam-ready bullets.")
    go_cards   = c2.button("🧠 Flashcards", help="Active-recall Q/A. Tap to reveal answers.")
    go_quiz    = c3.button("🎯 Quizzes", help="MCQs with instant explanations.")
    go_mock    = c4.button("📝 Mock Exams", help="Full exam: MCQ + short + long + fill. Graded.")
    open_chat  = c5.button("💬 Ask Zentra", help="Ask concepts, line-by-line help, or study plans.")
    st.markdown('</div>', unsafe_allow_html=True)

    # Out container (keeps layout stable)
    out = st.container()

    # ========= PRE-TOOL CHOICE HANDLER =========
    def start_tool(which: str):
        """Handle pre-tool flow: ensure notes, then require 'process choice' if a file is uploaded."""
        text, imgs = ensure_notes(pasted, uploaded)
        # If a file (of any type) is uploaded, ask: text vs vision
        if uploaded is not None and ss.process_choice is None:
            ss.pending_tool = which
            ss.temp_text, ss.temp_images = text, imgs
            st.rerun()
        else:
            run_tool(which, ss.process_choice or "text", text)

    # Render the choice bar only when needed
    if ss.pending_tool and ss.process_choice is None:
        with st.container():
            st.markdown('<div class="choice">', unsafe_allow_html=True)
            st.markdown(f"**How should Zentra process your file?** (for: `{ss.last_title}`)")
            choice = st.radio(
                "Processing mode",
                ["Text only", "Text + Images/Diagrams"],
                horizontal=True,
                label_visibility="collapsed",
                key="choice_radio"
            )
            cont_label = {
                "summary":"Continue → Summaries",
                "cards":"Continue → Flashcards",
                "quiz":"Continue → Quizzes",
                "mock":"Continue → Mock Exam",
            }.get(ss.pending_tool, "Continue")
            if st.button(cont_label):
                ss.process_choice = "vision" if "Images" in choice else "text"
                # run and clear
                run_tool(ss.pending_tool, ss.process_choice, ss.temp_text)
                ss.pending_tool = None
                ss.temp_text, ss.temp_images = "", []
            st.markdown('</div>', unsafe_allow_html=True)

    # ========= TOOL EXECUTION =========
    def run_tool(which: str, mode: str, text: str):
        if which == "summary":
            do_summary(text, mode)
        elif which == "cards":
            do_cards(text, mode)
        elif which == "quiz":
            do_quiz(text, mode)
        elif which == "mock":
            do_mock(text, mode)

    # ---------- Tool implementations ----------
    def do_summary(txt: str, mode: str):
        with st.spinner("Generating summary…"):
            vision_hint = "Consider diagrams/figures when inferring key points." if mode == "vision" else "Ignore images/figures."
            prompt = f"""Create clear, exam-ready bullet summaries. {vision_hint}
Be concise, factual, and well-structured.
Notes:
{txt}
"""
            out_text = ask_llm_text(prompt)
        out.subheader("✅ Summary")
        out.markdown(out_text or "_(empty)_")

    def do_cards(txt: str, mode: str):
        with st.spinner("Generating flashcards…"):
            vision_hint = "If diagrams likely exist, turn them into Q prompts." if mode == "vision" else "Base only on text."
            prompt = f"""Return JSON with an array 'cards' of flashcards; each has 'q' and 'a'.
1 concept per card. {vision_hint}
Limit to 12 cards max.

Notes:
{txt}
JSON ONLY."""
            raw = ask_llm_text(prompt)
        cards = []
        try:
            data = json.loads(raw)
            cards = data.get("cards") or []
        except Exception:
            # Fallback: split lines
            cards = [{"q": line.strip(), "a": "Answer"} for line in raw.split("\n") if line.strip()][:10]

        out.subheader("🧠 Flashcards")
        if not cards:
            out.info("No cards generated.")
            return
        # reveal-on-click via expanders
        for i, c in enumerate(cards, 1):
            with st.expander(f"Card {i}: {c.get('q','(blank)')}"):
                st.markdown(c.get("a","(no answer)"))

    def do_quiz(txt: str, mode: str):
        with st.spinner("Building quiz…"):
            n = adaptive_quiz_count(txt)
            vision_hint = "Consider diagrams if relevant to the question topics." if mode == "vision" else "Ignore diagrams."
            prompt = f"""Create a multiple-choice quiz of {n} questions.
Return strict JSON with:
{{"questions":[{{"q":"...", "choices":["A) ...","B) ...","C) ...","D) ..."], "answer":"A", "explanation":"..."}} ... ]}}

Guidelines:
- Four options A–D for each.
- Balanced difficulty, unambiguous answers.
- {vision_hint}

Notes:
{txt}
JSON ONLY."""
            raw = ask_llm_text(prompt)
        try:
            quiz = json.loads(raw).get("questions", [])
        except Exception:
            quiz = []

        if not quiz:
            out.warning("Could not generate a structured quiz. Try again with clearer notes.")
            return

        out.subheader("🎯 Quiz")
        with st.form("quiz_form", clear_on_submit=False):
            picks = []
            for i, q in enumerate(quiz, 1):
                st.markdown(f"**Q{i}. {q['q']}**")
                # choices arrive as ["A) ...", ...] — show as radio
                options = q["choices"]
                pick = st.radio(f"Pick {i}", ["A","B","C","D"], horizontal=True, key=f"quiz_{i}")
                st.caption(" ".join(options))
                st.markdown("---")
                picks.append(pick)

            submitted = st.form_submit_button("Submit Quiz")
            if submitted:
                correct = 0
                res_lines = []
                for i,(q,p) in enumerate(zip(quiz,picks),1):
                    ans = q["answer"].strip()
                    ok = (p == ans)
                    if ok: correct += 1
                    res_lines.append(f"**Q{i}** — Your: **{p}** | Answer: **{ans}**  \n_{q.get('explanation','')}_" )
                score = round(100*correct/len(quiz))
                st.success(f"Score: **{score}/100**  ({correct} / {len(quiz)})")
                st.markdown("\n\n".join(res_lines))
                ss.history_quiz.append(f"{ss.last_title} — {score}/100")

    def do_mock(txt: str, mode: str):
        out.subheader("📝 Mock Exam")
        with st.form("mock_form", clear_on_submit=False):
            diff = st.radio("Select difficulty", ["Easy","Standard","Hard"], horizontal=True, key="mock_diff")
            st.caption("MCQ + Short + Long + Fill-in. Submit to grade out of 100.")
            build_prompt = f"""Create a mock exam as JSON with:
{{
 "mcq":[{{"q":"...", "choices":["A) ...","B) ...","C) ...","D) ..."], "answer":"A"}} x5],
 "short":[{{"q":"...","sample_answer":"..."}} x2],
 "long":[{{"q":"...","sample_answer":"..."}} x1],
 "fill":[{{"q":"...","answer":"..."}} x2]
}}
Difficulty: {diff}. Keep questions unambiguous, exam-like.
{"Consider diagrams if relevant." if mode=="vision" else "Ignore diagrams."}

Notes:
{txt}
JSON ONLY."""
            with st.spinner("Preparing mock…"):
                raw = ask_llm_text(build_prompt)
            try:
                mock = json.loads(raw)
            except Exception:
                st.error("Mock could not be generated. Try again.")
                return

            # Render inputs
            mcq_ans = []
            st.markdown("#### MCQs")
            for i, q in enumerate(mock.get("mcq", [])[:5], 1):
                st.markdown(f"**Q{i}. {q['q']}**")
                pick = st.radio(f"Pick {i}", ["A","B","C","D"], horizontal=True, key=f"m_mcq_{i}")
                st.caption(" ".join(q["choices"]))
                st.markdown("---")
                mcq_ans.append(pick)

            st.markdown("#### Short Answers")
            short_ans = []
            for i, q in enumerate(mock.get("short", [])[:2], 1):
                short_ans.append(st.text_area(f"Short {i}: {q['q']}", key=f"m_short_{i}"))

            st.markdown("#### Long Answer")
            long_q = (mock.get("long") or [{"q":"(missing)"}])[0]["q"]
            long_ans = st.text_area(f"Essay: {long_q}", key="m_long")

            st.markdown("#### Fill-in")
            fill_ans = []
            for i, q in enumerate(mock.get("fill", [])[:2], 1):
                fill_ans.append(st.text_input(f"Fill {i}: {q['q']}", key=f"m_fill_{i}"))

            submitted = st.form_submit_button("Submit Mock for Grading")
            if submitted:
                # Grade via LLM (no answer key displayed to student)
                grading_prompt = f"""You are Zentra, a strict but fair examiner.
Grade the student's mock out of 100 with a clear breakdown:
- Section scores (MCQ / Short / Long / Fill)
- Strengths
- Weak areas
- Targeted advice

STUDENT ANSWERS:
MCQs: {mcq_ans}
Short: {short_ans}
Long: {long_ans}
Fill: {fill_ans}

ORIGINAL MOCK (for reference):
{json.dumps(mock)}

Return concise feedback. Start with a single line: "Score: NN/100"."""
                with st.spinner("Grading…"):
                    result = ask_llm_text(grading_prompt)
                st.success("✅ Mock graded")
                st.markdown(result)
                # Extract first number for history if present
                first_line = (result.splitlines() or [""])[0]
                ss.history_mock.append(f"{ss.last_title} — {first_line}")

    # --- Button actions (defer running until choice made) ---
    if go_summary: start_tool("summary")
    if go_cards:   start_tool("cards")
    if go_quiz:    start_tool("quiz")
    if go_mock:    start_tool("mock")

# ----------------
# CHAT COLUMN
# ----------------
with col_chat:
    st.markdown("### 💬 Ask Zentra")
    c1, c2 = st.columns([1,1], vertical_alignment="center")
    if c1.button("Close"): ss.chat_open = False; st.rerun()
    if c2.button("Clear"): ss.messages = []; st.rerun()

    if ss.chat_open:
        st.markdown('<div class="chat-wrap"><div class="chat-box" id="chat-box">', unsafe_allow_html=True)
        # Show messages
        for m in ss.messages:
            role = "🧑‍🎓 You" if m["role"]=="user" else "🤖 Zentra"
            st.markdown(f"<div class='chat-msg'><span class='chat-role'>{role}:</span>{m['content']}</div>", unsafe_allow_html=True)
        st.markdown("</div></div>", unsafe_allow_html=True)
        # Auto scroll
        st.markdown("<script>var box=document.getElementById('chat-box'); if(box){box.scrollTop=box.scrollHeight;}</script>", unsafe_allow_html=True)

        q = st.chat_input("Ask Zentra…")
        if q:
            ss.messages.append({"role":"user","content":q})
            # Keep chat independent (no weird personal stuff)
            prompt = f"""Answer as a helpful tutor. Only use the user's question.
If it references the uploaded notes, you may use them; otherwise, do not invent any personal context.
User: {q}
Notes (if relevant): {ss.notes_text[:4000]}
"""
            ans = ask_llm_text(prompt, system="You are Zentra, a precise and calm tutor. No fluff, no personal guesses.")
            ss.messages.append({"role":"assistant","content":ans})
            st.rerun()
