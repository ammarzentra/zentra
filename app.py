import streamlit as st
from openai import OpenAI
from PyPDF2 import PdfReader
import docx
import base64

# Initialize OpenAI client
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# -------------- APP CONFIG --------------
st.set_page_config(page_title="⚡ Zentra — AI Study Buddy", layout="wide")

# Custom CSS to polish UI + hide Streamlit footer
st.markdown("""
    <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}

        /* Gradient Hero Section */
        .hero {
            background: linear-gradient(90deg, #6a11cb, #2575fc);
            color: white;
            padding: 30px;
            border-radius: 12px;
            text-align: center;
            margin-bottom: 20px;
        }
        .hero h1 {
            font-size: 36px;
            font-weight: bold;
        }
        .hero p {
            font-size: 18px;
            opacity: 0.9;
        }

        /* Floating Ask Zentra button (top right) */
        .ask-button {
            position: fixed;
            top: 20px;
            right: 30px;
            background: #ffb703;
            color: black;
            padding: 10px 20px;
            border-radius: 25px;
            font-weight: bold;
            cursor: pointer;
            z-index: 1000;
        }
        .chatbox {
            position: fixed;
            top: 70px;
            right: 30px;
            width: 300px;
            height: 400px;
            background: white;
            border-radius: 12px;
            box-shadow: 0px 4px 20px rgba(0,0,0,0.2);
            display: none;
            flex-direction: column;
            overflow: hidden;
            z-index: 1001;
        }
        .chat-messages {
            flex: 1;
            padding: 10px;
            overflow-y: auto;
            font-size: 14px;
        }
        .chat-input {
            border-top: 1px solid #ddd;
            padding: 8px;
        }
    </style>

    <script>
        function toggleChat() {
            var chat = document.getElementById("zentra-chat");
            if (chat.style.display === "none") {
                chat.style.display = "flex";
            } else {
                chat.style.display = "none";
            }
        }
    </script>
""", unsafe_allow_html=True)

# -------------- HERO SECTION --------------
st.markdown("""
    <div class="hero">
        <h1>⚡ Zentra — AI Study Buddy</h1>
        <p>Smarter notes → better recall → higher scores.</p>
        <div style="margin-top:15px;">
            <button disabled style="margin:5px;padding:10px 20px;border-radius:8px;">📑 Summaries</button>
            <button disabled style="margin:5px;padding:10px 20px;border-radius:8px;">🗂 Flashcards</button>
            <button disabled style="margin:5px;padding:10px 20px;border-radius:8px;">🎯 Quizzes</button>
            <button disabled style="margin:5px;padding:10px 20px;border-radius:8px;">📝 Mock Exams</button>
        </div>
    </div>
""", unsafe_allow_html=True)

# Floating Ask Zentra Button
st.markdown('<div class="ask-button" onclick="toggleChat()">💬 Ask Zentra</div>', unsafe_allow_html=True)

# Chatbox HTML
st.markdown("""
    <div id="zentra-chat" class="chatbox">
        <div class="chat-messages" id="chat-messages">
            <p><b>Zentra:</b> Hi 👋 I’m your AI tutor. Ask me anything about your notes!</p>
        </div>
        <div class="chat-input">
            <input type="text" id="chat-input" placeholder="Type your question..." style="width:80%">
            <button onclick="document.getElementById('chat-messages').innerHTML += '<p><b>You:</b> ' + document.getElementById('chat-input').value + '</p>';">Send</button>
        </div>
    </div>
""", unsafe_allow_html=True)

# -------------- SIDEBAR --------------
with st.sidebar:
    st.subheader("📘 About Zentra")
    st.write("Zentra accelerates learning with clean summaries, active-recall flashcards, adaptive quizzes, mock exams, and a built-in AI tutor.")

    st.subheader("🛠 What each tool does")
    st.write("📑 **Summaries** → exam-ready notes")
    st.write("🗂 **Flashcards** → spaced repetition questions")
    st.write("🎯 **Quizzes** → MCQs with explanations")
    st.write("📝 **Mock Exams** → multi-section exam with marking")
    st.write("💬 **Ask Zentra** → your AI tutor/chat")

    st.subheader("⚡ Disclaimer")
    st.write("Zentra supports your study journey. Always verify before exams.")

# -------------- MAIN APP --------------
st.subheader("📂 Upload your notes (PDF / DOCX / TXT)")
uploaded_file = st.file_uploader("Upload file", type=["pdf", "docx", "txt"])

def extract_text(file):
    if file.name.endswith(".pdf"):
        pdf = PdfReader(file)
        return " ".join([page.extract_text() for page in pdf.pages if page.extract_text()])
    elif file.name.endswith(".docx"):
        doc = docx.Document(file)
        return " ".join([para.text for para in doc.paragraphs])
    elif file.name.endswith(".txt"):
        return file.read().decode("utf-8")
    else:
        return ""

if uploaded_file:
    text = extract_text(uploaded_file)

    st.subheader("✨ Study Tools")

    if st.button("📑 Summarize Notes"):
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "Summarize the notes into exam-ready bullet points."},
                      {"role": "user", "content": text}]
        )
        summary = response.choices[0].message.content
        st.write(summary)

    if st.button("🗂 Generate Flashcards"):
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "Make flashcards: Question → Answer format."},
                      {"role": "user", "content": text}]
        )
        st.write(response.choices[0].message.content)

    if st.button("🎯 Generate Quiz"):
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "Generate 10 multiple-choice questions with 4 options and correct answer marked."},
                      {"role": "user", "content": text}]
        )
        st.write(response.choices[0].message.content)

    if st.button("📝 Generate Mock Exam"):
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "Create a professional mock exam with MCQs, short answers, and essay questions, with marks distribution."},
                      {"role": "user", "content": text}]
        )
        st.write(response.choices[0].message.content)
