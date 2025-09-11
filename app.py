import streamlit as st   # ✅ must be first
import os, io, base64, tempfile, datetime, requests
from typing import List, Tuple
from openai import OpenAI

# =========================
# CONFIG & GLOBAL STYLES
# =========================
st.set_page_config(
    page_title="Zentra — AI Study Buddy",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
a[class*="viewerBadge"], div[class*="viewerBadge"], #ViewerBadgeContainer{display:none!important;}
footer{visibility:hidden;height:0}
.block-container{padding-top:1rem;padding-bottom:3rem;max-width:1200px;}
.hero{background:linear-gradient(90deg,#6a11cb 0%,#2575fc 100%);
padding:22px;border-radius:16px;color:#fff;margin-bottom:10px;border-radius:16px;}
.hero h1{margin:0;font-size:34px}
.hero p{margin:6px 0 0;opacity:.92}
.paywall { text-align:center; padding:42px 22px; background:linear-gradient(135deg,#1e1e2f,#23243a);
           border-radius:16px; color:#fff; box-shadow:0 4px 25px rgba(0,0,0,.35); max-width:720px; margin:40px auto;}
.paywall h2{margin:0 0 6px 0; font-size:28px}
.paywall p{opacity:.92}
.pay-btn{display:inline-block; padding:14px 22px; background:#8b5cf6; border-radius:10px; color:#fff; font-weight:700; text-decoration:none;}
.pay-btn:hover{filter:brightness(1.05)}
.input-card{max-width:720px; margin:0 auto 16px; background:#0f1117; color:#eee; padding:14px 16px; border-radius:12px; border:1px solid #232a35;}
.small{font-size:.9rem; opacity:.85}
</style>
<script src="https://assets.lemonsqueezy.com/lemon.js" defer></script>
""", unsafe_allow_html=True)

# =========================
# STATE
# =========================
if "chat_open" not in st.session_state: st.session_state.chat_open = False
if "messages"  not in st.session_state: st.session_state.messages = []
if "history_quiz" not in st.session_state: st.session_state.history_quiz = []
if "history_mock" not in st.session_state: st.session_state.history_mock = []
if "notes_text"   not in st.session_state: st.session_state.notes_text = ""
if "last_title"   not in st.session_state: st.session_state.last_title = "Untitled notes"
if "pending_mock" not in st.session_state: st.session_state.pending_mock = False
if "user_email"   not in st.session_state: st.session_state.user_email = ""

# =========================
# KEYS / ENDPOINTS
# =========================
OPENAI_KEY = st.secrets.get("OPENAI_API_KEY")
SUPABASE_URL = st.secrets.get("SUPABASE_URL")
SUPABASE_ANON = st.secrets.get("SUPABASE_ANON_KEY")
LEMON_CHECKOUT_URL = st.secrets.get("LEMON_CHECKOUT_URL")  # Lemon Squeezy product URL

def _client() -> OpenAI:
    if not OPENAI_KEY:
        st.error("Missing OPENAI_API_KEY in Streamlit Secrets."); st.stop()
    os.environ["OPENAI_API_KEY"] = OPENAI_KEY
    return OpenAI()

MODEL = "gpt-4o-mini"

# =========================
# SUBSCRIPTION CHECK (Supabase REST)
# =========================
def is_subscribed(email: str) -> bool:
    """
    True if latest row for this email has status in ('active','on_trial') and ends_at in the future.
    Table columns expected: id, email, status, ends_at, created_at
    """
    if not (SUPABASE_URL and SUPABASE_ANON):
        # if not configured, app runs unlocked (for development)
        return True

    try:
        url = f"{SUPABASE_URL}/rest/v1/subscriptions"
        headers = {
            "apikey": SUPABASE_ANON,
            "Authorization": f"Bearer {SUPABASE_ANON}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Prefer": "return=representation"
        }
        # select latest by created_at
        params = {
            "select": "*",
            "email": f"eq.{email}",
            "order": "created_at.desc",
            "limit": 1
        }
        r = requests.get(url, headers=headers, params=params, timeout=10)
        if r.status_code != 200:
            return False
        rows = r.json()
        if not rows:
            return False
        row = rows[0]
        status = (row.get("status") or "").lower()
        ends_at = row.get("ends_at")
        if not ends_at:
            return False
        # compare ends_at with now
        now = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
        try:
            ends_dt = datetime.datetime.fromisoformat(ends_at.replace("Z","+00:00"))
        except:
            return False
        active_like = status in ("active", "on_trial", "trialing")
        return active_like and (ends_dt > now)
    except Exception:
        return False

# =========================
# OPENAI HELPERS
# =========================
def ask_llm(prompt: str, system="You are Zentra, a precise and supportive study buddy. Be concise and clear."):
    r = _client().chat.completions.create(
        model=MODEL,
        messages=[{"role":"system","content":system},{"role":"user","content":prompt}],
        temperature=0.4,
    )
    return r.choices[0].message.content.strip()

# =========================
# FILE PARSE
# =========================
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

# =========================
# HERO
# =========================
st.markdown('<div class="hero"><h1>⚡ Zentra — AI Study Buddy</h1><p>Smarter notes → Better recall → Higher scores.</p></div>', unsafe_allow_html=True)

# =========================
# ACCESS GATE (Email + Subscription)
# =========================
with st.container():
    if not st.session_state.user_email:
        st.markdown('<div class="input-card">', unsafe_allow_html=True)
        email = st.text_input("Enter your email to continue", placeholder="you@example.com")
        colA, colB = st.columns([1,1])
        with colA:
            if st.button("Continue"):
                if email and "@" in email:
                    st.session_state.user_email = email.strip().lower()
                    st.rerun()
        with colB:
            st.caption("Use the same email you’ll pay with, so access unlocks automatically.")
        st.markdown('</div>', unsafe_allow_html=True)
        st.stop()

    # If we have an email, check subscription
    email_ok = is_subscribed(st.session_state.user_email)

    if not email_ok:
        # Paywall inside app (overlay checkout). We pass email via query param so Lemon pre-fills.
        lemon_href = LEMON_CHECKOUT_URL or ""
        if st.session_state.user_email and "?" in lemon_href:
            checkout_url = f"{lemon_href}&checkout[email]={st.session_state.user_email}"
        elif st.session_state.user_email:
            checkout_url = f"{lemon_href}?checkout[email]={st.session_state.user_email}"
        else:
            checkout_url = lemon_href

        st.markdown(f"""
        <div class="paywall">
            <h2>🔒 Unlock Zentra</h2>
            <p class="small">Your account <b>{st.session_state.user_email}</b> doesn’t have an active plan yet.</p>
            <p>Get instant access to summaries, flashcards, quizzes, graded mocks, and Ask Zentra.</p>
            <a class="pay-btn" href="{checkout_url}" data-ls-mode="overlay" target="_blank">Subscribe / Start Trial</a>
            <p class="small" style="margin-top:10px;">Already paid? Click “Refresh access” below.</p>
        </div>
        """, unsafe_allow_html=True)

        colr1, colr2 = st.columns([1,1])
        with colr1:
            if st.button("Refresh access"):
                st.rerun()
        with colr2:
            if st.button("Change email"):
                st.session_state.user_email = ""
                st.rerun()
        st.stop()

# =========================
# SIDEBAR (visible after unlock)
# =========================
with st.sidebar:
    st.markdown("## 📊 Toolbox")
    st.write("**How Zentra Works**: Turns notes into smart tools for learning. Smarter notes → better recall → higher scores.")

    st.markdown("### 📌 What Zentra Offers")
    st.markdown("- **Summaries** → exam-ready bullets\n- **Flashcards** → active recall Q/A\n- **Quizzes** → MCQs + explanations (AI chooses count)\n- **Mock Exams** → graded, multi-section with evaluation\n- **Ask Zentra** → personal AI tutor")

    st.markdown("### 🧪 Mock Evaluation")
    st.write("Includes MCQs, short, long, and fill-in. Difficulty: *Easy / Standard / Hard*. Zentra grades responses with a marking scheme, then gives **personal feedback** on weak areas and how to improve.")

    st.markdown("### 📂 History")
    st.caption("Recent Quizzes:"); st.write(st.session_state.history_quiz or "—")
    st.caption("Recent Mock Exams:"); st.write(st.session_state.history_mock or "—")

    st.markdown("---")
    st.caption("Disclaimer: AI-generated. Always verify before exams.")

st.info("Welcome to Zentra! Upload your notes and let AI transform them into study material.")

# =========================
# MAIN APP (UNLOCKED)
# =========================
col_main, col_chat = st.columns([3, 1.4], gap="large")

# ---------- OPENAI ----------
def _openai_text(prompt: str):
    r = _client().chat.completions.create(
        model=MODEL,
        messages=[{"role":"system","content":"You are Zentra, a precise and supportive study buddy. Be concise and clear."},
                  {"role":"user","content":prompt}],
        temperature=0.4,
    )
    return r.choices[0].message.content.strip()

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

    if open_chat:
        st.session_state.chat_open = True

    out_area = st.container()

    # Handlers
    def do_summary(txt):
        with st.spinner("Generating summary…"):
            prompt = f"Summarize into clear exam-ready bullet points.\n\nNotes:\n{txt}"
            out = _openai_text(prompt)
        out_area.subheader("✅ Summary"); out_area.markdown(out or "_(empty)_")

    def do_cards(txt):
        with st.spinner("Generating flashcards…"):
            prompt = f"Make Q/A flashcards from these notes. One concept per card.\n\nNotes:\n{txt}"
            out = _openai_text(prompt)
        out_area.subheader("🧠 Flashcards"); out_area.markdown(out or "_(empty)_")

    def do_quiz(txt):
        with st.spinner("Building quiz…"):
            n = adaptive_quiz_count(txt)
            prompt = f"Create {n} MCQs (A–D) with answers + explanations.\n\nNotes:\n{txt}"
            out = _openai_text(prompt)
        st.session_state.history_quiz.append(st.session_state.last_title)
        out_area.subheader("🎯 Quiz"); out_area.markdown(out or "_(empty)_")

    def do_mock(txt, diff):
        with st.form("mock_form", clear_on_submit=False):
            st.write(f"### Mock Exam ({diff})")
            st.caption("Answer the questions below, then submit for grading.")

            # Get mock from AI
            prompt = f"""Create a **{diff}** mock exam with: 
1) 5 MCQs (A–D)
2) 2 short-answer
3) 1 long-answer
4) 2 fill-in

Return in structured markdown format that the student can answer after."""
            raw = _openai_text(prompt + f"\n\nNotes:\n{txt}")

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

Notes:\n{txt}
Provide:
- Score (0–100)
- Breakdown by section
- Strengths
- Weaknesses
- Advice to improve"""
                result = _openai_text(grading_prompt)
                st.success("✅ Mock Graded")
                st.markdown(result)

                st.session_state.history_mock.append(
                    f"{st.session_state.last_title} — {result.splitlines()[0]}"
                )

    if go_summary or go_cards or go_quiz or go_mock:
        text, _ = ensure_notes(pasted, uploaded)

    if go_summary: do_summary(text)
    if go_cards:   do_cards(text)
    if go_quiz:    do_quiz(text)
    if go_mock:
        diff = st.radio("Difficulty", ["Easy","Standard","Hard"], horizontal=True)
        if st.button("Start Mock"): do_mock(text, diff)

# ---------- ASK ZENTRA ----------
with col_chat:
    if st.session_state.chat_open:
        st.markdown("### 💬 Ask Zentra")
        co1, co2 = st.columns(2)
        if co1.button("Close"): st.session_state.chat_open = False; st.rerun()
        if co2.button("Clear"): st.session_state.messages = []; st.rerun()

        for m in st.session_state.messages:
            with st.chat_message(m["role"]): st.markdown(m["content"])

        q = st.chat_input("Type your question…")
        if q:
            st.session_state.messages.append({"role":"user","content":q})
            with st.chat_message("user"): st.markdown(q)
            try:
                ans = _openai_text(f"You are Zentra. Use notes if helpful.\n\nNOTES:\n{st.session_state.notes_text}\n\nUSER: {q}")
            except Exception as e:
                ans = f"Error: {e}"
            st.session_state.messages.append({"role":"assistant","content":ans})
            with st.chat_message("assistant"): st.markdown(ans)
            st.rerun()
