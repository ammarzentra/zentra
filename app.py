import streamlit as st
from openai import OpenAI
import os
from io import BytesIO
from fpdf import FPDF

# --- Setup ---
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
st.set_page_config(page_title="⚡ Zentra — AI Study Buddy", layout="wide")

# --- CSS Hacks (branding + drawer chat) ---
st.markdown("""
    <style>
    footer, .viewerBadge_container__1QSob, #MainMenu {visibility: hidden;}
    .stButton>button {border-radius: 10px; padding: 10px 18px; font-weight: 600;}
    .zentra-hero {background: linear-gradient(90deg, #5a00ff, #00c3ff);
                  padding: 20px; border-radius: 12px; color: white; text-align:center;}
    .zentra-hero h1 {font-size: 2em; margin-bottom: 4px;}
    .zentra-hero p {font-size: 1.1em; margin-top: 0;}
    .drawer {position: fixed; top: 0; right: -400px; width: 400px; height: 100%;
             background: #1e1e2f; color: white; padding: 20px; transition: right 0.4s;}
    .drawer.open {right: 0;}
    .chat-box {height: 70vh; overflow-y: auto; border: 1px solid #444;
               padding: 10px; border-radius: 6px; background: #2a2a3d;}
    </style>
""", unsafe_allow_html=True)

# --- Hero Section ---
st.markdown("""
<div class="zentra-hero">
    <h1>⚡ Zentra — AI Study Buddy</h1>
    <p>Smarter notes → better recall → higher scores.</p>
</div>
""", unsafe_allow_html=True)

# --- Sidebar ---
st.sidebar.title("📊 Progress Dashboard")
st.sidebar.metric("Quizzes Taken", 0)
st.sidebar.metric("Mock Exams Taken", 0)

st.sidebar.markdown("---")
st.sidebar.subheader("ℹ️ About Zentra")
st.sidebar.info("Zentra accelerates learning with summaries, flashcards, adaptive quizzes, "
                "mock exams, and a built-in tutor.")

st.sidebar.subheader("📌 Tool Guide")
st.sidebar.write("📄 **Summaries** → Concise, exam-focused notes")
st.sidebar.write("🗂️ **Flashcards** → Active recall study method")
st.sidebar.write("🎯 **Quizzes** → Adaptive difficulty questions")
st.sidebar.write("📝 **Mock Exams** → Full-length assessment with feedback")
st.sidebar.write("🤖 **Ask Zentra** → Your AI-powered study buddy")

st.sidebar.subheader("📈 Adaptive Learning")
st.sidebar.write("Quizzes adapt based on note length. Mock exams test concepts broadly and mark performance.")

# --- Upload Notes ---
st.subheader("📥 Upload your notes (PDF/DOCX/TXT) or paste below")
uploaded_file = st.file_uploader("Drag & drop files", type=["pdf","docx","txt"])
notes = st.text_area("Or paste notes here…")

analysis_mode = st.radio("Analysis mode", ["📝 Text only", "🖼 Include images (beta)"])

# Helper: Save as PDF
def save_as_pdf(content, title):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(0, 10, content)
    buffer = BytesIO()
    pdf.output(buffer)
    return buffer

# --- Action Buttons ---
col1, col2, col3, col4, col5 = st.columns(5)
with col1: summary_btn = st.button("📄 Summaries", help="Generate focused, exam-ready summaries.")
with col2: flashcard_btn = st.button("🗂️ Flashcards", help="Create active-recall flashcards from notes.")
with col3: quiz_btn = st.button("🎯 Quizzes", help="Adaptive MCQs based on your notes.")
with col4: mockexam_btn = st.button("📝 Mock Exams", help="Full-length exam (MCQs + written) with marking.")
with col5: askzentra_btn = st.button("🤖 Ask Zentra", help="Chat with Zentra — your AI tutor.")

content_text = notes if notes.strip() else (uploaded_file.name if uploaded_file else "")

# --- Summaries ---
if summary_btn and content_text:
    with st.spinner("Generating summary..."):
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"system","content":"You are a concise academic summarizer."},
                      {"role":"user","content": f"Summarize this clearly:\n{content_text}"}]
        )
        summary = resp.choices[0].message.content
        st.success(summary)
        st.download_button("⬇️ Download Summary", save_as_pdf(summary,"Summary"), file_name="summary.pdf")

# --- Flashcards ---
if flashcard_btn and content_text:
    with st.spinner("Creating flashcards..."):
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"system","content":"You generate flashcards for active recall."},
                      {"role":"user","content": f"Make flashcards from:\n{content_text}"}]
        )
        flashcards = resp.choices[0].message.content
        st.info(flashcards)
        st.download_button("⬇️ Download Flashcards", save_as_pdf(flashcards,"Flashcards"), file_name="flashcards.pdf")

# --- Quizzes ---
if quiz_btn and content_text:
    with st.spinner("Generating quiz..."):
        q_count = 5 if len(content_text) < 500 else 10 if len(content_text) < 2000 else 15
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"system","content":"You generate adaptive MCQs with 4 options."},
                      {"role":"user","content": f"Create {q_count} multiple choice questions from:\n{content_text}"}]
        )
        quiz = resp.choices[0].message.content
        st.warning(quiz)
        st.download_button("⬇️ Download Quiz", save_as_pdf(quiz,"Quiz"), file_name="quiz.pdf")

# --- Mock Exam ---
if mockexam_btn and content_text:
    difficulty = st.radio("Select difficulty:", ["Easy","Standard","Difficult"])
    if st.button("Generate Exam Now"):
        with st.spinner("Building full mock exam..."):
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role":"system","content":"You generate full mock exams with MCQs, short answers, long answers, and marking (0-100)."},
                          {"role":"user","content": f"Create a {difficulty} mock exam from:\n{content_text}"}]
            )
            exam = resp.choices[0].message.content
            st.error(exam)
            st.download_button("⬇️ Download Mock Exam", save_as_pdf(exam,"Exam"), file_name="mock_exam.pdf")

# --- Ask Zentra Side Drawer ---
if askzentra_btn:
    st.markdown("""
    <script>
    document.querySelectorAll('.drawer').forEach(d => d.classList.add('open'));
    </script>
    """, unsafe_allow_html=True)

st.markdown("""
<div class="drawer" id="zentra-drawer">
  <h3>🤖 Ask Zentra</h3>
  <div class="chat-box" id="chat-box"></div>
</div>
""", unsafe_allow_html=True)

# --- Right-click Highlight Mockup ---
st.markdown("""
<script>
document.addEventListener("mouseup", function(){
  let text = window.getSelection().toString();
  if(text){
    let ask = confirm("Ask Zentra about: " + text + "?");
    if(ask){ alert("This will be sent to Zentra in full version."); }
  }
});
</script>
""", unsafe_allow_html=True)
