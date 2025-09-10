# app.py — Zentra (final build)
# Features:
# - Clean hero + dark UI
# - Upload PDF/DOCX/TXT or paste notes
# - PDF flow: student chooses Text-only vs Vision (images/diagrams) analysis
# - Summaries, Flashcards (auto-sized), Quiz (few size options based on note length), Mock Exam (scaled, graded /100)
# - Ask Zentra (sample prompts, clean chat)
# - Downloads to PDF for all outputs
# - Sidebar: Progress + "Memory Boost Games" (Memory Grid, Speed Tap Recall)
# - Hides Streamlit branding (CSS hack)

import os, re, io, time, base64, math
from typing import List, Dict
import streamlit as st
from openai import OpenAI

# ------------ UI / THEME ------------
st.set_page_config(page_title="Zentra — AI Study Buddy", page_icon="⚡", layout="wide")
HIDE = """
<style>
#MainMenu, footer, header {visibility: hidden;}
.viewerBadge_container__1QSob, .stAppDeployButton {display: none !important;}
.block-container {padding-top: 1rem; padding-bottom: 2rem;}
/* Hero */
.hero{background:linear-gradient(135deg,#251d49 0%,#4b2a84 100%);
border-radius:18px;padding:20px 22px;color:#fff;border:1px solid rgba(255,255,255,.08)}
.hero h1{margin:0 0 6px 0;font-weight:800}
.hero p{opacity:.95;margin:0}
/* Pills */
.pill{display:inline-block;padding:6px 10px;margin:8px 8px 0 0;border-radius:999px;font-size:.85rem;
background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.12)}
/* Buttons */
.stButton>button{width:100%;border-radius:12px;padding:12px 16px;font-weight:700;
background:linear-gradient(90deg,#7a2bf5,#ff2bb3);border:0}
.stDownloadButton>button{width:100%;border-radius:10px;padding:9px 14px;font-weight:700}
/* Cards */
.card{border:1px solid rgba(200,200,200,.12);border-radius:12px;padding:16px;background:rgba(255,255,255,.02)}
.small{font-size:.9rem;opacity:.85}
/* Chat bubbles */
.bubble{border-radius:12px;padding:10px 12px;margin:6px 0}
.user{background:#1b1f2a;border:1px solid #2a2f3a}
.assistant{background:#141827;border:1px solid #24293a}
.kpi{background:#0d0f14;border:1px solid #222531;border-radius:12px;padding:16px;text-align:center}
.kpi h3{margin:0;font-size:1.6rem}
.kpi p{margin:6px 0 0 0;opacity:.8}
</style>
"""
st.markdown(HIDE, unsafe_allow_html=True)

# ------------ OpenAI client ------------
API_KEY = st.secrets.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
if not API_KEY:
    st.error("Missing OpenAI API key. Add it in Streamlit → Settings → Secrets (OPENAI_API_KEY).")
    st.stop()
client = OpenAI(api_key=API_KEY)
MODEL = "gpt-4o-mini"  # text + vision capable

def call_llm(messages, temperature=0.2, max_tokens=2000):
    r = client.chat.completions.create(model=MODEL, messages=messages, temperature=temperature, max_tokens=max_tokens)
    return r.choices[0].message.content.strip()

# ------------ Parsers ------------
from pypdf import PdfReader
from docx import Document

def read_pdf_text(data: bytes) -> str:
    out=[]
    try:
        reader=PdfReader(io.BytesIO(data))
        for p in reader.pages:
            out.append(p.extract_text() or "")
    except Exception as e:
        out.append(f"[PDF read error: {e}]")
    return "\n".join(out)

# Vision rendering (PDF → images) using pdf2image (requires poppler; on Streamlit Cloud it works if library present)
# We'll try; if it fails, we gracefully fallback.
def pdf_to_images(data: bytes, dpi=180, max_pages=8):
    try:
        from pdf2image import convert_from_bytes
        imgs = convert_from_bytes(data, dpi=dpi, first_page=1, last_page=None)
        if len(imgs)>max_pages: imgs = imgs[:max_pages]
        return imgs
    except Exception:
        return []

def read_docx_bytes(data: bytes) -> str:
    try:
        doc=Document(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs)
    except Exception as e:
        return f"[DOCX read error: {e}]"

def normalize_notes(s: str) -> str:
    s=s.replace("\r","\n")
    s=re.sub(r"\n{3,}","\n\n",s)
    return s.strip()

def count_words(s: str) -> int:
    return len(s.split())

# ------------ Complexity & sizing ------------
def complexity_profile(words:int)->Dict[str,int]:
    if words<300:   return {"sum_words":180,"flash":12,"mcq":5,"mcq_opts":[3,5],"mcq_long_opts":[10],"short":2,"essay":1,"fib":4}
    if words<1200:  return {"sum_words":280,"flash":20,"mcq":8,"mcq_opts":[5,10],"mcq_long_opts":[10],"short":4,"essay":1,"fib":6}
    if words<3000:  return {"sum_words":400,"flash":28,"mcq":12,"mcq_opts":[5,10,15],"mcq_long_opts":[10,15],"short":6,"essay":2,"fib":10}
    return {"sum_words":650,"flash":40,"mcq":18,"mcq_opts":[10,15],"mcq_long_opts":[15],"short":8,"essay":3,"fib":14}

# ------------ PDF export (FPDF lightweight) ------------
from fpdf import FPDF
def to_pdf_bytes(title:str, md:str)->bytes:
    txt=re.sub(r"[#*_>`]{1,3}","",md).replace("•","-")
    pdf=FPDF(); pdf.set_auto_page_break(True,15); pdf.add_page()
    pdf.set_font("Arial","B",16); pdf.multi_cell(0,10,title); pdf.ln(3)
    pdf.set_font("Arial","",11)
    for line in txt.split("\n"):
        pdf.multi_cell(0,7,line)
    buf=io.BytesIO(); pdf.output(buf); return buf.getvalue()

# ------------ Vision helpers ------------
def pil_to_base64(pil_img):
    buf=io.BytesIO(); pil_img.save(buf, format="PNG"); b=buf.getvalue()
    return base64.b64encode(b).decode("utf-8")

def vision_extract_pages(pil_images:List, instruction:str)->str:
    """Send up to N page images to the model with instruction; returns stitched text notes."""
    if not pil_images: return ""
    msgs=[{"role":"system","content":"You are an expert at reading diagrams, screenshots and slides. Extract accurate, well-structured text."},
          {"role":"user","content":[{"type":"text","text":instruction}]+[
              {"type":"image_url","image_url":{"url":f"data:image/png;base64,{pil_to_base64(img)}"}} for img in pil_images
          ]}]
    return call_llm(msgs, temperature=0.1, max_tokens=2000)

# ------------ Session ------------
SS=st.session_state
SS.setdefault("quiz_hist",[])
SS.setdefault("exam_hist",[])
SS.setdefault("chat",[])

# ------------ HERO ------------
st.markdown("""
<div class="hero">
  <h1>⚡ Zentra</h1>
  <p>Smarter notes. Better recall. Higher scores.</p>
  <div>
    <span class="pill">Summaries</span>
    <span class="pill">Flashcards</span>
    <span class="pill">Quizzes</span>
    <span class="pill">Mock Exams</span>
    <span class="pill">Ask Zentra</span>
  </div>
</div>
""", unsafe_allow_html=True)

# ------------ INPUT ------------
st.subheader("Upload your notes (PDF / DOCX / TXT) or paste below")
c_up1, c_up2 = st.columns([1.2,1])
with c_up1:
    up = st.file_uploader(" ", type=["pdf","docx","txt"], label_visibility="collapsed")
with c_up2:
    paste = st.text_area(" ", placeholder="Or paste your notes here…", height=150, label_visibility="collapsed")

source_text=""
analysis_mode="text"
pdf_images=[]

if up is not None:
    data = up.read()
    name = up.name.lower()
    if name.endswith(".pdf"):
        # ask for analysis mode
        analysis_mode = st.radio("Choose how to process your PDF:", ["📝 Text-only (faster)","👁️ Vision (covers images/diagrams)"], index=0, horizontal=True)
        if analysis_mode.startswith("📝"):
            source_text = read_pdf_text(data)
            analysis_mode="text"
        else:
            # text + attempt vision images
            text_only = read_pdf_text(data)
            images = pdf_to_images(data, dpi=180, max_pages=8)
            extracted = ""
            if images:
                with st.spinner("Analyzing images/diagrams (Vision)…"):
                    extracted = vision_extract_pages(images, "Extract all text content, labels, bullet points and important relationships from these pages.")
                    pdf_images = images
            source_text = (text_only + "\n\n" + extracted).strip()
            analysis_mode="vision"
    elif name.endswith(".docx"):
        source_text = read_docx_bytes(data)
    else:
        try:
            source_text = data.decode("utf-8", errors="ignore")
        except:
            source_text = ""
else:
    source_text = paste

source_text = normalize_notes(source_text)
words = count_words(source_text)
profile = complexity_profile(words)

if not source_text:
    st.info("Upload a file or paste notes to get started.")

# ------------ MAIN TABS ------------
tabs = st.tabs(["📄 Summaries","🔑 Flashcards","🎯 Quiz","📝 Mock Exam","💬 Ask Zentra"])

# --- Summaries ---
with tabs[0]:
    if st.button("✨ Generate Summary", disabled=not source_text, key="btn_sum"):
        with st.spinner("Summarizing…"):
            sys="You are an expert study coach. Produce compact, accurate study summaries aligned to exams."
            user=f"""Summarize the notes in ~{profile['sum_words']} words.
- Use headings and bullet points.
- Include key terms, definitions, formulas, dates, cause→effect.
- If the notes came from slides/images (vision), integrate that info too.
NOTES:
{source_text}"""
            summary = call_llm([{"role":"system","content":sys},{"role":"user","content":user}], temperature=0.2, max_tokens=2000)
        st.markdown(summary)
        c1,c2=st.columns(2)
        with c1: st.download_button("📥 Download PDF", data=to_pdf_bytes("Summary", summary), file_name="zentra_summary.pdf", mime="application/pdf")
        with c2: st.download_button("📥 Download TXT", data=summary, file_name="zentra_summary.txt")

# --- Flashcards (auto-sized) ---
with tabs[1]:
    st.caption("AI decides how many cards fully cover your content.")
    if st.button("🔑 Generate Flashcards", disabled=not source_text, key="btn_fc"):
        with st.spinner("Generating flashcards…"):
            sys="You create excellent two-sided flashcards that maximize active recall."
            user=f"""Create approximately {profile['flash']} high-quality flashcards that cover ALL core concepts from the notes.
Output in clean Markdown list with **Q:** and **A:** pairs. Avoid duplicates; ensure broad coverage.

NOTES:
{source_text}"""
            cards_md = call_llm([{"role":"system","content":sys},{"role":"user","content":user}], temperature=0.2, max_tokens=3000)
        st.markdown("#### Flashcards")
        st.markdown(cards_md)
        c1,c2=st.columns(2)
        with c1: st.download_button("📥 Download PDF", data=to_pdf_bytes("Flashcards", cards_md), file_name="zentra_flashcards.pdf", mime="application/pdf")
        with c2: st.download_button("📥 Download TXT", data=cards_md, file_name="zentra_flashcards.txt")

# --- Quiz (few size options by length) ---
with tabs[2]:
    st.caption("Quick MCQs to check understanding (different pool than Mock Exam).")
    # options depend on note length
    if words<300:
        options=[3,5]
    elif words<1200:
        options=[5,10]
    elif words<3000:
        options=[5,10,15]
    else:
        options=[10,15]
    n = st.radio("How big should the quiz be?", options, index=0, horizontal=True, disabled=not source_text)
    if st.button("🎯 Start Quiz", disabled=not source_text, key="btn_quiz"):
        with st.spinner("Generating quiz…"):
            sys="You are a strict test maker. Generate exam-quality single-answer MCQs with clear distractors."
            user=f"""Create {n} unique MCQs from the notes below.
- Output in Markdown with numbering.
- Each item: question + 4 options (A–D).
- Put the answer key and 1–2 sentence explanations at the end.
- Ensure this set is DIFFERENT from any mock exam that might be generated.

NOTES:
{source_text}"""
            quiz_md = call_llm([{"role":"system","content":sys},{"role":"user","content":user}], temperature=0.25, max_tokens=2500)
        st.markdown(quiz_md)
        SS.quiz_hist.append({"ts":int(time.time()),"n":n,"title":"Quiz"})
        c1,c2=st.columns(2)
        with c1: st.download_button("📥 Download PDF", data=to_pdf_bytes("Quiz", quiz_md), file_name="zentra_quiz.pdf", mime="application/pdf")
        with c2: st.download_button("📥 Download TXT", data=quiz_md, file_name="zentra_quiz.txt")

# --- Mock Exam (scaled, graded /100) ---
with tabs[3]:
    diff = st.select_slider("Difficulty", options=["Easy","Standard","Hard"], value="Standard", disabled=not source_text)
    if st.button("📝 Generate Mock Exam", disabled=not source_text, key="btn_exam"):
        with st.spinner("Composing your mock exam…"):
            # scale counts from profile + difficulty multiplier
            mult=1.0 + (0.15 if diff=="Hard" else (-0.1 if diff=="Easy" else 0))
            counts={
                "mcq":  max(6, math.ceil(profile["mcq"]*mult)),
                "fib":  max(4, math.ceil(profile["fib"]*mult)),
                "short":max(2, math.ceil(profile["short"]*mult)),
                "essay":max(1, math.ceil(profile["essay"]*mult)),
            }
            sys="You are an expert examiner. Create rigorous but fair mock exams. Grade to 100."
            user=f"""Create a **Mock Exam** from the notes with the following sections (DIFFERENT bank than Quiz):

**Sections**
1) MCQs: {counts['mcq']} questions, 4 options (A–D).
2) Fill-in-the-blank: {counts['fib']} items (one-word/phrase).
3) Short Answers: {counts['short']} questions (2–4 sentences) with **model answers**.
4) Long Answer(s): {counts['essay']} prompts with **model answer** (5–10 bullet points).

**After the exam**, include:
- **Answer Key** for MCQ + FIB.
- **Marking Scheme** that totals **/100** (allocate marks across sections).
- **How to Self-Mark** short/long answers (concise rubric).
- **Personalized Feedback Template** (strengths, weak areas, next steps).

Ensure broad coverage (especially if notes came from slides/diagrams via Vision).
NOTES:
{source_text}"""
            exam_md = call_llm([{"role":"system","content":sys},{"role":"user","content":user}], temperature=0.25, max_tokens=4000)
        st.markdown(exam_md)
        SS.exam_hist.append({"ts":int(time.time()),"title":"Mock Exam","diff":diff,"counts":counts,"max":100})
        c1,c2=st.columns(2)
        with c1: st.download_button("📥 Download PDF", data=to_pdf_bytes("Mock Exam", exam_md), file_name="zentra_mock_exam.pdf", mime="application/pdf")
        with c2: st.download_button("📥 Download TXT", data=exam_md, file_name="zentra_mock_exam.txt")

# --- Ask Zentra ---
with tabs[4]:
    st.caption("Ask anything about your uploaded notes — or general study help.")
    # sample chips
    chips = st.columns(4)
    samples = [
        "Make me a 7-day study plan from these notes.",
        "Explain the 3 most testable concepts with examples.",
        "Create a quick cram sheet for exam morning.",
        "Give me memory hooks (mnemonics) for key terms."
    ]
    for i,s in enumerate(samples):
        if chips[i].button(s, key=f"chip_{i}"): SS.chat.append({"role":"user","content":s})

    q = st.text_input("Ask Zentra…", placeholder="e.g., Compare mitosis vs meiosis in a table")
    c1,c2=st.columns([1,.35])
    send = c1.button("💬 Send", use_container_width=True)
    clr  = c2.button("🧹 Clear", use_container_width=True)
    if clr: SS.chat=[]

    if (q and send): SS.chat.append({"role":"user","content":q})

    if SS.chat and SS.chat[-1]["role"]=="user":
        with st.spinner("Zentra is thinking…"):
            msgs=[{"role":"system","content":"You are Zentra, a precise, friendly study tutor. Use the student's notes if provided."}]
            if source_text:
                msgs.append({"role":"system","content":f"Student notes (context):\n{source_text[:15000]}"})
            msgs+=SS.chat
            ans = call_llm(msgs, temperature=0.2, max_tokens=1200)
        SS.chat.append({"role":"assistant","content":ans})

    for turn in SS.chat:
        if turn["role"]=="user":
            st.markdown(f'<div class="bubble user"><b>You</b>: {turn["content"]}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="bubble assistant"><b>Zentra</b>: {turn["content"]}</div>', unsafe_allow_html=True)

# ------------ SIDEBAR: Progress + Games ------------
with st.sidebar:
    st.subheader("📊 Progress")
    c1,c2 = st.columns(2)
    with c1:
        st.markdown(f'<div class="kpi"><h3>{len(SS.quiz_hist)}</h3><p>Quizzes</p></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="kpi"><h3>{len(SS.exam_hist)}</h3><p>Mock Exams</p></div>', unsafe_allow_html=True)

    st.markdown("**Quiz History**")
    if not SS.quiz_hist:
        st.caption("No quizzes yet.")
    else:
        for qh in SS.quiz_hist[::-1]:
            ts=time.strftime("%Y-%m-%d %H:%M", time.localtime(qh["ts"]))
            st.write(f"- {qh['n']} MCQs · _{ts}_")

    st.markdown("**Mock Exam History**")
    if not SS.exam_hist:
        st.caption("No mock exams yet.")
    else:
        for eh in SS.exam_hist[::-1]:
            ts=time.strftime("%Y-%m-%d %H:%M", time.localtime(eh["ts"]))
            c=eh["counts"]; st.write(f"- {eh['diff']} · MCQ {c['mcq']}, FIB {c['fib']}, SA {c['short']}, Essay {c['essay']} · _{ts}_")

    st.divider()
    st.subheader("🎮 Memory Boost Games")

    game = st.selectbox("Choose a game", ["🧠 Memory Grid","⚡ Speed Tap Recall"])

    # Game 1: Memory Grid (simple)
    if game=="🧠 Memory Grid":
        size = st.slider("Grid size", 3, 6, 4)
        show_sec = st.slider("Show time (sec)", 1, 5, 2)
        if "grid_seq" not in SS: SS.grid_seq=[]
        if st.button("Start Round"):
            import random
            SS.grid_seq=[(random.randrange(size), random.randrange(size)) for _ in range(max(3, size))]
            SS.grid_revealed=True
            SS.grid_clicks=[]
            SS.grid_started=time.time()
        if "grid_revealed" in SS and SS.grid_seq:
            # draw grid
            cols = st.columns(size)
            for r in range(size):
                for c in range(size):
                    lab = " "
                    if SS.get("grid_revealed"):
                        if (r,c) in SS.grid_seq: lab="●"
                    if cols[c].button(lab, key=f"g{r}-{c}"):
                        if not SS.get("grid_revealed"):
                            SS.grid_clicks.append((r,c))
            if SS.get("grid_revealed") and (time.time()-SS.grid_started)>=show_sec:
                SS.grid_revealed=False
                st.info("Now repeat the pattern in order!")
            if not SS.get("grid_revealed") and len(SS.get("grid_clicks",[]))>=len(SS.grid_seq)>0:
                st.write("Your input:", SS.grid_clicks)
                st.write("Target:", SS.grid_seq)
                st.success("Great memory!" if SS.grid_clicks==SS.grid_seq else "Keep training!")

    # Game 2: Speed Tap Recall (word association)
    if game=="⚡ Speed Tap Recall":
        if "tap_score" not in SS: SS.tap_score=0
        if "tap_word" not in SS: SS.tap_word=""
        vocab = ["osmosis","momentum","mitosis","inflation","photosynthesis","equilibrium","derivative","entropy"]
        colg1,colg2=st.columns([1,.6])
        with colg1:
            if st.button("Start/Next"):
                import random
                SS.tap_word=random.choice(vocab)
                SS.tap_score=SS.tap_score
        st.write(f"Word: **{SS.tap_word or '—'}**")
        ans = st.text_input("Type a related concept/definition (3s speed!)", value="")
        if st.button("Check"):
            if SS.tap_word:
                # quick relevance via LLM (low token)
                msg=[{"role":"system","content":"Check if the student's response is relevant to the cue word (yes/no only)."},
                     {"role":"user","content":f"Cue: {SS.tap_word}\nResponse: {ans}\nAnswer 'yes' if clearly related; else 'no'."}]
                ok = call_llm(msg, temperature=0, max_tokens=5).lower()
                if "yes" in ok:
                    SS.tap_score+=1; st.success("Nice! +1")
                else:
                    st.warning("Not quite—try again.")
        st.write(f"Score: **{SS.tap_score}**")

    st.divider()
    with st.expander("Disclaimer"):
        st.caption("Zentra is an AI assistant. Verify outputs with your syllabus/instructor. Vision mode may increase token usage.")
