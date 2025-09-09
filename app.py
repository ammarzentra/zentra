# app.py — Zentra (Final Pro Build)
# Features:
# - Upload PDF/DOCX/TXT or paste notes
# - Summary / Flashcards / Quiz (end answers) / Mock Exam (grading + feedback)
# - Ask Zentra (AI chat)
# - Progress Dashboard (counts + XP)
# - Adaptive Next Steps (keeps students engaged)
# - Download PDF of outputs (summary, flashcards, quiz, mock)
# - Premium UI styling

import streamlit as st
from openai import OpenAI
import os, io, json, time, datetime
from fpdf import FPDF
import PyPDF2
import docx

# ==========================
# CONFIG & CLIENT
# ==========================
st.set_page_config(page_title="Zentra — AI Study Buddy", page_icon="⚡", layout="wide")

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
MODEL = "gpt-4o-mini"

# ==========================
# STYLE
# ==========================
st.markdown("""
<style>
    .main { background: #0b0f18; color: #f5f7fb; }
    .block-container { padding-top: 1.5rem; }
    .zentra-hero {
        background: radial-gradient(1200px 500px at 10% -10%, #1d1148 10%, transparent 60%),
                    radial-gradient(1000px 500px at 90% -20%, #28143a 10%, transparent 60%);
        border: 1px solid rgba(255,255,255,0.06);
        padding: 22px 26px;
        border-radius: 16px;
        box-shadow: 0 12px 40px rgba(0,0,0,0.45);
        margin-bottom: 18px;
    }
    .zentra-title { font-size: 28px; font-weight: 800; letter-spacing: .2px; }
    .zentra-sub { opacity: .9; margin-top: 6px; }
    .zentra-card {
        background: #11172a;
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 14px;
        padding: 18px;
        margin-top: 16px;
        box-shadow: 0 10px 24px rgba(0,0,0,0.35);
    }
    .result-card {
        background: #0f1424;
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 12px;
        padding: 16px;
        margin-top: 10px;
    }
    div.stButton > button {
        background: linear-gradient(90deg, #7b2ff7, #f107a3);
        color: #fff; border: 0; border-radius: 12px;
        padding: 10px 18px; font-weight: 700;
        box-shadow: 0 8px 20px rgba(241,7,163,0.35);
        transition: .2s ease;
    }
    div.stButton > button:hover { transform: translateY(-1px) scale(1.02); }
    .small { font-size: 13px; opacity: .85; }
    .pill {
        display:inline-block; padding:4px 10px; border-radius:9999px;
        background:rgba(255,255,255,0.06); font-size:12px; margin-right:6px;
    }
    .stat {
        background:#0f1424; border:1px solid rgba(255,255,255,0.06);
        border-radius:10px; padding:10px 12px; text-align:center;
    }
    .stat b { font-size:20px; display:block; }
</style>
""", unsafe_allow_html=True)

# ==========================
# SESSION
# ==========================
if "summary" not in st.session_state: st.session_state.summary = ""
if "flashcards" not in st.session_state: st.session_state.flashcards = ""
if "quiz_json" not in st.session_state: st.session_state.quiz_json = None
if "quiz_answers" not in st.session_state: st.session_state.quiz_answers = {}
if "mock_json" not in st.session_state: st.session_state.mock_json = None
if "mock_answers" not in st.session_state: st.session_state.mock_answers = {}
if "ask_history" not in st.session_state: st.session_state.ask_history = []
if "xp" not in st.session_state: st.session_state.xp = 0
if "counts" not in st.session_state: st.session_state.counts = {"summaries":0,"flashcards":0,"quizzes":0,"mocks":0}
if "last_used_date" not in st.session_state: st.session_state.last_used_date = None
if "streak" not in st.session_state: st.session_state.streak = 0

def bump_streak():
    today = datetime.date.today()
    if st.session_state.last_used_date is None:
        st.session_state.streak = 1
    else:
        delta = (today - st.session_state.last_used_date).days
        if delta == 1:
            st.session_state.streak += 1
        elif delta > 1:
            st.session_state.streak = 1
    st.session_state.last_used_date = today

# ==========================
# HELPERS
# ==========================
def extract_text(file, pasted_text):
    if file is not None:
        if file.type == "application/pdf":
            reader = PyPDF2.PdfReader(file)
            txt = "\n".join([(p.extract_text() or "") for p in reader.pages])
            return txt.strip()
        if "wordprocessingml" in file.type:
            d = docx.Document(file)
            return "\n".join(par.text for par in d.paragraphs).strip()
        if file.type == "text/plain":
            return file.read().decode("utf-8", errors="ignore").strip()
    return (pasted_text or "").strip()

def ai_text(prompt, temperature=0.2):
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role":"system","content":"You are Zentra, an elite, motivating AI study coach. Be concise, structured, and helpful."},
            {"role":"user","content": prompt}
        ],
        temperature=temperature
    )
    return resp.choices[0].message.content.strip()

def ai_json(prompt, temperature=0.2):
    """Ask model to return strict JSON, then parse."""
    json_prompt = f"""Return STRICT JSON only. No prose, no markdown fences.
{prompt}"""
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role":"system","content":"Return STRICT JSON only. If unsure, still return valid empty JSON for the schema."},
            {"role":"user","content": json_prompt}
        ],
        temperature=temperature
    )
    raw = resp.choices[0].message.content.strip()
    # try to clean accidental fences
    raw = raw.replace("```json","").replace("```","").strip()
    try:
        return json.loads(raw)
    except:
        # fallback: try to find first {...}
        try:
            start = raw.find("{"); end = raw.rfind("}")
            return json.loads(raw[start:end+1])
        except:
            return None

def to_pdf_bytes(title, sections):
    """
    sections: list of tuples (header, text)
    returns bytes for download
    """
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()
    pdf.add_font('Arial', '', '', uni=True)
    pdf.set_font("Arial", size=16)
    pdf.multi_cell(0, 10, txt=title)
    pdf.ln(2)
    pdf.set_font("Arial", size=12)
    for header, text in sections:
        pdf.set_font("Arial", size=13)
        pdf.multi_cell(0, 8, txt=f"• {header}")
        pdf.set_font("Arial", size=11)
        for line in (text or "").split("\n"):
            pdf.multi_cell(0, 6, txt=line)
        pdf.ln(2)
    mem = io.BytesIO()
    pdf.output(mem)
    mem.seek(0)
    return mem

def add_xp(amount):
    st.session_state.xp += amount
    bump_streak()

def next_steps(after):
    mapping = {
        "summary": "Great — now turn those bullets into 🔑 Flashcards for active recall.",
        "flashcards": "Nice! Test yourself with a quick 🎯 Quiz.",
        "quiz": "Solid effort. Level up with a 📊 Mock Exam to simulate exam pressure.",
        "mock": "Review mistakes as new 🔑 Flashcards, then take another 🎯 Quiz tomorrow.",
        "ask": "Good question! If it relates to your notes, try ✨ Summarize, then 🔑 Flashcards."
    }
    return mapping.get(after,"Keep going — small consistent reps beat cramming.")

# ==========================
# HEADER / SIDEBAR
# ==========================
st.markdown("""
<div class="zentra-hero">
  <div class="zentra-title">⚡ Zentra – AI Study Buddy</div>
  <div class="zentra-sub">Smarter notes → faster recall → higher scores. Upload your notes and let Zentra build summaries, flashcards, quizzes, and mock exams — plus a tutor you can chat with.</div>
  <div style="margin-top:10px;">
    <span class="pill">PDF/DOCX/TXT</span>
    <span class="pill">Summaries</span>
    <span class="pill">Flashcards</span>
    <span class="pill">Quizzes</span>
    <span class="pill">Mock Exams</span>
    <span class="pill">Ask Zentra</span>
  </div>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.subheader("About Zentra")
    st.caption("Zentra accelerates learning with clean summaries, active-recall flashcards, adaptive quizzes, mock exams, and a built-in AI tutor. Consistency + feedback = progress.")
    st.subheader("Progress")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"<div class='stat'><b>{st.session_state.counts['summaries']}</b>Summaries</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='stat'><b>{st.session_state.counts['quizzes']}</b>Quizzes</div>", unsafe_allow_html=True)
    with c2:
        st.markdown(f"<div class='stat'><b>{st.session_state.counts['flashcards']}</b>Flashcards</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='stat'><b>{st.session_state.counts['mocks']}</b>Mock Exams</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='stat'><b>{st.session_state.xp}</b>Zentra XP</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='stat'><b>{st.session_state.streak}</b>Day Streak</div>", unsafe_allow_html=True)

    with st.expander("Disclaimer"):
        st.write("Zentra is your AI study assistant. Always review outputs and combine with your own understanding for best results.")

# ==========================
# INPUT AREA
# ==========================
left, right = st.columns([1.15, 0.85], gap="large")
with left:
    st.markdown("<div class='zentra-card'>", unsafe_allow_html=True)
    uploaded = st.file_uploader("📂 Upload notes (PDF / DOCX / TXT)", type=["pdf","docx","txt"])
    pasted = st.text_area("✍️ Or paste notes here", height=180, placeholder="Paste notes if you aren’t uploading a file…")
    source_text = extract_text(uploaded, pasted)
    st.markdown("</div>", unsafe_allow_html=True)

with right:
    st.markdown("<div class='zentra-card'>", unsafe_allow_html=True)
    st.markdown("**What each feature does**")
    st.caption("✨ Summarize – condenses your notes into exam-ready bullets.")
    st.caption("🔑 Flashcards – creates Q&A for active recall.")
    st.caption("🎯 Quiz – 5 MCQs, answers revealed at the end.")
    st.caption("📊 Mock Exam – 10 Q exam with grading + feedback.")
    st.caption("💬 Ask Zentra – chat with the tutor for any concept.")
    st.markdown("</div>", unsafe_allow_html=True)

# ==========================
# ACTION ROW
# ==========================
c1, c2, c3, c4, c5 = st.columns(5)
do_sum = c1.button("✨ Summarize", help="Get your notes condensed into exam-ready bullet points.")
do_card = c2.button("🔑 Flashcards", help="Auto-generate Q&A cards for active recall.")
do_quiz = c3.button("🎯 Quiz", help="Practice with MCQs. Answers shown at submission.")
do_mock = c4.button("📊 Mock Exam", help="10 questions + grading and personalized feedback.")
do_chat = c5.button("💬 Ask Zentra", help="Ask anything like a tutor. Explanations included.")

# ==========================
# SUMMARY
# ==========================
if do_sum:
    if not source_text:
        st.warning("Upload a file or paste some notes first.")
    else:
        with st.spinner("Summarizing…"):
            st.session_state.summary = ai_text(
                f"Summarize the following into 6–10 punchy bullet points. Prioritize key definitions, formulas, cause→effect, and exam-relevant facts.\n\n{source_text}"
            )
        st.session_state.counts["summaries"] += 1
        add_xp(10)
        st.success("📌 Summary")
        st.markdown(f"<div class='result-card'>{st.session_state.summary}</div>", unsafe_allow_html=True)
        st.info(next_steps("summary"))

# ==========================
# FLASHCARDS
# ==========================
if do_card:
    if not source_text:
        st.warning("Upload a file or paste some notes first.")
    else:
        with st.spinner("Creating flashcards…"):
            data = ai_json(
                f"""Create 12 flashcards from the notes in JSON:
{{
 "flashcards":[{{"q":"", "a":""}}]
}}
Focus on high-yield concepts, steps, definitions, and typical trick points. Notes:\n{source_text}
"""
            )
        if not data or "flashcards" not in data:
            st.error("Couldn't parse flashcards. Try again.")
        else:
            out = []
            for i, c in enumerate(data["flashcards"], 1):
                q, a = c.get("q","").strip(), c.get("a","").strip()
                if not q: continue
                st.markdown(f"<div class='result-card'><b>Q{i}:</b> {q}<br><br><b>A:</b> {a}</div>", unsafe_allow_html=True)
                out.append(f"Q{i}: {q}\nA: {a}")
            st.session_state.flashcards = "\n\n".join(out)
            st.session_state.counts["flashcards"] += 1
            add_xp(12)
            st.info(next_steps("flashcards"))

# ==========================
# QUIZ (MCQ)
# ==========================
if do_quiz:
    if not source_text:
        st.warning("Upload a file or paste some notes first.")
    else:
        with st.spinner("Generating quiz…"):
            quiz = ai_json(
                f"""Create 5 MCQs in strict JSON:
{{
 "mcq":[{{"q":"","options":["A","B","C","D"],"answer_index":0,"explanation":""}}]
}}
MCQs should be conceptually varied and exam-style. Notes:\n{source_text}
"""
            )
        if not quiz or "mcq" not in quiz:
            st.error("Couldn't parse quiz. Try again.")
        else:
            st.session_state.quiz_json = quiz
            st.session_state.quiz_answers = {}
            st.session_state.counts["quizzes"] += 1
            add_xp(15)

if st.session_state.quiz_json:
    st.subheader("🎯 Quiz")
    for i, q in enumerate(st.session_state.quiz_json["mcq"], 1):
        st.markdown(f"**{i}. {q['q']}**")
        choice = st.radio(f"q{i}", q["options"], index=None)
        st.session_state.quiz_answers[i] = choice
    if st.button("Submit Quiz"):
        correct = 0
        details = []
        for i, q in enumerate(st.session_state.quiz_json["mcq"], 1):
            ans = st.session_state.quiz_answers.get(i, None)
            correct_idx = q["answer_index"]
            correct_text = q["options"][correct_idx]
            is_right = (ans == correct_text)
            if is_right: correct += 1
            details.append((i, is_right, q.get("explanation","")))
        st.success(f"Score: {correct} / {len(st.session_state.quiz_json['mcq'])}")
        for i, ok, expl in details:
            st.markdown(f"<div class='result-card'>Q{i}: {'✅ Correct' if ok else '❌ Incorrect'}<br><br><b>Why:</b> {expl}</div>", unsafe_allow_html=True)
        # personalized feedback & next steps
        fb = ai_text(
            f"You are a coach. A student scored {correct}/{len(st.session_state.quiz_json['mcq'])} on these MCQs:\n{json.dumps(st.session_state.quiz_json)}\nGive concise feedback bullets + next study steps."
        )
        st.info(f"**Personalized Feedback & Next Steps**\n\n{fb}")

# ==========================
# MOCK EXAM
# ==========================
if do_mock:
    if not source_text:
        st.warning("Upload a file or paste some notes first.")
    else:
        with st.spinner("Building mock exam…"):
            mock = ai_json(
                f"""Create a mock exam in strict JSON:
{{
 "mcq":[{{"q":"","options":["A","B","C","D"],"answer_index":0,"explanation":""}}],
 "short":[{{"q":"", "ideal_answer":""}}]
}}
Provide 6 MCQs + 3 short answers. Keep difficulty mixed. Notes:\n{source_text}
"""
            )
        if not mock or "mcq" not in mock or "short" not in mock:
            st.error("Couldn't parse mock exam. Try again.")
        else:
            st.session_state.mock_json = mock
            st.session_state.mock_answers = {}
            st.session_state.counts["mocks"] += 1
            add_xp(25)

if st.session_state.mock_json:
    st.subheader("📊 Mock Exam")
    st.markdown("**MCQs**")
    for i, q in enumerate(st.session_state.mock_json["mcq"], 1):
        st.markdown(f"**{i}. {q['q']}**")
        choice = st.radio(f"m{i}", q["options"], index=None)
        st.session_state.mock_answers[f"m{i}"] = choice
    st.markdown("**Short Answers**")
    for i, q in enumerate(st.session_state.mock_json["short"], 1):
        ans = st.text_area(f"SA{i}: {q['q']}", height=80)
        st.session_state.mock_answers[f"s{i}"] = ans

    if st.button("Submit Mock Exam"):
        # grade MCQ
        correct_m = 0
        mcq_feedback = []
        for i, q in enumerate(st.session_state.mock_json["mcq"], 1):
            sel = st.session_state.mock_answers.get(f"m{i}", None)
            correct_idx = q["answer_index"]; correct_txt = q["options"][correct_idx]
            ok = (sel == correct_txt)
            if ok: correct_m += 1
            mcq_feedback.append((i, ok, q.get("explanation","")))
        # grade shorts via rubric with AI
        rubric = ai_text(
            f"Grade these short answers 0-5 each (5=excellent). Give brief justification and a one-line improvement tip.\n\n"
            f"Ideal answers: {json.dumps(st.session_state.mock_json['short'])}\n"
            f"Student answers: {json.dumps({k:v for k,v in st.session_state.mock_answers.items() if k.startswith('s')})}"
        )
        st.success(f"MCQ Score: {correct_m} / {len(st.session_state.mock_json['mcq'])}")
        for i, ok, expl in mcq_feedback:
            st.markdown(f"<div class='result-card'>MCQ {i}: {'✅ Correct' if ok else '❌ Incorrect'}<br><br><b>Why:</b> {expl}</div>", unsafe_allow_html=True)

        st.markdown(f"<div class='result-card'><b>Short Answer Grading (AI Rubric)</b><br><br>{rubric}</div>", unsafe_allow_html=True)
        coach = ai_text(
            f"Act as a coach. Based on this mock exam (MCQ score {correct_m}) and the rubric feedback, give the student tailored next steps (bulleted) and a 3-day mini plan."
        )
        st.info(f"**Personalized Feedback & Next Steps**\n\n{coach}")

# ==========================
# ASK ZENTRA (CHAT)
# ==========================
if do_chat:
    st.subheader("💬 Ask Zentra")
    q = st.text_input("Ask anything about your topic:")
    if q:
        with st.spinner("Zentra is thinking…"):
            # context aware: include notes if available
            context = f"Context from notes:\n{source_text[:2000]}" if source_text else "No extra context."
            ans = ai_text(
                f"You are a patient tutor. Explain clearly and concisely. Use steps or examples where helpful.\n{context}\n\nQuestion: {q}"
            )
            st.session_state.ask_history.append(("You", q))
            st.session_state.ask_history.append(("Zentra", ans))
            add_xp(8)
    if st.session_state.ask_history:
        for who, msg in st.session_state.ask_history[-8:]:
            st.markdown(f"<div class='result-card'><b>{who}:</b><br>{msg}</div>", unsafe_allow_html=True)
        st.caption(next_steps("ask"))

# ==========================
# DOWNLOADS (PDFs)
# ==========================
st.markdown("<div class='zentra-card'>", unsafe_allow_html=True)
st.subheader("📥 Download Results")
colA, colB, colC, colD = st.columns(4)

# Summary PDF
with colA:
    if st.session_state.summary:
        pdf = to_pdf_bytes("Zentra — Summary", [("Summary", st.session_state.summary)])
        st.download_button("⬇️ Summary PDF", data=pdf, file_name="zentra_summary.pdf", mime="application/pdf", use_container_width=True)
    else:
        st.button("⬇️ Summary PDF", disabled=True, use_container_width=True)

# Flashcards PDF
with colB:
    if st.session_state.flashcards:
        pdf = to_pdf_bytes("Zentra — Flashcards", [("Flashcards", st.session_state.flashcards)])
        st.download_button("⬇️ Flashcards PDF", data=pdf, file_name="zentra_flashcards.pdf", mime="application/pdf", use_container_width=True)
    else:
        st.button("⬇️ Flashcards PDF", disabled=True, use_container_width=True)

# Quiz PDF (render last quiz json -> show with answers & explanations)
with colC:
    if st.session_state.quiz_json:
        # Flatten quiz to text
        lines = []
        for i, q in enumerate(st.session_state.quiz_json["mcq"], 1):
            lines.append(f"{i}. {q['q']}")
            for opt in q["options"]:
                lines.append(f" - {opt}")
            lines.append(f"Answer: {q['options'][q['answer_index']]}")
            if q.get("explanation"): lines.append(f"Why: {q['explanation']}")
            lines.append("")
        pdf = to_pdf_bytes("Zentra — Quiz", [("Quiz", "\n".join(lines))])
        st.download_button("⬇️ Quiz PDF", data=pdf, file_name="zentra_quiz.pdf", mime="application/pdf", use_container_width=True)
    else:
        st.button("⬇️ Quiz PDF", disabled=True, use_container_width=True)

# Mock Exam PDF
with colD:
    if st.session_state.mock_json:
        lines = []
        lines.append("MCQs")
        for i, q in enumerate(st.session_state.mock_json["mcq"], 1):
            lines.append(f"{i}. {q['q']}")
            for opt in q["options"]:
                lines.append(f" - {opt}")
            lines.append(f"Answer: {q['options'][q['answer_index']]}")
            if q.get("explanation"): lines.append(f"Why: {q['explanation']}")
            lines.append("")
        lines.append("\nShort Answers")
        for i, q in enumerate(st.session_state.mock_json["short"], 1):
            lines.append(f"{i}. {q['q']}")
            lines.append(f"Ideal: {q.get('ideal_answer','')}\n")
        pdf = to_pdf_bytes("Zentra — Mock Exam", [("Mock Exam", "\n".join(lines))])
        st.download_button("⬇️ Mock Exam PDF", data=pdf, file_name="zentra_mock_exam.pdf", mime="application/pdf", use_container_width=True)
    else:
        st.button("⬇️ Mock Exam PDF", disabled=True, use_container_width=True)

st.markdown("</div>", unsafe_allow_html=True)

  

       
