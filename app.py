import streamlit as st
from openai import OpenAI
import fitz  # PyMuPDF
import docx
from fpdf import FPDF
import io

# ===================== SETUP =====================
st.set_page_config(page_title="⚡ Zentra — AI Study Buddy", layout="wide")
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
MODEL = "gpt-4o-mini"

# ===================== CUSTOM CSS =====================
st.markdown("""
    <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}

        .zentra-header {
            background: linear-gradient(90deg, #6a11cb, #2575fc);
            padding: 25px;
            border-radius: 12px;
            text-align: center;
            color: white;
        }
        .zentra-header h1 { font-size: 38px; margin: 0; }
        .zentra-header p { font-size: 16px; margin-top: 8px; opacity: 0.9; }
        .stButton>button { width: 100%; border-radius: 8px; font-weight: 600; padding: 10px; }
        .tooltip { font-size: 13px; color: #aaa; margin-top: -8px; margin-bottom: 12px; }
    </style>
""", unsafe_allow_html=True)

# ===================== HEADER =====================
st.markdown("""
    <div class="zentra-header">
        <h1>⚡ Zentra — AI Study Buddy</h1>
        <p>Upload notes → Get summaries, flashcards, quizzes & exams. Plus your own AI tutor.</p>
    </div>
""", unsafe_allow_html=True)

# ===================== SIDEBAR =====================
st.sidebar.title("📌 About Zentra")
st.sidebar.info("""
Zentra helps students learn smarter:
- 📑 Summaries → exam-ready notes  
- 🃏 Flashcards → spaced recall  
- 🎯 Quizzes → adaptive MCQs  
- 📝 Mock Exams → multi-format tests with marking  
- 🤖 Ask Zentra → your AI tutor  
""")

st.sidebar.markdown("---")
st.sidebar.subheader("📊 Progress")
st.sidebar.text("Quizzes: 0")
st.sidebar.text("Mock Exams: 0")

# ===================== FILE UPLOAD =====================
st.subheader("📂 Upload your notes (PDF / DOCX / TXT) or paste below")
uploaded_file = st.file_uploader("Upload file", type=["pdf", "docx", "txt"])
notes_text = st.text_area("Or paste your notes here…", height=150)

def extract_text(file):
    text = ""
    if file.name.endswith(".pdf"):
        pdf = fitz.open(stream=file.read(), filetype="pdf")
        for page in pdf:
            text += page.get_text()
    elif file.name.endswith(".docx"):
        doc = docx.Document(file)
        for para in doc.paragraphs:
            text += para.text + "\n"
    else:
        text = file.read().decode("utf-8")
    return text

if uploaded_file:
    notes_text = extract_text(uploaded_file)

# ===================== HELPERS =====================
def ask_openai(prompt):
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "You are Zentra, a professional AI study assistant."},
            {"role": "user", "content": prompt}
        ]
    )
    return resp.choices[0].message.content

def save_as_pdf(content, title="Zentra Output"):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(0, 10, content)
    return pdf.output(dest="S").encode("latin-1")

# ===================== TOOLS =====================
st.subheader("✨ Study Tools")

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    if st.button("📑 Summaries") and notes_text.strip():
        summary = ask_openai(f"Summarize clearly in exam-style bullet points:\n{text}")
        st.success("✅ Summary Generated")
        st.write(summary)
        st.download_button("⬇️ Download PDF", save_as_pdf(summary), file_name="summary.pdf")

with col2:
    if st.button("🃏 Flashcards") and notes_text.strip():
        cards = ask_openai(f"Make flashcards (Q front, A back). Cover all key topics:\n{notes_text}")
        st.success("✅ Flashcards Generated")
        st.write(cards)
        st.download_button("⬇️ Download PDF", save_as_pdf(cards), file_name="flashcards.pdf")

with col3:
    if st.button("🎯 Quizzes") and notes_text.strip():
        quiz = ask_openai(f"Generate adaptive MCQs (3-4 options each + answers):\n{notes_text}")
        st.success("✅ Quiz Generated")
        st.write(quiz)
        st.download_button("⬇️ Download PDF", save_as_pdf(quiz), file_name="quiz.pdf")

with col4:
    if st.button("📝 Mock Exams") and notes_text.strip():
        exam = ask_openai(f"Create a full mock exam with MCQs, short answers, and essay Qs. Mark it:\n{notes_text}")
        st.success("✅ Mock Exam Generated")
        st.write(exam)
        st.download_button("⬇️ Download PDF", save_as_pdf(exam), file_name="mock_exam.pdf")

with col5:
    if st.button("💬 Ask Zentra"):
        st.session_state["chat_open"] = True

# ===================== ASK ZENTRA CHAT =====================
if "chat_open" in st.session_state and st.session_state["chat_open"]:
    st.markdown("### 💬 Ask Zentra")
    user_q = st.text_input("Type your question:")
    if st.button("Send") and user_q:
        ans = ask_openai(user_q)
        st.markdown(f"**Zentra:** {ans}")
