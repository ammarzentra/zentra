import streamlit as st
from openai import OpenAI
import fitz  # PyMuPDF
import docx
from fpdf import FPDF

# ===================== SETUP =====================
st.set_page_config(page_title="⚡ Zentra — AI Study Buddy", layout="wide")
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
MODEL = "gpt-4o-mini"

# ===================== CUSTOM CSS =====================
st.markdown("""
    <style>
        #MainMenu, footer, header {visibility: hidden;}
        .zentra-header {
            background: linear-gradient(90deg, #6a11cb, #2575fc);
            padding: 25px;
            border-radius: 12px;
            text-align: center;
            color: white;
        }
        .zentra-header h1 { font-size: 40px; margin: 0; font-weight: bold; }
        .zentra-header p { font-size: 16px; margin-top: 8px; opacity: 0.9; }
        .stButton>button { width: 100%; border-radius: 8px; font-weight: 600; padding: 10px; }
        .chatbox {
            position: fixed; bottom: 20px; right: 20px;
            width: 350px; height: 450px;
            background: #1e1e2f; border-radius: 10px;
            padding: 12px; overflow-y: auto;
            color: white; font-size: 14px;
        }
    </style>
""", unsafe_allow_html=True)

# ===================== HEADER =====================
st.markdown("""
    <div class="zentra-header">
        <h1>⚡ Zentra — AI Study Buddy</h1>
        <p>Smarter notes → better recall → higher scores.</p>
    </div>
""", unsafe_allow_html=True)

# ===================== SIDEBAR =====================
st.sidebar.title("📌 About Zentra")
st.sidebar.success("""
**How Zentra Works:**  
Upload notes → Generate summaries, flashcards, quizzes, and mock exams.  
Ask Zentra anytime like a study tutor.  

**Why Students Love It:**  
✅ Faster revision  
✅ Adaptive practice  
✅ Smart AI explanations  
""")

st.sidebar.markdown("### 🛠 What each tool does")
st.sidebar.info("""
📑 **Summaries** → Exam-ready notes  
🃏 **Flashcards** → Active recall Q&A  
🎯 **Quizzes** → Adaptive MCQs with answers  
📝 **Mock Exams** → Full-length exam with marking  
💬 **Ask Zentra** → Chat with AI tutor  
""")

st.sidebar.markdown("---")
st.sidebar.markdown("### ⚠ Disclaimer")
st.sidebar.warning("Zentra is an AI-powered assistant. Always review results before relying on them for exams.")

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

# ===================== WELCOME =====================
if "first_time" not in st.session_state:
    st.session_state["first_time"] = True

if st.session_state["first_time"]:
    st.info("👋 Welcome to Zentra! Upload your notes and let AI transform them into study material.")
    st.session_state["first_time"] = False

# ===================== TOOLS =====================
st.subheader("✨ Study Tools")

col1, col2, col3, col4 = st.columns(4)

with col1:
    if st.button("📑 Summaries") and notes_text.strip():
        summary = ask_openai(f"Summarize in exam-style bullet points:\n{notes_text}")
        st.success("✅ Summary Generated")
        st.write(summary)
        st.download_button("⬇️ Download PDF", save_as_pdf(summary), file_name="summary.pdf")

with col2:
    if st.button("🃏 Flashcards") and notes_text.strip():
        cards = ask_openai(f"Make 15 flashcards (Q front, A back):\n{notes_text}")
        st.success("✅ Flashcards Generated")
        st.write(cards)
        st.download_button("⬇️ Download PDF", save_as_pdf(cards), file_name="flashcards.pdf")

with col3:
    if st.button("🎯 Quizzes") and notes_text.strip():
        quiz = ask_openai(f"Generate adaptive MCQs with answers and explanations:\n{notes_text}")
        st.success("✅ Quiz Generated")
        st.write(quiz)
        st.download_button("⬇️ Download PDF", save_as_pdf(quiz), file_name="quiz.pdf")

with col4:
    if st.button("📝 Mock Exams") and notes_text.strip():
        exam = ask_openai(f"Create a professional mock exam (MCQs + short answer + essay + marking):\n{notes_text}")
        st.success("✅ Mock Exam Generated")
        st.write(exam)
        st.download_button("⬇️ Download PDF", save_as_pdf(exam), file_name="mock_exam.pdf")

# ===================== ASK ZENTRA CHATBOX =====================
if "chat" not in st.session_state:
    st.session_state["chat"] = []

st.markdown("## 💬 Ask Zentra (Tutor)")
user_q = st.text_input("Ask anything about your notes or subject:")
if st.button("Send Question") and user_q:
    ans = ask_openai(user_q)
    st.session_state["chat"].append(("You", user_q))
    st.session_state["chat"].append(("Zentra", ans))

if st.session_state["chat"]:
    with st.container():
        for sender, msg in st.session_state["chat"]:
            if sender == "You":
                st.markdown(f"**🧑 You:** {msg}")
            else:
                st.markdown(f"**🤖 Zentra:** {msg}")
