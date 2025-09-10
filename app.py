import streamlit as st
import os
from openai import OpenAI
import PyPDF2
import docx2txt
from io import BytesIO
from fpdf import FPDF

# ============== CONFIG ==============
st.set_page_config(
    page_title="Zentra — AI Study Buddy",
    page_icon="⚡",
    layout="wide",
)

# ============== STYLE ==============
hide_streamlit_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stAppDeployButton {display:none;}
    .viewerBadge_link__qRIco {display:none;}
    .st-emotion-cache-12fmjuu {display:none;}
    </style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

gradient = """
    <style>
    .hero {
        padding: 1.5rem;
        border-radius: 12px;
        background: linear-gradient(90deg, #7B2FF7 0%, #00C9FF 100%);
        text-align: center;
        color: white;
    }
    .hero h1 { font-size: 2rem; font-weight: bold; }
    .hero p { font-size: 1rem; margin-top: -10px; }
    .chat-button {
        position: fixed;
        bottom: 20px; right: 20px;
        background: #7B2FF7;
        color: white; border-radius: 50px;
        padding: 12px 20px;
        font-weight: bold; cursor: pointer;
    }
    </style>
"""
st.markdown(gradient, unsafe_allow_html=True)

# ============== OPENAI CLIENT ==============
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# ============== FUNCTIONS ==============
def extract_text(file):
    if file.name.endswith(".pdf"):
        pdf_reader = PyPDF2.PdfReader(file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() or ""
        return text
    elif file.name.endswith(".docx"):
        return docx2txt.process(file)
    elif file.name.endswith(".txt"):
        return file.read().decode("utf-8")
    else:
        return ""

def save_as_pdf(text, title):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    for line in text.split("\n"):
        pdf.multi_cell(0, 10, line)
    buffer = BytesIO()
    pdf.output(buffer, 'F')
    return buffer.getvalue()

def ask_openai(prompt, notes):
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role":"system","content":prompt},
            {"role":"user","content":notes}
        ]
    )
    return resp.choices[0].message.content

# ============== SIDEBAR ==============
with st.sidebar:
    st.subheader("📊 Progress")
    st.metric("Quizzes", 0)
    st.metric("Mock Exams", 0)

    st.subheader("⚡ About Zentra")
    st.caption("AI-powered study buddy → Summaries, flashcards, quizzes, and exams.")

    st.subheader("🔑 What each tool does")
    st.markdown("""
    - **Summaries** → Exam-ready notes  
    - **Flashcards** → Spaced-recall Qs  
    - **Quizzes** → MCQs w/ answers  
    - **Mock Exams** → Full exams w/ marking  
    - **Ask Zentra** → Your study tutor  
    """)

# ============== HERO HEADER ==============
st.markdown("""
<div class="hero">
    <h1>⚡ Zentra — AI Study Buddy</h1>
    <p>Upload notes → Get summaries, flashcards, quizzes, and mock exams.</p>
</div>
""", unsafe_allow_html=True)

# ============== FILE UPLOAD ==============
st.subheader("📥 Upload your notes")
uploaded_file = st.file_uploader("Upload PDF / DOCX / TXT", type=["pdf","docx","txt"])

notes = ""
if uploaded_file:
    notes = extract_text(uploaded_file)

manual_text = st.text_area("✍️ Or paste notes here…")
if manual_text.strip():
    notes = manual_text

# ============== FEATURES ==============
st.subheader("📌 What do you need?")
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    if st.button("📄 Summaries") and notes:
        summary = ask_openai("Summarize clearly in bullet points", notes)
        st.success(summary)
        st.download_button("⬇️ Download Summary", save_as_pdf(summary,"Summary"), file_name="summary.pdf")

with col2:
    if st.button("🃏 Flashcards") and notes:
        flash = ask_openai("Create detailed Q&A flashcards", notes)
        st.success(flash)
        st.download_button("⬇️ Download Flashcards", save_as_pdf(flash,"Flashcards"), file_name="flashcards.pdf")

with col3:
    if st.button("🎯 Quizzes") and notes:
        quiz = ask_openai("Generate adaptive MCQs with answers", notes)
        st.success(quiz)
        st.download_button("⬇️ Download Quiz", save_as_pdf(quiz,"Quiz"), file_name="quiz.pdf")

with col4:
    if st.button("📝 Mock Exams") and notes:
        exam = ask_openai("Generate a full mock exam with MCQs, short and long Qs, with marks", notes)
        st.success(exam)
        st.download_button("⬇️ Download Mock Exam", save_as_pdf(exam,"MockExam"), file_name="mock_exam.pdf")

with col5:
    st.markdown('<div id="chat-launch" class="chat-button">💬 Ask Zentra</div>', unsafe_allow_html=True)

# ============== CHAT POPUP ==============
if "chat_open" not in st.session_state:
    st.session_state.chat_open = False

if st.session_state.chat_open or st.button("💬 Open Chat"):
    st.subheader("💬 Ask Zentra (Study Tutor)")
    user_q = st.text_input("Ask a question:")
    if user_q:
        ans = ask_openai("You are Zentra, a study tutor.", user_q)
        st.info(ans)
