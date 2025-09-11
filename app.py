# app.py — Zentra (PAYWALL + LEMON SQUEEZY + SUPABASE + Full App)
# Secrets required in Streamlit:
#   OPENAI_API_KEY
#   SUPABASE_URL
#   SUPABASE_ANON_KEY
#   LEMON_CHECKOUT_URL  (e.g. https://zentraai.lemonsqueezy.com/buy/xxxxxxxx)
#
# DB (Supabase) table required: subscriptions
#   columns: id (text), email (text), status (text), ends_at (timestamptz), created_at (timestamptz)

import os, io, base64, tempfile, datetime
from typing import List, Tuple

import streamlit as st
from openai import OpenAI

# ---------- PAGE SETUP ----------
st.set_page_config(
    page_title="Zentra — AI Study Buddy",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------- GLOBAL STYLES ----------
st.markdown("""
<style>
/* Hide Streamlit footer/watermark */
a[class*="viewerBadge"], div[class*="viewerBadge"], #ViewerBadgeContainer{display:none!important;}
footer{visibility:hidden;height:0}

/* Container + hero */
.block-container{padding-top:1rem;padding-bottom:3rem;max-width:1200px;}
.hero{background:linear-gradient(90deg,#6a11cb 0%,#2575fc 100%);
padding:22px;border-radius:16px;color:#fff;margin-bottom:14px;}
.hero h1{margin:0;font-size:34px}
.hero p{margin:6px 0 0;opacity:.92}

/* Paywall */
.paywrap{display:flex;justify-content:center;align-items:center;}
.paycard{
  width:min(920px,96vw); background:#0f1221; color:#fff; border:1px solid rgba(255,255,255,.08);
  border-radius:18px; overflow:hidden; box-shadow:0 10px 40px rgba(0,0,0,.5);
}
.paytop{
  background: radial-gradient(1200px 300px at center -100px, #7c4dff 0%, transparent 70%),
              linear-gradient(135deg,#6a11cb 0%,#2575fc 100%);
  padding:28px 26px;
}
.paytop h2{margin:0;font-size:30px}
.paygrid{display:grid;grid-template-columns: 1.2fr .8fr; gap:0; }
.payleft{padding:22px 26px}
.payright{padding:22px 26px; border-left:1px solid rgba(255,255,255,.06); background:#0b0e1a}
.kicker{display:inline-block; padding:6px 10px; border-radius:999px; background:rgba(255,255,255,.12); font-size:12px; letter-spacing:.5px; margin-bottom:10px}
.big{font-size:38px; font-weight:800; margin:.25rem 0}
.badge{display:inline-block; font-size:12px; padding:4px 10px; border:1px solid rgba(255,255,255,.2); border-radius:999px; margin-right:6px; opacity:.9}
.features{columns:2; column-gap:26px; margin:10px 0 4px}
.features li{margin:6px 0}
.small{opacity:.8; font-size:13px}

/* Inputs + buttons */
.input{width:100%; padding:12px 14px; border-radius:10px; border:1px solid #2b2e3c; background:#0b0e1a; color:#fff; outline:none}
.input:focus{border-color:#6a9bff}
.btn{
  display:inline-block; width:100%; text-align:center; padding:12px 16px; border-radius:12px; border:none;
  background:#f72585; color:#fff; font-weight:700; cursor:pointer; transition:.15s transform, .2s background;
}
.btn:hover{background:#d3136d; transform:translateY(-1px)}
.btn.secondary{background:#14182a; border:1px solid #2b2e3c}
.btn.secondary:hover{background:#1a1f35}
.buttonrow{display:flex; gap:10px; margin-top:10px}

/* Right column bullets */
.price{font-size:28px; font-weight:800; margin:0}
.check{display:flex; gap:8px; align-items:center; margin:6px 0; opacity:.92}

/* Study tools row spacing */
.stButton>button{border-radius:12px}
</style>
""", unsafe_allow_html=True)

# ---------- STATE ----------
if "subscribed" not in st.session_state: st.session_state.subscribed = False
if "user_email" not in st.session_state: st.session_state.user_email = ""
if "chat_open" not in st.session_state: st.session_state.chat_open = False
if "messages" not in st.session_state: st.session_state.messages = []
if "history_quiz" not in st.session_state: st.session_state.history_quiz = []
if "history_mock" not in st.session_state: st.session_state.history_mock = []
if "notes_text" not in st.session_state: st.session_state.notes_text = ""
if "last_title" not in st.session_state: st.session_state.last_title = "Untitled notes"
if "pending_mock" not in st.session_state: st.session_state.pending_mock = False

# ---------- ENV / CLIENTS ----------
def _openai() -> OpenAI:
    key = st.secrets.get("OPENAI_API_KEY")
    if not key:
        st.error("Missing OPENAI_API_KEY in Secrets"); st.stop()
    os.environ["OPENAI_API_KEY"] = key
    return OpenAI()

# Supabase (read-only) for access check
SUPABASE_URL = st.secrets.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = st.secrets.get("SUPABASE_ANON_KEY", "")
LEMON_CHECKOUT_URL = st.secrets.get("LEMON_CHECKOUT_URL", "")

supabase = None
if SUPABASE_URL and SUPABASE_ANON_KEY:
    try:
        from supabase import create_client
        supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    except Exception:
        supabase = None

MODEL = "gpt-4o-mini"

def ask_llm(prompt: str, system="You are Zentra, a precise and supportive study buddy. Be concise and clear."):
    r = _openai().chat.completions.create(
        model=MODEL,
        messages=[{"role":"system","content":system},{"role":"user","content":prompt}],
        temperature=0.4,
    )
    return r.choices[0].message.content.strip()

# ---------- FILE PARSE ----------
def read_file(uploaded) -> Tuple[str, List[Tuple[str, bytes]]]:
    if not uploaded: return "", []
    name = uploaded.name.lower(); data = uploaded.read()
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
        text = data.decode("utf-8","ignore")
    return (text or "").strip(), images

def ensure_notes(pasted, uploaded):
    txt = (pasted or "").strip()
    imgs: List[Tuple[str, bytes]] = []
    if uploaded:
        t, ii = read_file(uploaded)
        if t: txt = (txt + "\n" + t).strip() if txt else t
        if ii: imgs = ii
        st.session_state.last_title = uploaded.name
    if len(txt) < 5 and not imgs:
        st.warning("Your notes look empty. Paste text or upload a readable PDF/DOCX.")
        st.stop()
    st.session_state.notes_text = txt
    return txt, imgs

def adaptive_quiz_count(txt: str) -> int:
    return max(3, min(20, len(txt.split()) // 180))

# ---------- ACCESS CHECK ----------
def has_active_subscription(email: str) -> bool:
    """
    Reads Supabase 'subscriptions' for the email.
    Active if:
      - status in ('active','on_trial','trialing','past_due') AND
      - ends_at is in the future (or null for evergreen)
    """
    if not email or not supabase:
        return False
    try:
        res = supabase.table("subscriptions").select("*").eq("email", email.lower()).order("created_at", desc=True).limit(1).execute()
        if not res.data:
            return False
        row = res.data[0]
        status = (row.get("status") or "").lower()
        ends_at = row.get("ends_at")
        ok_status = status in ("active","on_trial","trialing","past_due")
        if not ok_status:
            return False
        if ends_at:
            try:
                # Supabase returns ISO8601 string
                ends = datetime.datetime.fromisoformat(ends_at.replace("Z","+00:00"))
                return ends > datetime.datetime.now(datetime.timezone.utc)
            except Exception:
                return False
        return True
    except Exception:
        return False

# ---------- PAYWALL UI ----------
def show_paywall():
    st.markdown('<div class="paywrap"><div class="paycard">', unsafe_allow_html=True)
    st.markdown('<div class="paytop"><span class="kicker">Zentra • AI Study Buddy</span><h2>Unlock smarter studying</h2></div>', unsafe_allow_html=True)
    st.markdown('<div class="paygrid">', unsafe_allow_html=True)

    # LEFT: Features + email sign-in for check
    st.markdown('<div class="payleft">', unsafe_allow_html=True)
    st.markdown("""
    <div class="badge">Summaries</div>
    <div class="badge">Flashcards</div>
    <div class="badge">Quizzes</div>
    <div class="badge">Mock Exams (graded)</div>
    <div class="badge">Ask Zentra Tutor</div>
    """, unsafe_allow_html=True)

    st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)
    st.markdown("""
    <ul class="features">
      <li>📄 Exam-ready summaries from your notes</li>
      <li>🧠 Active-recall flashcards that actually cover the content</li>
      <li>🎯 Adaptive MCQ quizzes with instant explanations</li>
      <li>📝 Mock exams (MCQ + short + long + fill-in) with grading + feedback</li>
      <li>💬 Ask Zentra: concepts, study plans, line-by-line help</li>
    </ul>
    """, unsafe_allow_html=True)
    st.markdown('<div class="small">7-day free trial • Cancel anytime • Student-friendly pricing</div>', unsafe_allow_html=True)

    with st.form("access_check", clear_on_submit=False):
        email = st.text_input("Enter your email to check access", value=st.session_state.user_email, placeholder="you@university.edu", key="pay_email")
        go = st.form_submit_button("Continue")
        if go:
            st.session_state.user_email = (email or "").strip().lower()
            if has_active_subscription(st.session_state.user_email):
                st.session_state.subscribed = True
                st.success("Access granted. Enjoy Zentra!")
                st.rerun()
            else:
                st.warning("No active subscription found for this email. Use Subscribe below, then click “Refresh access”.")
    st.markdown('</div>', unsafe_allow_html=True)

    # RIGHT: Price + Lemon embed
    st.markdown('<div class="payright">', unsafe_allow_html=True)
    st.markdown('<p class="price">$5.99<span style="font-size:14px;opacity:.75">/month</span></p>', unsafe_allow_html=True)
    st.markdown('<div class="check">✅ 7-day free trial</div>', unsafe_allow_html=True)
    st.markdown('<div class="check">✅ Cancel anytime</div>', unsafe_allow_html=True)
    st.markdown('<div class="check">✅ Works for all subjects</div>', unsafe_allow_html=True)

    # Lemon Squeezy embed
    if LEMON_CHECKOUT_URL:
        st.components.v1.html(f"""
        <script src="https://assets.lemonsqueezy.com/lemon.js" defer></script>
        <a href="{LEMON_CHECKOUT_URL}"
           class="btn"
           data-ls-embed="true"
           style="text-decoration:none;display:block">Subscribe — Start Free Trial</a>
        <div class="buttonrow">
          <button class="btn secondary" onclick="window.parent.postMessage({{type:'refreshZentra'}}, '*')">Refresh access after payment</button>
        </div>
        """, height=120)
    else:
        st.info("Add LEMON_CHECKOUT_URL to Streamlit Secrets to enable in-app checkout.")

    # JS bridge: let “Refresh access” cause a rerun
    st.components.v1.html("""
    <script>
      window.addEventListener("message",(e)=>{
        if(e.data && e.data.type==="refreshZentra"){
          const btns = window.parent.document.querySelectorAll('button');
          if(btns && btns.length){ btns[0].click(); } // nudge a rerun
        }
      });
    </script>
    """, height=0)

    st.markdown('</div>', unsafe_allow_html=True)  # /payright
    st.markdown('</div></div></div>', unsafe_allow_html=True)  # /grid + /card + /wrap

# ---------- PAYWALL GATE ----------
# If not subscribed, show paywall first.
if not st.session_state.subscribed:
    show_paywall()
    st.stop()

# ---------- HERO ----------
st.markdown('<div class="hero"><h1>⚡ Zentra — AI Study Buddy</h1><p>Smarter notes → Better recall → Higher scores.</p></div>', unsafe_allow_html=True)

# ---------- SIDEBAR (TOOLBOX) ----------
with st.sidebar:
    st.markdown("## 📊 Toolbox")
    st.write("**How Zentra Works**: Turns your notes into smart study tools. Consistency + feedback = progress.")
    st.markdown("### 📌 What Zentra Offers")
    st.markdown("- **Summaries** → exam-ready bullets\n- **Flashcards** → active recall Q/A\n- **Quizzes** → adaptive MCQs + explanations\n- **Mock Exams** → graded, multi-section with evaluation\n- **Ask Zentra** → personal AI tutor")
    st.markdown("### 🧪 Mock Evaluation")
    st.write("MCQ, short, long, fill-in. Difficulty: *Easy / Standard / Hard*. Zentra grades with a rubric and gives **personal feedback** on how to improve.")
    st.markdown("### 📂 History")
    st.caption("Recent Quizzes:"); st.write(st.session_state.history_quiz or "—")
    st.caption("Recent Mock Exams:"); st.write(st.session_state.history_mock or "—")
    st.markdown("---")
    st.caption(f"Logged in as: {st.session_state.user_email or 'unknown'}")
    st.caption("Disclaimer: AI-generated. Always verify before exams.")

# ---------- MAIN LAYOUT ----------
col_main, col_chat = st.columns([3, 1.4], gap="large")

# ---------- CORE STUDY APP ----------
with col_main:
    # Upload
    st.markdown("### 📁 Upload your notes")
    cu, cm = st.columns([3,2], vertical_alignment="bottom")
    with cu:
        uploaded = st.file_uploader("Drag and drop file here", type=["pdf","docx","txt","png","jpg","jpeg"], label_visibility="collapsed")
        pasted = st.text_area("Or paste your notes here…", height=150, label_visibility="collapsed")
    with cm:
        st.write("**Analysis mode**")
        mode = st.radio("", ["Text only", "Include images (Vision)"], horizontal=True, label_visibility="collapsed")
    include_images = (mode == "Include images (Vision)")

    # Study tools
    st.markdown("### ✨ Study Tools")
    c1,c2,c3,c4,c5 = st.columns(5)
    go_summary = c1.button("📄 Summaries")
    go_cards   = c2.button("🧠 Flashcards")
    go_quiz    = c3.button("🎯 Quizzes")
    go_mock    = c4.button("📝 Mock Exams")
    open_chat  = c5.button("💬 Ask Zentra")

    if open_chat: st.session_state.chat_open = True

    out_area = st.container()

    # Handlers
    def do_summary(txt):
        with st.spinner("Generating summary…"):
            prompt = f"""Summarize into sharp exam-style bullet points.
Focus on defs, laws, steps, formulas, must-know facts. No fluff.

NOTES:
{txt}"""
            out = ask_llm(prompt)
        out_area.subheader("✅ Summary"); out_area.markdown(out or "_(empty)_")

    def do_cards(txt):
        with st.spinner("Generating flashcards…"):
            prompt = f"""Create comprehensive flashcards in the format:

**Q:** ...
**A:** ...

One concept per card. Be concise and complete.

NOTES:
{txt}"""
            out = ask_llm(prompt)
        out_area.subheader("🧠 Flashcards"); out_area.markdown(out or "_(empty)_")

    def do_quiz(txt):
        with st.spinner("Building quiz…"):
            n = adaptive_quiz_count(txt)
            prompt = f"""Create {n} MCQs (A–D) with the correct answer and a brief explanation after each.
Vary difficulty and cover all key areas.

NOTES:
{txt}"""
            out = ask_llm(prompt)
        st.session_state.history_quiz.append(st.session_state.last_title)
        out_area.subheader("🎯 Quiz"); out_area.markdown(out or "_(empty)_")

    def do_mock(txt, diff):
        with st.form("mock_form", clear_on_submit=False):
            st.write(f"### Mock Exam ({diff})")
            st.caption("Answer below, then submit for grading.")

            # Generate the mock
            prompt = f"""Create a **{diff}** mock exam with:
1) 5 MCQs (A–D)
2) 2 short-answer
3) 1 long-answer
4) 2 fill-in

Return in structured markdown (clearly numbered)."""
            raw = ask_llm(prompt + f"\n\nNOTES:\n{txt}")
            st.markdown(raw)

            # Response fields
            mcq_ans = [st.radio(f"MCQ {i+1}", ["A","B","C","D"]) for i in range(5)]
            short_ans = [st.text_area(f"Short Answer {i+1}") for i in range(2)]
            long_ans = st.text_area("Long Answer (Essay)")
            fill_ans = [st.text_input(f"Fill in {i+1}") for i in range(2)]

            submitted = st.form_submit_button("Submit Mock")
            if submitted:
                grading_prompt = f"""You are Zentra. Grade fairly.

STUDENT ANSWERS:
MCQs: {mcq_ans}
Short: {short_ans}
Long: {long_ans}
Fill: {fill_ans}

NOTES:
{txt}

Provide:
- Score (0–100)
- Breakdown by section
- Strengths
- Weaknesses
- Advice to improve (actionable)"""
                result = ask_llm(grading_prompt)
                st.success("✅ Mock Graded")
                st.markdown(result)
                st.session_state.history_mock.append(f"{st.session_state.last_title} — {result.splitlines()[0]}")

    # Orchestration
    if go_summary or go_cards or go_quiz or go_mock:
        text, _ = ensure_notes(pasted, uploaded)

    if go_summary: do_summary(text)
    if go_cards:   do_cards(text)
    if go_quiz:    do_quiz(text)
    if go_mock:
        diff = st.radio("Difficulty", ["Easy","Standard","Hard"], horizontal=True, key="mkdiff")
        if st.button("Start Mock"): do_mock(text, diff)

# ---------- ASK ZENTRA (right column chat) ----------
with col_chat:
    if st.session_state.chat_open:
        st.markdown("### 💬 Ask Zentra")
        c1,c2 = st.columns(2)
        if c1.button("Close"): st.session_state.chat_open = False; st.rerun()
        if c2.button("Clear"): st.session_state.messages = []; st.rerun()

        if not st.session_state.messages:
            st.caption("Try: *Explain this line*, *Make a 7-day plan*, *Test me on chapter X*")

        for m in st.session_state.messages:
            with st.chat_message(m["role"]):
                st.markdown(m["content"])

        q = st.chat_input("Type your question…")
        if q:
            st.session_state.messages.append({"role":"user","content":q})
            with st.chat_message("user"): st.markdown(q)
            try:
                ans = ask_llm(
                    f"You are Zentra. Use notes if helpful.\n\n"
                    f"NOTES (may be empty):\n{st.session_state.notes_text}\n\n"
                    f"USER: {q}"
                )
            except Exception as e:
                ans = f"Error: {e}"
            st.session_state.messages.append({"role":"assistant","content":ans})
            with st.chat_message("assistant"): st.markdown(ans)
            st.rerun()
