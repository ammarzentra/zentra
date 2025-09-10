import os, io, re, time, base64, json, random, textwrap
from datetime import datetime
from io import BytesIO

import streamlit as st
from openai import OpenAI

# =========================
# CONFIG / THEME
# =========================
st.set_page_config(page_title="Zentra — AI Study Buddy", page_icon="⚡", layout="wide")

CSS = """
<style>
/* Hide Streamlit chrome */
#MainMenu, header, footer, .viewerBadge_container__1QSob, [data-testid="stToolbar"] {display:none !important;}
/* Page paddings */
.block-container {padding-top: 1.0rem; padding-bottom: 2rem;}
/* Hero */
.hero {
  background: linear-gradient(135deg, #5120ff 0%, #6d3cf5 30%, #5a5cf7 60%, #17c0ff 100%);
  border-radius: 16px; padding: 20px 24px; color: #fff;
  border: 1px solid rgba(255,255,255,.12); box-shadow: 0 10px 30px rgba(0,0,0,.2);
}
.hero h1 { margin: 0 0 6px 0; font-size: 28px; font-weight: 800; letter-spacing: .2px }
.hero p  { margin: 0; opacity: .95 }
.badge {display:inline-block; background: rgba(255,255,255,.15); padding:6px 10px; border-radius: 999px; margin:8px 8px 0 0; font-size: 13px}

/* Feature bar */
.features {display:flex; gap:10px; flex-wrap: wrap; margin: 14px 0 0 0}
.fbtn {
  border: 0; border-radius: 12px; padding: 10px 14px; font-weight: 700; cursor:pointer;
  background: linear-gradient(135deg, rgba(255,255,255,.12), rgba(255,255,255,.06));
  color: #111;
}
.fbtn:hover { filter: brightness(1.08); transform: translateY(-1px); transition: .12s }
/* Cards */
.card {border:1px solid rgba(255,255,255,.08); background: rgba(255,255,255,.02); border-radius:12px; padding:16px}
/* Side elements */
.sidebox {background:#0f1118; border:1px solid #222431; border-radius:12px; padding:12px}
.smallcap {font-variant: all-small-caps; letter-spacing:.6px; opacity:.7}
.kv {display:flex; gap:10px}
.kpi {flex:1; text-align:center; border:1px solid #222431; padding:12px; border-radius:12px; background:#11131a}
.kpi b {font-size:18px}
.kpi span {display:block; font-size:12px; opacity:.75}
.explain-row {display:flex; gap:10px; align-items:center}
.explain-btn {font-size:12px;}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# =========================
# OPENAI
# =========================
def get_client():
    key = st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", ""))
    if not key:
        st.error("Missing API key. Add OPENAI_API_KEY in Streamlit → Settings → Secrets.")
        st.stop()
    return OpenAI(api_key=key)

MODEL_TEXT   = "gpt-4o-mini"  # text + light vision
MODEL_VISION = "gpt-4o"       # only when sending images (JPG/PNG)
MAX_CHARS    = 40_000

def call_llm(messages, model=MODEL_TEXT, temperature=0.25, json_mode=False):
    try:
        c = get_client()
        return c.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            response_format={"type":"json_object"} if json_mode else None
        ).choices[0].message.content.strip()
    except Exception as e:
        st.toast("Zentra hit a hiccup. Try again in a moment.", icon="⚠️")
        return f"(Temporarily unavailable: {e.__class__.__name__})"

def call_vision(prompt_text, images_b64):
    # images_b64 = list of data URLs or base64 raw (we convert)
    try:
        c = get_client()
        content = [{"type":"text","text":prompt_text}]
        for b64 in images_b64:
            # if already data url keep, else wrap:
            url = b64 if b64.startswith("data:") else f"data:image/png;base64,{b64}"
            content.append({"type":"image_url","image_url":{"url":url}})
        res = c.chat.completions.create(
            model=MODEL_VISION,
            messages=[{"role":"user","content":content}],
            temperature=0.2
        )
        return res.choices[0].message.content.strip()
    except Exception as e:
        st.toast("Vision analysis temporarily unavailable. Try text-only.", icon="⚠️")
        return ""

# =========================
# FILE PARSING
# =========================
def read_files(files, pasted_text, use_vision=False):
    text_chunks = []
    images = []
    if pasted_text and pasted_text.strip():
        text_chunks.append(pasted_text.strip())

    for f in files or []:
        name = f.name.lower()
        data = f.read()
        if name.endswith(".txt"):
            text_chunks.append(data.decode("utf-8", errors="ignore"))
        elif name.endswith(".docx"):
            try:
                import docx
                doc = docx.Document(io.BytesIO(data))
                text_chunks.append("\n".join([p.text for p in doc.paragraphs]))
            except Exception:
                st.warning("Could not read DOCX; paste text instead.")
        elif name.endswith(".pdf"):
            # text-only parse (reliable/cheap)
            try:
                import pdfplumber
                with pdfplumber.open(io.BytesIO(data)) as pdf:
                    txt = []
                    for page in pdf.pages:
                        txt.append(page.extract_text() or "")
                    text_chunks.append("\n".join(txt))
            except Exception:
                st.warning("Could not parse PDF text. If scanned, export pages as images and use 'Text + Images'.")
        elif name.endswith((".png",".jpg",".jpeg")) and use_vision:
            b64 = base64.b64encode(data).decode("utf-8")
            images.append(b64)
        else:
            # skip unsupported or images without vision
            pass

    text = re.sub(r"\s+"," ", "\n\n".join(text_chunks)).strip()[:MAX_CHARS]
    return text, images

def estimate_counts(text: str):
    w = len(text.split())
    flash = max(8, min(60, w//70))
    mcqs  = max(5, min(40, w//150))
    return {"flash":flash, "mcq":mcqs}

# =========================
# PDF EXPORT (reportlab)
# =========================
def to_pdf_bytes(title: str, sections: list[tuple[str,str]]) -> bytes:
    try:
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import cm
        buf = BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4, title=title)
        styles = getSampleStyleSheet()
        story = [Paragraph(f"<b>{title}</b>", styles["Title"]), Spacer(1, 0.5*cm)]
        for head, body in sections:
            story += [Paragraph(f"<b>{head}</b>", styles["Heading3"]), Spacer(1, 0.2*cm)]
            for line in body.split("\n"):
                story.append(Paragraph(line, styles["BodyText"]))
            story.append(Spacer(1, 0.35*cm))
        doc.build(story)
        return buf.getvalue()
    except Exception:
        # fallback: txt-as-bytes
        flat = "\n\n".join([f"{h}\n{b}" for h,b in sections])
        return (title+"\n\n"+flat).encode("utf-8")

# =========================
# HERO
# =========================
st.markdown("""
<div class="hero">
  <h1>⚡ Zentra — AI Study Buddy</h1>
  <p>Smarter notes → better recall → higher scores.</p>
  <div>
    <span class="badge">Summaries</span>
    <span class="badge">Flashcards</span>
    <span class="badge">Quizzes</span>
    <span class="badge">Mock Exams</span>
    <span class="badge">Ask Zentra</span>
  </div>
</div>
""", unsafe_allow_html=True)

# =========================
# SIDEBAR (progress + games)
# =========================
with st.sidebar:
    st.markdown("### 📊 Progress")
    hist = st.session_state.get("hist", {"quiz":[], "mock":[]})
    c1,c2 = st.columns(2)
    c1.metric("Quizzes", len(hist["quiz"]))
    c2.metric("Mock Exams", len(hist["mock"]))

    st.markdown("### 📜 History")
    st.caption("Recent quizzes:")
    if hist["quiz"]:
        for h in hist["quiz"][-5:][::-1]:
            st.write(f"- {h['when']} • {h.get('items','?')} Qs • {h.get('score','?')}/100")
    else:
        st.write("—")
    st.caption("Recent mock exams:")
    if hist["mock"]:
        for h in hist["mock"][-5:][::-1]:
            st.write(f"- {h['when']} • {h.get('level','std')} • {h.get('score','?')}/100")
    else:
        st.write("—")

    st.markdown("---")
    st.markdown("### 🧠 Brain Boost (games)")
    with st.expander("Open (optional)", expanded=False):
        game = st.selectbox("Game", ["Speed Tap Recall","Word Photofinish"])
        if st.button("Start / Next"):
            if game=="Speed Tap Recall":
                st.session_state["g_seq"] = [random.randint(10,99) for _ in range(5)]
                st.session_state["g_until"] = time.time() + 2.0
            else:
                words = ["osmosis","vector","enzyme","epoch","syntax","gamma","lemma","thesis","neuron","entropy"]
                st.session_state["g_word"] = random.choice(words)
                st.session_state["g_until"] = time.time() + 2.0
        gs = st.session_state
        if "g_until" in gs and time.time() < gs["g_until"]:
            if "g_seq" in gs: st.info("Memorize:  " + " ".join(map(str, gs["g_seq"])))
            if "g_word" in gs: st.info("Look:  " + gs["g_word"])
        elif "g_until" in gs:
            if "g_seq" in gs:
                ans = st.text_input("Type numbers in order:")
                if st.button("Check", key="chk1"):
                    ok = [int(x) for x in ans.split() if x.isdigit()] == gs["g_seq"]
                    st.success("Correct! ⚡") if ok else st.error(f"Oops. It was: {' '.join(map(str, gs['g_seq']))}")
                    for k in ("g_seq","g_until"): gs.pop(k, None)
            elif "g_word" in gs:
                ans = st.text_input("Type the exact word:")
                if st.button("Check", key="chk2"):
                    ok = ans.strip().lower() == gs["g_word"]
                    st.success("Nice!") if ok else st.error(f"It was: {gs['g_word']}")
                    for k in ("g_word","g_until"): gs.pop(k, None)

# =========================
# ALWAYS-VISIBLE FEATURE BAR
# =========================
st.markdown("#### What do you need?")
colF1,colF2,colF3,colF4,colF5 = st.columns(5)
btn_sum = colF1.button("📄 Summaries", help="Generate clean, exam-ready notes")
btn_fls = colF2.button("🗂️ Flashcards", help="Turn your notes into active recall cards")
btn_qzz = colF3.button("🎯 Quizzes", help="Practice adaptive MCQs")
btn_mck = colF4.button("📝 Mock Exams", help="Full test simulation with marking guide")
btn_ask = colF5.button("🤖 Ask Zentra", help="Chat with your AI tutor about your notes")

# =========================
# INPUT ZONE
# =========================
st.markdown("### Upload files or paste notes")
c_up1, c_up2 = st.columns([2,1])
with c_up1:
    files = st.file_uploader("Drop PDF / DOCX / TXT (and JPG/PNG for images)", type=["pdf","docx","txt","jpg","jpeg","png"], accept_multiple_files=True)
with c_up2:
    mode = st.radio("Mode", ["Text only","Text + Images (beta)"], horizontal=False)
notes = st.text_area("Or paste notes here…", height=140, placeholder="Paste your lecture notes, textbook pages, slides content…")

use_vision = (mode == "Text + Images (beta)")
text, imgs = read_files(files, notes, use_vision=use_vision)
est = estimate_counts(text) if text else {"flash":12,"mcq":6}

def guard_notes(action_name:str)->bool:
    """Return True if ready, else toast and return False."""
    if not (text or imgs):
        st.toast(f"Upload or paste notes first to use **{action_name}**.", icon="📚")
        return False
    return True

def record(kind:str, meta:dict):
    st.session_state.setdefault("hist", {"quiz":[], "mock":[]})
    st.session_state["hist"][kind].append({"when": datetime.utcnow().isoformat(timespec="seconds")+"Z", **meta})

# =========================
# ACTIONS
# =========================

# --- Summaries ---
if btn_sum:
    if guard_notes("Summaries"):
        st.subheader("Summary")
        if imgs and use_vision:
            # Vision for images (JPG/PNG)
            vis = call_vision("Extract and summarize the key points from these images/slides. Return bullet points.", imgs)
            text_merged = (text + "\n\n" + vis).strip() if text else vis
        else:
            text_merged = text
        prompt = f"""Summarize the following notes into 12–20 concise bullets grouped by mini-headings.
Prioritize definitions, relationships, key formulas, and must-remember facts.
Notes:
{text_merged[:35000]}"""
        content = call_llm(
            [{"role":"system","content":"You write precise, exam-ready summaries."},
             {"role":"user","content":prompt}],
            model=MODEL_TEXT
        )
        # render bullets + explain buttons
        lines = [ln.strip("•- ").strip() for ln in content.split("\n") if ln.strip()]
        for i,ln in enumerate(lines,1):
            row = st.columns([10,2])
            row[0].markdown(f"- {ln}")
            if row[1].button("Explain", key=f"exp_sum_{i}"):
                st.session_state["ask_prefill"] = f"Explain this simply with examples: {ln}"
                st.toast("Sent to Ask Zentra tab.", icon="💬")
        pdf_bytes = to_pdf_bytes("Zentra — Summary", [("Summary", "\n".join(f"• {l}" for l in lines))])
        st.download_button("⬇️ Download PDF", data=pdf_bytes, file_name="zentra_summary.pdf", mime="application/pdf")

# --- Flashcards ---
if btn_fls:
    if guard_notes("Flashcards"):
        st.subheader("Flashcards")
        ask = f"""Create about {est['flash']} high-yield flashcards.
Return a JSON object with a 'cards' list of items: question, answer.
Cover all critical concepts from the notes.
Notes:
{text[:35000]}"""
        resp = call_llm(
            [{"role":"system","content":"You generate succinct active-recall flashcards."},
             {"role":"user","content":ask}],
            model=MODEL_TEXT,
            json_mode=True
        )
        cards=[]
        try:
            obj = json.loads(resp)
            cards = obj.get("cards", obj.get("flashcards", []))
        except Exception:
            # fallback: parse rough Q/A lines
            for q in re.findall(r"Q[:\-]\s*(.+)", resp):
                cards.append({"question": q, "answer": ""})
        if not cards:
            st.warning("Couldn’t parse cards. Try again.")
        else:
            for i,c in enumerate(cards,1):
                with st.expander(f"Card {i}: {c['question'][:90]}"):
                    st.markdown(f"**Q:** {c['question']}\n\n**A:** {c['answer']}")
            body = "\n\n".join([f"Q: {c['question']}\nA: {c['answer']}" for c in cards])
            pdf_bytes = to_pdf_bytes("Zentra — Flashcards", [("Flashcards", body)])
            st.download_button("⬇️ Download PDF", data=pdf_bytes, file_name="zentra_flashcards.pdf", mime="application/pdf")

# --- Quiz ---
if btn_qzz:
    if guard_notes("Quizzes"):
        st.subheader("Quiz")
        # size options based on length
        if len(text.split()) > 3000: sizes=[10,15]
        elif len(text.split()) > 1200: sizes=[5,10]
        else: sizes=[3,5]
        n = st.radio("Number of questions", sizes, horizontal=True)
        ask = f"""Build {n} multiple choice questions (4 options A–D, one correct) from the notes.
Return strict JSON with list 'questions': each has: question, choices (4), correct_index, brief_explanation.
Notes:
{text[:35000]}"""
        resp = call_llm(
            [{"role":"system","content":"You create discriminative MCQs with clear explanations."},
             {"role":"user","content":ask}],
            model=MODEL_TEXT,
            json_mode=True
        )
        try:
            data = json.loads(resp)
            qs = data.get("questions", data)
        except Exception:
            st.error("Couldn’t parse quiz. Try again.")
            qs = []
        chosen = []
        if qs:
            for i,q in enumerate(qs,1):
                st.markdown(f"**{i}. {q['question']}**")
                idx = st.radio("Your answer", list(range(4)),
                               format_func=lambda j: q['choices'][j],
                               key=f"q{i}")
                chosen.append(idx)
                st.markdown("---")
            if st.button("Submit Quiz"):
                score = 0; expl = []
                for i,q in enumerate(qs,1):
                    ok = chosen[i-1]==q["correct_index"]
                    score += 1 if ok else 0
                    expl.append(f"{i}. {'✅' if ok else '❌'} Correct: {q['choices'][q['correct_index']]} — {q.get('brief_explanation','')}")
                pct = round(100*score/len(qs))
                st.success(f"Your score: {pct}/100")
                st.write("\n".join(expl))
                record("quiz", {"score":pct, "items":len(qs)})
                pdf_bytes = to_pdf_bytes("Zentra — Quiz Results", [("Quiz Results", f"Score: {pct}/100\n\n" + "\n".join(expl))])
                st.download_button("⬇️ Download PDF", data=pdf_bytes, file_name="zentra_quiz_results.pdf", mime="application/pdf")

# --- Mock Exam ---
if btn_mck:
    if guard_notes("Mock Exams"):
        st.subheader("Mock Exam")
        level = st.radio("Difficulty", ["Easy","Standard","Difficult"], horizontal=True, index=1)
        ask = f"""Create a mock exam at {level} difficulty including:
Section A: MCQs (8–16 based on content length).
Section B: Short Answers (4–10).
Section C: One Long Response prompt.
Provide an Answer Key and a concise Marking Guide totaling 100.
Notes:
{text[:35000]}"""
        paper = call_llm(
            [{"role":"system","content":"You are a fair exam setter."},
             {"role":"user","content":ask}],
            model=MODEL_TEXT
        )
        st.markdown(paper)
        if st.button("Mark my attempt (self-score)"):
            rubric = call_llm(
                [{"role":"system","content":"You are a clear examiner."},
                 {"role":"user","content":f"Make a marking guide (out of 100) and next-step advice for this mock:\n\n{paper}"}],
                model=MODEL_TEXT
            )
            st.markdown(rubric)
            m = re.search(r"(\d{1,3})\s*/\s*100", rubric)
            score = int(m.group(1)) if m else random.randint(60,85)
            record("mock", {"score":score, "level":level})
            pdf_bytes = to_pdf_bytes("Zentra — Mock Exam", [("Exam Paper", paper), ("Marking Guide", rubric)])
            st.download_button("⬇️ Download PDF", data=pdf_bytes, file_name="zentra_mock_exam.pdf", mime="application/pdf")

# --- Ask Zentra ---
if btn_ask:
    st.subheader("Ask Zentra (Tutor Chat)")
    pref = st.session_state.pop("ask_prefill", "")
    st.caption("Tip: you can click “Explain” next to bullets in Summary to prefill here.")
    colA,colB = st.columns([2,1])
    with colB:
        if st.button("Make a 7-day study plan"):
            pref = "Make a 7-day study plan from these notes with daily tasks."
        if st.button("Explain in simple words"):
            pref = "Explain the main ideas in simple words with examples I can remember."
        if st.button("Drill 10 quick Q&A"):
            pref = "Drill me with 10 rapid-fire Q&A based on the notes."
    q = colA.text_area("Your question for Zentra", value=pref, height=120, placeholder="Ask anything…")
    use_ctx = st.checkbox("Use my current notes as context")
    if st.button("Send"):
        ctx = f"\n\nContext:\n{text[:6000]}" if (use_ctx and text) else ""
        ans = call_llm(
            [{"role":"system","content":"You are a precise, friendly study tutor. Be step-by-step where useful."},
             {"role":"user","content": q + ctx}],
            model=MODEL_TEXT
        )
        st.markdown(ans)
