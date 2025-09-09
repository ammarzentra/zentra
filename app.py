import streamlit as st
from openai import OpenAI
import os
from fpdf import FPDF

# 🔑 API key (from Streamlit secrets)
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
MODEL = "gpt-4o-mini"

# 🎨 Page setup
st.set_page_config(page_title="⚡ Zentra – AI Study Buddy", page_icon="⚡", layout="wide")

# 💜 Custom CSS styling
st.markdown("""
<style>
    .main {background-color: #0e0e0e;}
    .stTextArea textarea {background-color: #1a1a1a; color: white;}
    .zentra-card {
        background-color: #161616;
        padding: 20px;
        border-radius: 15px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.5);
        margin-bottom: 20px;
    }
    .zentra-btn {
        border-radius: 12px;
        font-size: 16px;
        font-weight: bold;
        padding: 10px 20px;
    }
</style>
""", unsafe_allow_html=True)

# 🔥 Sidebar
st.sidebar.title("⚡ Zentra")
st.sidebar.markdown("Your AI-powered Study Buddy 📚")
st.sidebar.info("Disclaimer: Zentra is an AI assistant. Always verify before exams.")

# ✍️ Notes input
st.markdown("<div class='zentra-card'>", unsafe_allow_html=True)
notes = st.text_area("📘 Paste your notes here:", height=200, placeholder="Paste textbook or PDF notes...")
st.markdown("</div>", unsafe_allow_html=True)

# 📥 Storage for results
if "results" not in st.session_state:
    st.session_state.results = ""

# 🛠 Helper function
def ask_ai(prompt):
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "You are Zentra, an elite AI study buddy."},
            {"role": "user", "content": prompt}
        ]
    )
    return resp.choices[0].message.content

# 📌 Action Buttons
col1, col2, col3, col4 = st.columns(4)

with col1:
    if st.button("✨ Summarize", use_container_width=True):
        if notes.strip():
            with st.spinner("Zentra is summarizing..."):
                summary = ask_ai(f"Summarize the following notes into 6–8 bullet points:\n\n{notes}")
                st.success("📘 Summary")
                st.write(summary)
                st.session_state.results += "\n\nSUMMARY:\n" + summary
        else:
            st.warning("Please enter notes first.")

with col2:
    if st.button("🔑 Flashcards", use_container_width=True):
        if notes.strip():
            with st.spinner("Generating flashcards..."):
                flashcards = ask_ai(f"Turn these notes into 10 flashcards (Q&A format):\n\n{notes}")
                st.success("🔑 Flashcards")
                st.write(flashcards)
                st.session_state.results += "\n\nFLASHCARDS:\n" + flashcards
        else:
            st.warning("Please enter notes first.")

with col3:
    if st.button("🎯 Quiz", use_container_width=True):
        if notes.strip():
            with st.spinner("Creating quiz..."):
                quiz = ask_ai(f"Create 5 multiple choice questions from these notes. "
                              f"Show options A-D, but only reveal answers + explanations AFTER all 5 questions.")
                st.success("🎯 Quiz")
                st.write(quiz)
                st.session_state.results += "\n\nQUIZ:\n" + quiz
        else:
            st.warning("Please enter notes first.")

with col4:
    if st.button("📝 Mock Exam", use_container_width=True):
        if notes.strip():
            with st.spinner("Preparing exam..."):
                exam = ask_ai(f"Generate a 10-question mock exam with answers hidden until the end. "
                              f"At the end, provide a score breakdown and personalized study tips.")
                st.success("📝 Mock Exam")
                st.write(exam)
                st.session_state.results += "\n\nMOCK EXAM:\n" + exam
        else:
            st.warning("Please enter notes first.")

# 📥 Download Results as PDF
if st.session_state.results:
    if st.button("📥 Download Results as PDF"):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        for line in st.session_state.results.split("\n"):
            pdf.multi_cell(0, 10, line)
        pdf.output("zentra_results.pdf")
        with open("zentra_results.pdf", "rb") as f:
            st.download_button("Download PDF", f, "zentra_results.pdf")

