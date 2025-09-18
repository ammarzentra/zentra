# app.py — Zentra (PRO BUILD • polished UI • fixed reruns • full tools + chat)
# Requires Streamlit secrets:
# OPENAI_API_KEY, SUPABASE_URL, SUPABASE_ANON_KEY, LEMON_CHECKOUT_URL

import os, io, base64, tempfile, re, time, traceback
from typing import List, Tuple
import streamlit as st

# =========================
# Secrets & Env
# =========================
try:
    OPENAI_API_KEY     = st.secrets["OPENAI_API_KEY"]
    SUPABASE_URL       = st.secrets.get("SUPABASE_URL", "")
    SUPABASE_ANON_KEY  = st.secrets.get("SUPABASE_ANON_KEY", "")
    LEMON_CHECKOUT_URL = st.secrets.get("LEMON_CHECKOUT_URL", "https://example.com")
except Exception:
    st.error("Missing secrets. Add OPENAI_API_KEY, SUPABASE_URL, SUPABASE_ANON_KEY, LEMON_CHECKOUT_URL.")
    st.stop()

os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

# Dev bypass ON until Lemon goes live
DEV_BYPASS = True

# =========================
# Models & OpenAI client
# =========================
from openai import OpenAI
_CLIENT = None
MODEL_TEXT   = "gpt-4o-mini"
MODEL_VISION = "gpt-4o-mini"
BASE_SYSTEM  = "You are Zentra, a precise, supportive, exam-focused tutor. Be concise and correct."

def _client() -> OpenAI:
    global _CLIENT
    if _CLIENT: return _CLIENT
    _CLIENT = OpenAI()
    return _CLIENT

def ask_llm(prompt: str, system: str = BASE_SYSTEM) -> str:
    try:
        r = _client().chat.completions.create(
            model=MODEL_TEXT,
            messages=[{"role":"system","content":system},
                      {"role":"user","content":prompt}],
            temperature=0.4,
        )
        return (r.choices[0].message.content or "").strip()
    except Exception as e:
        return f"⚠️ Model error: {e}"

def ask_vision(prompt: str, images: List[Tuple[str, bytes]], text_hint: str) -> str:
    parts = [
        {"type":"text","text":"You are Zentra. Use BOTH images and text. Keep answers exam-ready and concise."},
        {"type":"text","text": f"TEXT:\n{text_hint}\n\nTASK:\n{prompt}"}
    ]
    for name, b in images[:2]:
        b64 = base64.b64encode(b).decode()
        mime = "image/png" if name.lower().endswith(".png") else "image/jpeg"
        parts.append({"type":"image_url","image_url":{"url": f"data:{mime};base64,{b64}"}})
    try:
        r = _client().chat.completions.create(
            model=MODEL_VISION,
            messages=[{"role":"user","content":parts}],
            temperature=0.4
        )
        return (r.choices[0].message.content or "").strip()
    except Exception as e:
        return f"⚠️ Vision error: {e}"

# =========================
# Page config & CSS
# =========================
st.set_page_config(
    page_title="Zentra — AI Study Buddy",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
/* Layout polish */
footer{visibility:hidden;height:0}
.block-container{padding-top:0.6rem; padding-bottom:3rem; max-width:1200px;}
html, body, [data-testid="stAppViewContainer"]{
  background: radial-gradient(1200px 600px at 10% -10%, #2a2b47 0%, transparent 60%),
              radial-gradient(900px 400px at 110% 10%, #1b2649 0%, transparent 55%),
              linear-gradient(180deg, #0b0f1a 0%, #0a0d17 100%) !important;
}

/* Nav */
.navbar{
  display:flex; align-items:center; justify-content:space-between;
  background:#0e1117; border:1px solid #232b3a; border-radius:14px;
  padding:10px 14px; margin:2px 0 10px;
}
.brand{font-weight:900; font-size:18px; color:#e8ecf7}
.navpill{padding:6px 10px; border:1px solid #2b3550; border-radius:10px; font-size:12px; opacity:.9}
.navright{display:flex; gap:8px; align-items:center}

/* Hero */
.hero{ background: linear-gradient(90deg,#6a11cb 0%,#2575fc 100%);
  border-radius:18px; color:#fff; text-align:center; padding:20px 18px; margin:6px 0 12px;
  box-shadow:0 8px 30px rgba(0,0,0,.25); }
.hero h1{margin:0; font-size:38px; font-weight:900; letter-spacing:.3px;}
.hero p{margin:4px 0 0; opacity:.92}

/* Paywall */
.paywall{
  background: rgba(17, 20, 32, 0.88);
  border: 1px solid #2c3550; border-radius: 22px; padding: 40px 28px; color:#e8ecf7;
  text-align:center; margin:26px auto; max-width:820px; box-shadow: 0 20px 50px rgba(0,0,0,.40);
}
.paywall h1{margin:0; font-size:44px; font-weight:900;}
.pill{display:inline-block; padding:6px 12px; border-radius:999px; border:1px solid #3a4466; background:#12182a; font-size:13px; opacity:.95; margin-bottom:8px;}
.features{text-align:left; margin:16px auto 6px; display:inline-block; font-size:15px; line-height:1.45; max-width:640px}
.features li{margin:6px 0;}
.subscribe-btn{
  background:#1d4ed8; color:#fff; padding:14px 28px; border-radius:12px; text-decoration:none; font-size:18px; font-weight:800; letter-spacing:.2px;
  display:inline-block; transition: transform .06s ease, background .2s ease; border:1px solid #2a55d8;
}
.subscribe-btn:hover{ background:#1842b7; transform: translateY(-1px); }
.dev-link{display:block; margin-top:12px; font-size:13px; opacity:.75}

/* Cards & inputs */
.upload-card{background:#0e1117; border:1px solid #232b3a; border-radius:16px; padding:16px; margin-bottom:10px;}
.upload-title{font-weight:800; font-size:18px; margin-bottom:6px}
textarea[aria-label="Paste your notes here…"]{min-height:180px}
.section-title{font-weight:900; font-size:20px; margin:10px 0 12px;}
.tool-row .stButton>button{
  width:100%; border-radius:12px; border:1px solid #2b2f3a; padding:10px; background:#10141e; color:#e8ecf7; font-weight:800; white-space:nowrap;
}
.tool-row .stButton>button:hover{background:#141a27; border-color:#3a4252;}
.results-box{ border:1px solid #232b3a; background:#0e1117; border-radius:14px; padding:14px; min-height:160px; }

/* Chat */
.chat-card{background:#0e1117; border:1px solid #232b3a; border-radius:14px; padding:10px;}
.msguser{color:#9ecbff} .msgai{color:#c0d5ff}
hr{border: none; border-top: 1px solid #222a3a; margin: 10px 0;}
</style>
""", unsafe_allow_html=True)

# =========================
# Top Nav
# =========================
st.markdown(
    '<div class="navbar"><div class="brand">⚡ Zentra</div>'
    '<div class="navright"><span class="navpill">Active recall</span>'
    '<span class="navpill">Autograded mocks</span><span class="navpill">On-demand tutor</span></div></div>',
    unsafe_allow_html=True
)

# =========================
# State
# =========================
ss = st.session_state
for k, v in {
    "dev_unlocked": False,
    "chat_open": False,
    "messages": [],
    "history_quiz": [],
    "history_mock": [],
    "notes_text": "",
    "last_title": "Untitled notes",
    "pending_tool": None,         # 'summary'|'flash'|'quiz'|'mock'
    "process_choice": None,       # 'Text only' | 'Text + Images/Diagrams'
    "mock_diff": "Standard",
    "flash_state": {},
}.items():
    if k not in ss: ss[k] = v

# =========================
# File handling
# =========================
def read_file(uploaded) -> Tuple[str, List[Tuple[str, bytes]]]:
    if not uploaded: return "", []
    name = uploaded.name.lower()
    data = uploaded.read()
    text = ""
    images: List[Tuple[str, bytes]] = []
    if name.endswith(".txt"):
        text = data.decode("utf-8","ignore")
    elif name.endswith(".pdf"):
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data))
            pages = [(p.extract_text() or "") for p in reader.pages]
            text = "\n".join(pages)
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
        text = data.decode("utf-8","ignore")
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
        st.warning("Looks empty. If your PDF is image-only, choose **Text + Images/Diagrams** or upload OCR text.")
        st.stop()
    ss.notes_text = txt
    return txt, imgs

def adaptive_quiz_count(txt: str) -> int:
    return max(4, min(16, len(txt.split()) // 180))

def rounded_score_from_len(txt: str) -> int:
    w = max(1, len(txt.split()))
    if w < 300: return 30
    if w < 700: return 50
    if w < 1200: return 70
    if w < 2000: return 90
    return 100

# =========================
# Hero
# =========================
st.markdown('<div class="hero"><h1>AI Study Buddy</h1><p>Smarter notes → Better recall → Higher scores.</p></div>', unsafe_allow_html=True)

# =========================
# Paywall (Dev bypass visible)
# =========================
if DEV_BYPASS and not ss.dev_unlocked:
    st.markdown(f"""
    <div class="paywall">
      <div class="pill">7-day free trial • Cancel anytime</div>
      <h1>Zentra — AI Study Buddy</h1>
      <p>Turn messy notes into laser-focused summaries, flashcards, quizzes that teach, and graded mock exams — plus an on-demand tutor.</p>
      <a class="subscribe-btn" href="{LEMON_CHECKOUT_URL}" target="_blank">Subscribe — $5.99 / month</a>
      <a class="dev-link" href="#" onclick="window.parent.postMessage({{type:'devLogin'}}, '*'); return false;">(Dev login for testing)</a>
      <div class="features">
        <ul>
          <li>📄 Summaries — exam-ready bullets that cover what matters</li>
          <li>🧠 Flashcards — active recall, reveal when ready</li>
          <li>🎯 Quizzes — auto-scored with key explanations</li>
          <li>📝 Mock Exams — MCQ + short + long + fill-in, graded</li>
          <li>💬 Ask Zentra — your tutor for any topic</li>
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
          const d = window.parent.document;
          const btn = [...d.querySelectorAll('button')].find(b=>b.innerText.includes("Dev Login"));
          if(btn) btn.click();
        }
      });
    </script>
    """, height=0)
    st.stop()

# =========================
# Sidebar
# =========================
with st.sidebar:
    st.markdown("### 🌟 Why students love Zentra")
    st.write("Shrink long notes into tight summaries, drill key ideas with flashcards, and test yourself with quizzes & mocks that teach — all in one workspace.")
    st.caption("Active recall • Structured practice • Autograded mocks • On-demand tutor")

    st.markdown("### 📂 History")
    if ss.history_quiz:
        st.caption("Recent Quizzes")
        for i, item in enumerate(reversed(ss.history_quiz[-8:])):
            c = st.columns([5,1])
            with c[0]: st.write(f"• {item.get('title','Quiz')} — {item.get('score','—')}")
            with c[1]:
                if st.button("🗑️", key=f"del_q_{i}"):
                    orig = list(ss.history_quiz)
                    for j in range(len(orig)-1, -1, -1):
                        if orig[j] == item:
                            ss.history_quiz.pop(j); break
                    st.rerun()
    else:
        st.caption("Recent Quizzes"); st.write("—")

    if ss.history_mock:
        st.caption("Recent Mock Exams")
        for i, item in enumerate(reversed(ss.history_mock[-8:])):
            c = st.columns([5,1])
            with c[0]: st.write(f"• {item.get('title','Mock')} — {item.get('score','—')}")
            with c[1]:
                if st.button("🗑️", key=f"del_m_{i}"):
                    orig = list(ss.history_mock)
                    for j in range(len(orig)-1, -1, -1):
                        if orig[j] == item:
                            ss.history_mock.pop(j); break
                    st.rerun()
    else:
        st.caption("Recent Mock Exams"); st.write("—")

    st.markdown("---")
    if st.button("Clear All History"):
        ss.history_quiz, ss.history_mock = [], []
        st.rerun()
    st.caption("Disclaimer: AI-generated. Verify before exams.")

# =========================
# Main layout
# =========================
col_main, col_chat = st.columns([3, 1.35], gap="large")

# ---------- MAIN ----------
with col_main:
    # Upload
    st.markdown('<div class="upload-card"><div class="upload-title">📁 Upload Your Notes</div>', unsafe_allow_html=True)
    up_left, up_right = st.columns([3,2], vertical_alignment="bottom")
    with up_left:
        uploaded = st.file_uploader("Upload file", type=["pdf","docx","txt","png","jpg","jpeg"], label_visibility="collapsed")
        pasted   = st.text_area("Paste your notes here…", height=180, label_visibility="collapsed")
    with up_right:
        st.caption("If your file has diagrams, choose **Text + Images/Diagrams** below.")
    st.markdown('</div>', unsafe_allow_html=True)

    # Tools
    st.markdown('<div class="section-title">✨ Study Tools</div>', unsafe_allow_html=True)
    st.markdown('<div class="tool-row">', unsafe_allow_html=True)
    a,b,c,d,e = st.columns(5)
    go_summary = a.button("📄 Summaries")
    go_cards   = b.button("🧠 Flashcards")
    go_quiz    = c.button("🎯 Quizzes")
    go_mock    = d.button("📝 Mock Exams")
    open_chat  = e.button("💬 Ask Zentra")
    st.markdown('</div>', unsafe_allow_html=True)

    if open_chat:
        ss.chat_open = True
        st.rerun()

    results_placeholder = st.empty()

    # Set pending tool
    if go_summary: ss.pending_tool, ss.process_choice = "summary", None; st.rerun()
    if go_cards:   ss.pending_tool, ss.process_choice = "flash",   None; st.rerun()
    if go_quiz:    ss.pending_tool, ss.process_choice = "quiz",    None; st.rerun()
    if go_mock:    ss.pending_tool, ss.process_choice = "mock",    None; st.rerun()

    def collect_inputs():
        text, imgs = ensure_notes(pasted, uploaded)
        return text, imgs

    if ss.pending_tool:
        with st.expander("How should Zentra process your file?", expanded=True):
            ss.process_choice = st.radio("", ["Text only", "Text + Images/Diagrams"],
                                         index=0, horizontal=True, label_visibility="collapsed")
            x,y,_ = st.columns([1,1,6])
            with x: go = st.button("Continue", type="primary", key="proc_go")
            with y: cancel = st.button("Cancel", key="proc_cancel")

        if cancel:
            ss.pending_tool, ss.process_choice = None, None
            st.rerun()

        if go:
            text, imgs = collect_inputs()
            include_images = (ss.process_choice == "Text + Images/Diagrams")

            with results_placeholder.container():
                st.markdown('<div class="results-box">', unsafe_allow_html=True)

                # ---------- SUMMARY ----------
                if ss.pending_tool == "summary":
                    st.subheader("✅ Summary")
                    with st.spinner("Generating summary…"):
                        prompt = f"""Summarize the following notes into **clean, exam-ready bullet points**.
Cover definitions, theorems/laws, key steps, formulas, and 'must-know' facts. Be tight and complete.
NOTES:
{text}"""
                        out = ask_vision(prompt, imgs, text) if (include_images and imgs) else ask_llm(prompt)
                    st.markdown(out or "_(no content)_")

                # ---------- FLASHCARDS ----------
                elif ss.pending_tool == "flash":
                    st.subheader("🧠 Flashcards")
                    with st.spinner("Creating flashcards…"):
                        prompt = f"""Create high-quality flashcards that **cover all key points**.
Return each card exactly as:
**Q:** …
**A:** …
NOTES:
{text}"""
                        raw = ask_vision(prompt, imgs, text) if (include_images and imgs) else ask_llm(prompt)

                    cards = []
                    for line in raw.splitlines():
                        s = line.strip().strip("-").strip()
                        if s.startswith("**Q:**") or s.lower().startswith("q:"):
                            cards.append({"q": s.split(":",1)[1].strip(), "a": ""})
                        elif (s.startswith("**A:**") or s.lower().startswith("a:")) and cards:
                            cards[-1]["a"] = s.split(":",1)[1].strip()

                    if not cards:
                        st.markdown(raw or "_(no content)_")
                    else:
                        for i, card in enumerate(cards):
                            key_q = f"flash_reveal_{i}"
                            if key_q not in ss.flash_state: ss.flash_state[key_q] = False
                            cols = st.columns([7,2])
                            with cols[0]:
                                st.markdown(f"**Q{i+1}:** {card['q']}")
                                if ss.flash_state[key_q]:
                                    st.markdown(f"**A:** {card['a']}")
                            with cols[1]:
                                if not ss.flash_state[key_q]:
                                    if st.button("Reveal", key=f"reveal_{i}"):
                                        ss.flash_state[key_q] = True; st.rerun()
                                else:
                                    if st.button("Hide", key=f"hide_{i}"):
                                        ss.flash_state[key_q] = False; st.rerun()

                # ---------- QUIZ ----------
                elif ss.pending_tool == "quiz":
                    st.subheader("🎯 Quiz")
                    n = adaptive_quiz_count(text)
                    with st.spinner("Generating quiz…"):
                        prompt = f"""Create {n} multiple-choice questions (A–D).
Return a numbered list of questions with four options A–D.
At the end include an **Answer Key** line exactly like:
Answer Key: 1) B, 2) D, 3) A, ...
Ensure coverage across the notes.
NOTES:
{text}"""
                        raw = ask_vision(prompt, imgs, text) if (include_images and imgs) else ask_llm(prompt)

                    with st.form("quiz_form", clear_on_submit=False):
                        st.markdown(raw)
                        st.markdown("---")
                        st.caption("Your Answers")
                        answers = [st.radio(f"Q{i+1}", ["A","B","C","D"], key=f"quiz_ans_{i}", horizontal=True) for i in range(n)]
                        submitted = st.form_submit_button("Submit Quiz")
                        if submitted:
                            blob = raw.replace("\n"," ")
                            m = re.search(r"Answer\s*Key\s*:\s*(.+)$", blob, re.IGNORECASE)
                            correct = []
                            if m:
                                key_line = m.group(1)
                                pairs = re.findall(r"(\d+)\s*\)\s*([ABCD])", key_line)
                                correct = [p[1] for p in sorted(pairs, key=lambda x:int(x[0]))]
                            score = sum(1 for i in range(min(len(answers), len(correct))) if answers[i]==correct[i])
                            detail = [f"Q{i+1}: {'✅' if answers[i]==correct[i] else '❌'} (Your: {answers[i]} | Ans: {correct[i]})"
                                      for i in range(min(len(answers), len(correct)))]
                            score_str = f"{score}/{len(correct)} correct"
                            st.success(f"Score: {score_str}")
                            st.markdown("\n".join(detail))
                            ss.history_quiz.append({"title": ss.last_title, "score": score_str})

                # ---------- MOCK ----------
                elif ss.pending_tool == "mock":
                    st.subheader("📝 Mock Exam")
                    with st.expander("Select difficulty", expanded=True):
                        ss.mock_diff = st.radio("", ["Easy","Standard","Hard"], horizontal=True,
                                                index=["Easy","Standard","Hard"].index(ss.mock_diff),
                                                label_visibility="collapsed")
                    total_max = rounded_score_from_len(text)
                    with st.spinner("Building mock exam…"):
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

                    st.markdown(raw)

                    with st.form("mock_form", clear_on_submit=False):
                        st.markdown("---"); st.caption("Your Answers")
                        mcq_ans   = [st.radio(f"MCQ {i+1}", ["A","B","C","D"], key=f"mock_mcq_{i}", horizontal=True) for i in range(5)]
                        short_ans = [st.text_area(f"Short Answer {i+1}", key=f"mock_short_{i}") for i in range(2)]
                        long_ans  = st.text_area("Long Answer (Essay)", key="mock_long")
                        fill_ans  = [st.text_input(f"Fill in {i+1}", key=f"mock_fill_{i}") for i in range(2)]
                        submit    = st.form_submit_button("Submit Mock for Grading")
                        if submit:
                            with st.spinner("Grading your mock…"):
                                grading = f"""You are Zentra. Grade the student's mock strictly using the provided rubric.
Total points must be an integer multiple of 10 with max {total_max}.
Provide:
- Total Score (e.g., 60/{total_max})
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

                st.markdown('</div>', unsafe_allow_html=True)

            # close tool and refresh
            ss.pending_tool, ss.process_choice = None, None
            st.rerun()

# ---------- CHAT ----------
with col_chat:
    if ss.chat_open:
        st.markdown("### 💬 Ask Zentra")
        for m in ss.messages:
            if m["role"] == "user":
                st.markdown(f"🧑‍🎓 **You:** {m['content']}")
            else:
                st.markdown(f"🤖 **Zentra:** {m['content']}")

        user_q = st.chat_input("Type your message…")
        if user_q:
            ss.messages.append({"role":"user","content":user_q})
            with st.spinner("Thinking…"):
                reply = ask_llm(
                    "You are **Zentra**. Answer clearly and briefly. "
                    "Only reference uploaded notes if the user explicitly asks about them.\n\n"
                    f"USER: {user_q}"
                )
            ss.messages.append({"role":"assistant","content":reply})
            st.rerun()

        cols = st.columns(2)
        with cols[0]:
            if st.button("Close"):
                ss.chat_open = False; st.rerun()
        with cols[1]:
            if st.button("Clear"):
                ss.messages = []; st.rerun()
