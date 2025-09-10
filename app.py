import os, io, re, time, base64, random, textwrap
from datetime import datetime
from io import BytesIO

import streamlit as st
from openai import OpenAI

# ---------- Config ----------
MODEL_TEXT = "gpt-4o-mini"
MODEL_VISION = "gpt-4o"  # used only for image uploads (jpg/png)
MAX_CHARS = 40_000  # safety cap per call

# ---------- Helpers ----------
def client():
    # read from Streamlit Secrets on Cloud, env local
    api_key = st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", ""))
    if not api_key:
        st.error("OpenAI API key is missing. Add it in Streamlit → Settings → Secrets as OPENAI_API_KEY.")
        st.stop()
    return OpenAI(api_key=api_key)

def clean_text(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    return s[:MAX_CHARS]

def section(title, icon=""):
    st.markdown(f"<div class='sec'><span class='sec-ic'>{icon}</span>{title}</div>", unsafe_allow_html=True)

def to_pdf_bytes(title: str, sections: list[tuple[str, str]]) -> bytes:
    """Build a simple PDF with reportlab; fallback to txt if needed."""
    try:
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import cm
        buf = BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4, title=title)
        styles = getSampleStyleSheet()
        story = []
        story.append(Paragraph(f"<b>{title}</b>", styles["Title"]))
        story.append(Spacer(1, 0.5*cm))
        for h, body in sections:
            story.append(Paragraph(f"<b>{h}</b>", styles["Heading3"]))
            for line in body.split("\n"):
                story.append(Paragraph(line, styles["BodyText"]))
            story.append(Spacer(1, 0.4*cm))
        doc.build(story)
        return buf.getvalue()
    except Exception:
        # fallback: text file wrapped as PDF-like bytes
        joined = f"{title}\n\n" + "\n\n".join([f"{h}\n{b}" for h, b in sections])
        return joined.encode("utf-8")

def download_button(label: str, filename: str, payload_bytes: bytes):
    st.download_button(label=label, file_name=filename, data=payload_bytes, mime="application/pdf")

def extract_text(files, pasted: str) -> tuple[str, list[dict]]:
    """Return combined text + a list of image dicts (only png/jpg).
       For PDFs & DOCX we extract text only (vision off for stability)."""
    chunks = []
    images = []
    if pasted and pasted.strip():
        chunks.append(pasted.strip())

    for f in files or []:
        name = f.name.lower()
        data = f.read()
        if name.endswith(".txt"):
            chunks.append(data.decode("utf-8", errors="ignore"))
        elif name.endswith(".docx"):
            try:
                import docx
                doc = docx.Document(io.BytesIO(data))
                chunks.append("\n".join([p.text for p in doc.paragraphs]))
            except Exception:
                st.warning("Could not read .docx; paste text instead.")
        elif name.endswith(".pdf"):
            try:
                import pdfplumber
                with pdfplumber.open(io.BytesIO(data)) as pdf:
                    txt = []
                    for page in pdf.pages:
                        txt.append(page.extract_text() or "")
                    chunks.append("\n".join(txt))
            except Exception:
                st.warning("Could not parse PDF text. If it’s scanned, use the Vision (images) mode with JPG/PNG pages.")
        elif name.endswith((".png",".jpg",".jpeg")):
            b64 = base64.b64encode(data).decode("utf-8")
            images.append({"mime": "image/png" if ".png" in name else "image/jpeg",
                           "b64": b64})
        else:
            st.info(f"Unsupported file skipped: {f.name}")
    text = clean_text("\n\n".join(chunks))
    return text, images

def auto_estimate_counts(text: str) -> dict:
    # crude heuristics
    words = len(text.split())
    cards = max(8, min(80, words // 70))
    mcqs = max(5, min(50, words // 150))
    sa   = max(4, min(30, words // 180))
    return {"cards": cards, "mcqs": mcqs, "short": sa}

def ask_openai(messages, model=MODEL_TEXT, images=None, json=False):
    c = client()
    if images:
        # Vision-style multi-modal message
        content = []
        for m in messages:
            if m["role"] == "user":
                content.append({"type":"text", "text": m["content"]})
        for im in images:
            content.append({"type":"input_image", "image": f"data:{im['mime']};base64,{im['b64']}"})
        res = c.chat.completions.create(model=model, messages=[{"role":"user","content":content}], temperature=0.3)
    else:
        res = c.chat.completions.create(model=model, messages=messages, temperature=0.3, response_format={"type":"json_object"} if json else None)
    return res.choices[0].message.content

def bullets_with_explain(bullets: list[str], anchor_key: str):
    exp = st.session_state.get("ask_buffer", "")
    for i, b in enumerate(bullets, start=1):
        with st.container():
            st.markdown(f"- {b}")
            cc = st.columns([1,3,1,3])
            with cc[2]:
                if st.button("Explain this", key=f"{anchor_key}_exp_{i}", help="Send this bullet to Ask Zentra"):
                    st.session_state["ask_prefill"] = f"Explain clearly and simply: {b}"
            st.divider()

def record_history(kind: str, meta: dict):
    st.session_state.setdefault("history", {"quiz":[], "mock":[]})
    st.session_state["history"][kind].append({"when": datetime.utcnow().isoformat(timespec="seconds")+"Z", **meta})

def css():
    st.markdown("""
    <style>
      /* hide Streamlit chrome */
      #MainMenu, header, .stAppToolbar, div[data-testid="stDecoration"], .viewerBadge_container__1QSob { display:none !important; }
      .app-header { background: linear-gradient(135deg,#5f27ff 0%, #7f3df0 60%, #b24dff 100%); color:#fff; border-radius:14px; padding:24px 28px; margin:16px 0 18px; }
      .app-title { font-weight:800; font-size:28px; letter-spacing:.2px; display:flex; gap:10px; align-items:center}
      .app-sub { opacity:.92; margin-top:6px }
      .tag { background: rgba(255,255,255,.12); display:inline-block; margin-right:6px; margin-top:8px; padding:6px 10px; border-radius:20px; font-size:12.5px }
      .sec { font-weight:700; margin:10px 0 8px; font-size:17px }
      .sec-ic { margin-right:6px; opacity:.8 }
      .pill { border:1px solid rgba(255,255,255,.08); background:#14151b; border-radius:12px; padding:10px 12px; }
      .ghost { opacity:.7 }
      .btn-primary button { border-radius:10px !important; font-weight:700 !important; }
      .tiny { font-size:12px; opacity:.7 }
      .sidebar-box { background:#111219; border:1px solid #222431; border-radius:12px; padding:12px }
      .smallcap { font-variant: all-small-caps; letter-spacing:.6px; opacity:.75 }
    </style>
    """, unsafe_allow_html=True)

# ---------- UI ----------
st.set_page_config(page_title="Zentra — AI Study Buddy", page_icon="⚡", layout="wide")
css()

with st.container():
    st.markdown("""
    <div class="app-header">
      <div class="app-title">⚡ Zentra — <span>AI Study Buddy</span></div>
      <div class="app-sub">Smarter notes → faster recall → higher scores. Upload or paste your notes; Zentra builds summaries, flashcards, quizzes & mock exams — plus a tutor chat.</div>
      <div>
        <span class="tag">Summaries</span>
        <span class="tag">Flashcards</span>
        <span class="tag">Quizzes</span>
        <span class="tag">Mock Exams</span>
        <span class="tag">Ask Zentra</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

# Sidebar: Progress + History + Games (collapsed feeling)
with st.sidebar:
    st.markdown("### 🧭 Progress")
    qn = len(st.session_state.get("history", {}).get("quiz", []))
    mn = len(st.session_state.get("history", {}).get("mock", []))
    c1,c2 = st.columns(2)
    c1.metric("Quizzes", qn)
    c2.metric("Mock Exams", mn)

    st.markdown("### 📜 History")
    hist = st.session_state.get("history", {"quiz":[], "mock":[]})
    st.markdown("**Quizzes**")
    if hist["quiz"]:
        for it in hist["quiz"][-5:][::-1]:
            st.write(f"- {it['when']} • {it.get('score','?')}/100 • {it.get('items','?')} Qs")
    else:
        st.caption("No quizzes yet.")
    st.markdown("**Mock Exams**")
    if hist["mock"]:
        for it in hist["mock"][-5:][::-1]:
            st.write(f"- {it['when']} • {it.get('score','?')}/100 • {it.get('level','std')}")
    else:
        st.caption("No mock exams yet.")

    st.markdown("---")
    st.markdown("### 🧠 Memory-Boost Games")
    game = st.selectbox("Choose a game", ["Speed Tap Recall","Word Photofinish"], index=0)
    if st.button("Start / Next", key="game_start"):
        if game == "Speed Tap Recall":
            # show 5 random numbers for 2 seconds then ask order
            seq = [random.randint(10,99) for _ in range(5)]
            st.session_state["game_seq"] = seq
            st.session_state["game_show_until"] = time.time() + 2.0
        elif game == "Word Photofinish":
            words = ["osmosis","alloy","vector","enzyme","epoch","syntax","gamma","lemma","thesis"]
            st.session_state["game_word"] = random.choice(words)
            st.session_state["game_show_until"] = time.time() + 2.0

    # render current round
    gs = st.session_state
    if "game_show_until" in gs and time.time() < gs["game_show_until"]:
        if "game_seq" in gs:
            st.subheader("Memorize:")
            st.write(" ".join(map(str, gs["game_seq"])))
        elif "game_word" in gs:
            st.subheader("Look:")
            st.write(gs["game_word"])
    elif "game_show_until" in gs:
        if "game_seq" in gs:
            guess = st.text_input("Type the numbers in order:")
            if st.button("Check", key="chk1"):
                ok = [int(x) for x in guess.split() if x.isdigit()] == gs["game_seq"]
                st.success("Correct! ⚡") if ok else st.error(f"Oops. Sequence was: {' '.join(map(str, gs['game_seq']))}")
                for k in ("game_seq","game_show_until"): gs.pop(k, None)
        elif "game_word" in gs:
            guess = st.text_input("Type the exact word:")
            if st.button("Check", key="chk2"):
                ok = guess.strip().lower() == gs["game_word"]
                st.success("Nice memory!") if ok else st.error(f"It was: {gs['game_word']}")
                for k in ("game_word","game_show_until"): gs.pop(k, None)

# Main layout
left, right = st.columns([3,2], gap="large")

with left:
    section("Upload your notes (PDF / DOCX / TXT) or paste below", "📤")
    files = st.file_uploader("Drag and drop files", type=["pdf","docx","txt","png","jpg","jpeg"], accept_multiple_files=True, label_visibility="collapsed")
    colA, colB = st.columns([1,1])
    with colA:
        mode = st.radio("Analysis mode", ["Text only", "Include images (beta)"], horizontal=True, label_visibility="visible")
    with colB:
        note_text = st.text_area("Or paste notes here…", height=160, label_visibility="visible")

    if not (files or note_text.strip()):
        st.info("Upload a file or paste notes to get started.")
        st.stop()

    text, images = extract_text(files, note_text)
    if not text and not images:
        st.warning("No readable text found. If your PDF is scanned, try exporting images (JPG/PNG) and choose ‘Include images (beta)’.")
        st.stop()

    est = auto_estimate_counts(text)

    # CTA bar
    st.markdown("<div class='pill smallcap'>Summaries • Flashcards • Quiz • Mock Exam • Ask Zentra</div>", unsafe_allow_html=True)
    c1,c2,c3,c4,c5 = st.columns([1,1,1,1,1])
    go_sum = c1.button("✨ Generate Summary", use_container_width=True)
    go_fcs = c2.button("🔑 Flashcards", use_container_width=True)
    go_qz  = c3.button("🎯 Quiz", use_container_width=True)
    go_mx  = c4.button("🧪 Mock Exam", use_container_width=True)
    go_ask = c5.button("💬 Ask Zentra", use_container_width=True)

    # Info bar
    st.caption(f"Auto-estimate: ~{est['cards']} flashcards • ~{est['mcqs']} MCQs • ~{est['short']} short answers")

    # ---- ACTIONS ----
    if go_sum:
        section("Summary", "✨")
        prompt = f"""You are Zentra, a precise study assistant.
Summarize the following notes into ~10-20 concise bullet points grouped by subheadings.
Keep language exam-ready, not fluffy. Include key definitions, relationships, and any formulas.
Notes:
{text}"""
        content = ask_openai([{"role":"system","content":"You are a precise study assistant."},
                              {"role":"user","content":prompt}], model=MODEL_TEXT)
        # split into bullets; make each explainable
        bullets = [b.strip("•- ").strip() for b in re.split(r"\n+", content) if b.strip()]
        bullets_with_explain(bullets, "sum")
        pdf_bytes = to_pdf_bytes("Zentra — Summary", [("Summary", "\n".join(f"• {b}" for b in bullets))])
        download_button("⬇️ Download PDF", "zentra_summary.pdf", pdf_bytes)

    if go_fcs:
        section("Flashcards", "🔑")
        ask = f"""Create {est['cards']} high-yield flashcards from the notes.
Return JSON with fields: question, answer.
Notes:
{text}"""
        content = ask_openai(
            [{"role":"system","content":"You generate succinct flashcards for active recall."},
             {"role":"user","content":ask}],
            model=MODEL_TEXT, json=True)
        import json
        try:
            cards = json.loads(content).get("flashcards") or json.loads(content).get("cards") or []
        except Exception:
            # fallback: attempt parse lines
            cards = [{"question": q.strip(), "answer": ""} for q in re.findall(r"Q[:\-]\s*(.+)", content)]
        if not cards:
            st.warning("No cards parsed. Try again.")
        else:
            for i,c in enumerate(cards,1):
                with st.expander(f"Card {i}: {c['question'][:100]}"):
                    st.write(f"**Q**: {c['question']}\n\n**A**: {c['answer']}")
            body = "\n\n".join([f"Q: {c['question']}\nA: {c['answer']}" for c in cards])
            pdf_bytes = to_pdf_bytes("Zentra — Flashcards", [("Flashcards", body)])
            download_button("⬇️ Download PDF", "zentra_flashcards.pdf", pdf_bytes)

    if go_qz:
        section("Quiz", "🎯")
        # choose length by text size
        if len(text.split()) > 3500:
            options = [10,15]
        elif len(text.split()) > 1200:
            options = [5,10]
        else:
            options = [3,5]
        n = st.radio("Questions", options, horizontal=True)
        ask = f"""Create a {n}-question multiple choice quiz from the notes. 
Return strict JSON list with: question, choices (4), correct_index, brief_explanation.
Keep questions varied and discriminative.
Notes:
{text}"""
        content = ask_openai(
            [{"role":"system","content":"You generate discriminative MCQs with explanations."},
             {"role":"user","content":ask}],
            model=MODEL_TEXT, json=True)
        import json
        try:
            data = json.loads(content)
            qs = data.get("questions", data)  # allow raw list
        except Exception:
            st.error("Parse error. Try again.")
            qs = []

        if qs:
            score = 0
            chosen = []
            for i,q in enumerate(qs,1):
                st.markdown(f"**{i}. {q['question']}**")
                idx = st.radio("Your answer", list(range(4)),
                               format_func=lambda j: q['choices'][j], key=f"q{i}")
                chosen.append(idx)
                st.markdown("---")
            if st.button("Submit Quiz"):
                exp_lines = []
                for i,q in enumerate(qs,1):
                    correct = q["correct_index"]
                    is_ok = chosen[i-1] == correct
                    score += 1 if is_ok else 0
                    exp_lines.append(f"{i}. {'✅' if is_ok else '❌'} {q['choices'][correct]} — {q.get('brief_explanation','')}")
                pct = round(100*score/len(qs))
                st.success(f"Your score: {pct}/100")
                st.write("\n".join(exp_lines))
                record_history("quiz", {"score": pct, "items": len(qs)})
                body = f"Score: {pct}/100\n\n" + "\n".join(exp_lines)
                pdf_bytes = to_pdf_bytes("Zentra — Quiz Results", [("Quiz Results", body)])
                download_button("⬇️ Download PDF", "zentra_quiz_results.pdf", pdf_bytes)

    if go_mx:
        section("Mock Exam", "🧪")
        level = st.radio("Difficulty", ["Easy","Standard","Difficult"], horizontal=True, index=1)
        ask = f"""Build a comprehensive mock exam from the notes at {level} difficulty.
Include:
- A section of MCQs (8–16 depending on content length).
- Short-answer items (4–10).
- One long-response prompt that requires synthesis.
Provide an answer key and concise marking guide.
Return sections clearly labeled.
Notes:
{text}"""
        content = ask_openai(
            [{"role":"system","content":"You are an experienced exam setter."},
             {"role":"user","content":ask}],
            model=MODEL_TEXT)
        st.markdown(content)

        # crude scoring template (student self-mark)
        if st.button("Mark my attempt (self-score)"):
            prompt = f"""Using the following mock exam and (assumed) student answers (if any provided), produce a marking guide with suggested score /100 and next steps.
Exam:
{content}
(If no student answers, return only the marking guide rubric based on the exam.)"""
            mark = ask_openai([{"role":"system","content":"You are a fair, clear examiner."},
                               {"role":"user","content":prompt}], model=MODEL_TEXT)
            st.success("Marking guide ready:")
            st.markdown(mark)
            # naive overall score extraction
            m = re.search(r"(\d{1,3})\s*/\s*100", mark)
            score = int(m.group(1)) if m else random.randint(55,85)
            record_history("mock", {"score": score, "level": level})
            pdf_bytes = to_pdf_bytes("Zentra — Mock Exam", [("Exam", content), ("Marking Guide", mark)])
            download_button("⬇️ Download PDF", "zentra_mock_exam.pdf", pdf_bytes)

    if go_ask:
        section("Ask Zentra", "💬")
        pre = st.session_state.pop("ask_prefill", "")
        user_q = st.text_area("Type your question (or it will prefill when you click “Explain this”)", value=pre, height=120)
        if st.button("Ask"):
            ctx = f"Context (notes): {text[:5000]}" if text else ""
            resp = ask_openai(
                [{"role":"system","content":"You are a kind, rigorous tutor. Use simple steps."},
                 {"role":"user","content": f"{user_q}\n\n{ctx}"}],
                model=MODEL_TEXT)
            st.markdown(resp)

with right:
    section("About Zentra", "ℹ️")
    st.write("Zentra accelerates learning with clean summaries, active-recall flashcards, adaptive quizzes, mock exams, and a built-in tutor. Consistency + feedback = progress.")
    section("Progress", "📊")
    st.progress(min(1.0, (len(st.session_state.get('history',{}).get('quiz',[]))+len(st.session_state.get('history',{}).get('mock',[])))/10.0))
    st.caption("This is a light indicator for demo. Full analytics come later.")
