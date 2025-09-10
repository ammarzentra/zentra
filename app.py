import os, io, random, time, textwrap
from datetime import datetime
from typing import List, Tuple

import streamlit as st

# -------------------------------
# OPENAI CLIENT (v1 SDK)
# -------------------------------
try:
    from openai import OpenAI
except Exception:
    st.stop()

API_KEY = st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", ""))
if not API_KEY:
    st.markdown("⚠️ **Missing API key**. Add it in Streamlit → Settings → Secrets as `OPENAI_API_KEY`.")
    st.stop()

client = OpenAI(api_key=API_KEY)
MODEL = "gpt-4o-mini"

# -------------------------------
# SMALL UTILITIES
# -------------------------------
def soft_tokens(s: str) -> int:
    # quick n’ dirty token proxy
    return max(1, len(s.split()) // 0.75)

def pick_counts_by_length(words: int) -> Tuple[int, int]:
    """Return (flashcards, mcqs) by approximate note size."""
    if words < 500:
        return (8, 6)
    elif words < 1500:
        return (16, 12)
    elif words < 4000:
        return (28, 20)
    else:
        return (40, 30)

def safe_chat(system: str, user: str) -> str:
    try:
        r = client.chat.completions.create(
            model=MODEL,
            messages=[{"role":"system","content":system},{"role":"user","content":user}],
            temperature=0.2,
        )
        return r.choices[0].message.content.strip()
    except Exception as e:
        st.toast("Something went wrong. Try again in a moment.", icon="⚠️")
        return f"(Temporarily unavailable: {e.__class__.__name__})"

def make_pdf_bytes(title: str, lines: List[str]) -> bytes:
    """Try to build a lightweight PDF. Falls back to TXT if fpdf missing."""
    try:
        from fpdf import FPDF
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=12)
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, title, ln=True)
        pdf.set_font("Arial", "", 12)
        for ln in lines:
            for wrapped in textwrap.wrap(ln, 92):
                pdf.cell(0, 7, wrapped, ln=True)
        b = io.BytesIO()
        pdf.output(b)
        return b.getvalue()
    except Exception:
        # plain text fallback
        buf = "\n".join(lines).encode("utf-8")
        return buf

def extract_text(uploaded) -> str:
    """PDF/DOCX/TXT → text. Leave images for 'Vision' path later."""
    name = uploaded.name.lower()
    data = uploaded.read()
    if name.endswith(".txt"):
        return data.decode("utf-8", errors="ignore")
    if name.endswith(".docx"):
        try:
            from docx import Document
        except Exception:
            st.error("`python-docx` not installed. Add to requirements.txt.")
            st.stop()
        bio = io.BytesIO(data)
        doc = Document(bio)
        return "\n".join([p.text for p in doc.paragraphs])
    # PDF
    try:
        from pypdf import PdfReader
    except Exception:
        st.error("`pypdf` not installed. Add to requirements.txt.")
        st.stop()
    reader = PdfReader(io.BytesIO(data))
    txt = []
    for p in reader.pages:
        try:
            txt.append(p.extract_text() or "")
        except Exception:
            txt.append("")
    return "\n".join(txt)

def outline_from_text(notes: str) -> str:
    return safe_chat(
        "You write terse outlines for long study notes.",
        f"Make a 5-10 bullet outline capturing the structure of these notes:\n\n{notes[:12000]}",
    )

# -------------------------------
# PAGE CONFIG + CSS POLISH
# -------------------------------
st.set_page_config(page_title="Zentra — AI Study Buddy", page_icon="⚡", layout="wide")

HIDE_STREAMLIT = """
<style>
/* Hide Streamlit footer/header badges */
header [data-testid="stToolbar"] { visibility: hidden; height: 0; }
footer { visibility: hidden; height: 0; }
/* Hero */
.hero {
  background: linear-gradient(135deg, #5b2cff 0%, #7a2df0 40%, #a82deb 100%);
  border-radius: 14px; padding: 22px 24px; color: #fff; border: 1px solid rgba(255,255,255,0.08);
}
.hero h1 { margin: 0 0 6px 0; font-size: 34px; }
.hero p { margin: 0; opacity: .92 }
.chip {background:rgba(255,255,255,.12); padding:6px 10px;border-radius:100px;margin-right:8px;font-size:13px;display:inline-block}
.result-card {border:1px solid rgba(255,255,255,.08); border-radius:12px; padding:16px; background:rgba(255,255,255,.02)}
.small-btn {font-size:13px; padding:6px 10px; border-radius:10px}
.sidecard {border:1px solid rgba(255,255,255,.08); border-radius:10px; padding:10px 12px; background:rgba(255,255,255,.02)}
.ask-float {position: sticky; top: 10px;}
</style>
"""
st.markdown(HIDE_STREAMLIT, unsafe_allow_html=True)

# -------------------------------
# SIDEBAR (compact)
# -------------------------------
with st.sidebar:
    st.markdown("### 🔹 Progress")
    c1, c2 = st.columns(2)
    with c1: st.markdown(f"""<div class="sidecard"><b>{st.session_state.get('quiz_count',0)}</b><br/>Quizzes</div>""", unsafe_allow_html=True)
    with c2: st.markdown(f"""<div class="sidecard"><b>{st.session_state.get('exam_count',0)}</b><br/>Mock Exams</div>""", unsafe_allow_html=True)

    st.markdown("### 🕹️ Memory Boost")
    with st.expander("Open game (optional)", expanded=False):
        diff = st.radio("Difficulty", ["Easy", "Medium", "Hard"], horizontal=True)
        target_secs = {"Easy": 30, "Medium": 45, "Hard": 60}[diff]
        if st.button("Start Speed Recall"):
            st.session_state["game_start"] = time.time()
            st.session_state["game_target"] = target_secs
            st.session_state["game_score"] = 0
            st.session_state["game_word"] = None
            st.rerun()
        if "game_start" in st.session_state:
            elapsed = int(time.time() - st.session_state["game_start"])
            left = max(0, st.session_state["game_target"] - elapsed)
            st.write(f"Time: **{left}s** | Score: **{st.session_state['game_score']}**")
            word = st.session_state.get("game_word")
            if not word:
                # random short term to recall
                seed = st.session_state.get("last_summary","") or st.session_state.get("last_outline","") or "photosynthesis DNA neuron enzyme mitosis"
                choices = [w for w in seed.replace("\n"," ").split() if w.isalpha() and 4<=len(w)<=11]
                random.shuffle(choices)
                word = (choices[:1] or ["osmosis"])[0]
                st.session_state["game_word"] = word
            st.info(f"Type this quickly: **{word}**")
            guess = st.text_input("Type here:", key="game_guess")
            if st.button("Submit"):
                if guess.strip().lower()==st.session_state["game_word"].lower():
                    st.session_state["game_score"] += 1
                st.session_state["game_word"] = None
                st.session_state["game_guess"] = ""
                st.rerun()
            if left==0:
                st.success(f"Time! Final score: {st.session_state['game_score']}")
                for k in ["game_start","game_target","game_word","game_guess"]:
                    st.session_state.pop(k, None)

# -------------------------------
# HERO
# -------------------------------
st.markdown(
    """
<div class="hero">
  <h1>⚡ Zentra — AI Study Buddy</h1>
  <p>Smarter notes → faster recall → higher scores. Upload or paste your notes; Zentra builds summaries, flashcards, quizzes, and mock exams — plus a tutor you can chat with.</p>
  <div style="margin-top:10px">
    <span class="chip">Summaries</span>
    <span class="chip">Flashcards</span>
    <span class="chip">Quizzes</span>
    <span class="chip">Mock Exams</span>
    <span class="chip">Ask Zentra</span>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

# -------------------------------
# INPUTS
# -------------------------------
st.markdown("### Upload your notes (PDF / DOCX / TXT) **or** paste below")

col_up, col_name = st.columns([3,2])
with col_up:
    uploaded = st.file_uploader("Drag & drop or browse", type=["pdf","docx","txt"], label_visibility="collapsed")
with col_name:
    mode = st.radio("Analysis mode", ["Text only (cheaper)","Include images (vision)"], horizontal=True)

notes = st.text_area("Paste notes here if you aren't uploading a file...", height=180)
if uploaded and not notes.strip():
    with st.spinner("Extracting text…"):
        try:
            notes = extract_text(uploaded)
        except Exception as e:
            st.warning("Could not read the file. Try .pdf/.docx/.txt.")
            notes = ""

if not notes.strip():
    st.info("Upload a file **or** paste notes to get started.")
    st.stop()

# Basic derived metrics
word_count = len(notes.split())
flash_count, mcq_count = pick_counts_by_length(word_count)

# -------------------------------
# TABS: core features + Ask Zentra
# -------------------------------
tab_sum, tab_cards, tab_quiz, tab_exam, tab_ask = st.tabs(["🟣 Summaries", "🟡 Flashcards", "🔴 Quiz", "🟢 Mock Exam", "💬 Ask Zentra"])

# ===== SUMMARY =====
with tab_sum:
    st.markdown("#### Summary")
    st.caption("Zentra writes focused, exam-ready summaries (not fluffy).")
    if st.button("✨ Generate Summary", type="primary"):
        with st.spinner("Summarizing…"):
            # If vision later: call multimodal here for images
            summary = safe_chat(
                "You produce tight, clearly formatted study summaries.",
                f"Summarize the following *comprehensively but concise*, use headings & bullets where helpful:\n\n{notes[:16000]}"
            )
        st.session_state["last_summary"] = summary
        st.session_state["last_outline"] = outline_from_text(notes)
        st.markdown(f'<div class="result-card">{summary}</div>', unsafe_allow_html=True)

        # Download
        pdf_bytes = make_pdf_bytes("Zentra Summary", [summary])
        st.download_button("⬇️ Download summary (PDF/TXT)", data=pdf_bytes, file_name="zentra_summary.pdf", mime="application/pdf")

        # Context helper
        with st.popover("Ask Zentra about this summary"):
            ask_q = st.text_input("Type a question about the summary:")
            if st.button("Ask (summary context)"):
                resp = safe_chat(
                    "Answer as a helpful tutor using the provided context.",
                    f"Context:\n{summary}\n\nQuestion: {ask_q}"
                )
                st.write(resp)

# ===== FLASHCARDS =====
with tab_cards:
    st.markdown("#### Flashcards")
    st.caption("Counts are auto-sized to your note length.")
    if st.button(f"🗝️ Make ~{flash_count} flashcards"):
        with st.spinner("Building flashcards…"):
            fc = safe_chat(
                "Create clean flashcards as Q: ... / A: ... one per line.",
                f"Make about {flash_count} **high-yield** flashcards that cover all key facts from these notes:\n\n{notes[:16000]}\n\nFormat strictly as:\nQ: ...\nA: ...\nQ: ...\nA: ..."
            )
        st.session_state["last_flashcards"] = fc
        st.text(fc)
        pdf_bytes = make_pdf_bytes("Zentra Flashcards", fc.splitlines())
        st.download_button("⬇️ Download flashcards (PDF/TXT)", data=pdf_bytes, file_name="zentra_flashcards.pdf", mime="application/pdf")

        with st.popover("Ask Zentra about these flashcards"):
            ask_q = st.text_input("Question about a card?")
            if st.button("Ask (flashcards context)"):
                resp = safe_chat("Tutor with context", f"Flashcards:\n{fc}\n\nQuestion: {ask_q}")
                st.write(resp)

# ===== QUIZ =====
with tab_quiz:
    st.markdown("#### Quiz")
    size = "Short" if word_count<800 else ("Standard" if word_count<2500 else "Long")
    st.caption(f"Auto-sized for your notes: **{size}** quiz.")

    diff = st.radio("Difficulty", ["Easy","Standard","Challenging"], horizontal=True)
    if st.button(f"🎯 Generate {size} Quiz"):
        qs = {"Short": mcq_count//2, "Standard": mcq_count, "Long": mcq_count + 8}[size]
        with st.spinner("Generating quiz MCQs…"):
            quiz = safe_chat(
                "Create multiple-choice questions. Provide answer key at the end.",
                f"Build **{qs}** high-quality MCQs from the notes. 4 options each (A–D), one correct. Mix conceptual & applied. Then an answer key.\n\nNotes:\n{notes[:16000]}"
            )
        st.session_state["quiz_count"] = st.session_state.get("quiz_count",0)+1
        st.session_state["last_quiz"] = quiz
        st.markdown(f'<div class="result-card" style="white-space:pre-wrap">{quiz}</div>', unsafe_allow_html=True)
        pdf_bytes = make_pdf_bytes("Zentra Quiz", quiz.splitlines())
        st.download_button("⬇️ Download quiz (PDF/TXT)", data=pdf_bytes, file_name="zentra_quiz.pdf", mime="application/pdf")

        with st.popover("Ask Zentra about this quiz"):
            q = st.text_input("Confused about a question?")
            if st.button("Explain (quiz context)"):
                ans = safe_chat("Explain clearly with steps", f"Quiz:\n{quiz}\n\nExplain: {q}")
                st.write(ans)

# ===== MOCK EXAM =====
with tab_exam:
    st.markdown("#### Mock Exam")
    exam_level = st.radio("Mode", ["Easy", "Standard", "Difficult"], horizontal=True)

    if st.button("📝 Build Mock Exam"):
        # scale sections by notes length + difficulty
        base_mcq = {"Easy": 8, "Standard": 14, "Difficult": 20}[exam_level]
        mult = 1 if word_count<1200 else (1.4 if word_count<3500 else 1.8)
        mcqs = int(base_mcq*mult)

        short_n = int(0.4*mcqs)
        long_n  = 2 if exam_level=="Easy" else (3 if exam_level=="Standard" else 4)

        with st.spinner("Composing full mock exam…"):
            exam = safe_chat(
                "You are an assessment designer. Return a professional mock exam.",
                f"""
Create a **mock exam** from the notes with these sections:
- Section A: {mcqs} MCQs (A–D), different from any earlier quiz ideas.
- Section B: {short_n} Short-Answer items (2–4 lines).
- Section C: {long_n} Long-Answer prompts requiring structured explanations.

Provide:
1) Exam paper (clean formatting, section headers, points per item; total 100 points).
2) Answer key & marking guide with point splits.
3) Personalized revision advice at the end.

Notes:
{notes[:16000]}
"""
            )
        st.session_state["exam_count"] = st.session_state.get("exam_count",0)+1
        st.session_state["last_exam"] = exam
        st.markdown(f'<div class="result-card" style="white-space:pre-wrap">{exam}</div>', unsafe_allow_html=True)
        pdf_bytes = make_pdf_bytes("Zentra Mock Exam", exam.splitlines())
        st.download_button("⬇️ Download mock exam (PDF/TXT)", data=pdf_bytes, file_name="zentra_mock_exam.pdf", mime="application/pdf")

        with st.popover("Ask Zentra about this exam"):
            q = st.text_input("Ask about a section or marking:")
            if st.button("Explain (exam context)"):
                ans = safe_chat("Explain as tutor with rubric", f"Exam:\n{exam}\n\nExplain: {q}")
                st.write(ans)

# ===== ASK ZENTRA (dedicated)
with tab_ask:
    st.markdown("#### Ask Zentra")
    st.caption("A focused chat tutor. It can also use your latest summary/quiz/exam as context.")
    col_sug, col_chat = st.columns([1,2])
    with col_sug:
        st.markdown("**Try one:**")
        if st.button("Make a 7-day study plan"):
            st.session_state["ask_prompt"]="Make a 7-day study plan for these notes."
        if st.button("Explain this concept simply"):
            st.session_state["ask_prompt"]="Explain the main concept in simple terms with examples."
        if st.button("Drill me with quick questions"):
            st.session_state["ask_prompt"]="Create 10 rapid-fire questions with answers."
        if st.button("Revise fast in 10 bullets"):
            st.session_state["ask_prompt"]="Summarize key ideas in 10 bullets for quick revision."

    with col_chat:
        default = st.session_state.get("ask_prompt","")
        user_q = st.text_area("Your question for Zentra", value=default, height=100)
        use_ctx = st.checkbox("Use my latest outputs as context (summary/quiz/exam)")
        if st.button("💬 Ask Zentra", type="primary"):
            context_blobs = []
            if use_ctx:
                for k in ["last_summary","last_quiz","last_exam"]:
                    if k in st.session_state:
                        context_blobs.append(st.session_state[k])
            ctx = "\n\n".join(context_blobs) if context_blobs else "(no context)"
            ans = safe_chat(
                "Be a precise, friendly study tutor.",
                f"Context (optional):\n{ctx}\n\nUser question:\n{user_q}"
            )
            st.markdown(f'<div class="result-card">{ans}</div>', unsafe_allow_html=True)
