import streamlit as st
from openai import OpenAI
import os

# 🔑 API key (loaded from Streamlit secrets)
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
MODEL = "gpt-4o-mini"

# 🌟 Page setup
st.set_page_config(
    page_title="⚡ Zentra — AI Study Buddy",
    page_icon="⚡",
    layout="wide"
)

# 🎨 Custom CSS for sleek design
st.markdown("""
    <style>
        .main { background-color: #0e1117; color: #fff; }
        .stTextArea textarea { background: #1a1d29; color: #fff; border-radius: 10px; }
        .stButton button {
            background: linear-gradient(90deg, #7b2ff7, #f107a3);
            color: white;
            border: none;
            border-radius: 12px;
            padding: 0.6em 1.2em;
            font-weight: bold;
            transition: 0.3s;
        }
        .stButton button:hover {
            transform: scale(1.05);
            box-shadow: 0px 0px 15px rgba(241,7,163,0.6);
        }
        .result-card {
            background: #1a1d29;
            padding: 20px;
            border-radius: 12px;
            margin: 15px 0;
            box-shadow: 0px 0px 8px rgba(255,255,255,0.1);
        }
    </style>
""", unsafe_allow_html=True)

# 🏷️ Sidebar
st.sidebar.title("⚡ Zentra")
st.sidebar.markdown("Your AI-powered Study Buddy 📚")
st.sidebar.info("""
**What Zentra Does**
- Summarizes notes into clear bullet points  
- Creates flashcards for quick revision  
- Generates quizzes for practice  
- Builds mock exams with scoring  
""")
st.sidebar.success("Disclaimer: Zentra is an AI study assistant. Always review before exams.")

# 📥 Notes input
notes = st.text_area("📥 Paste your notes here:", placeholder="Paste textbook or notes...", height=200)

# ✅ Summarize
if st.button("✨ Summarize"):
    if not notes.strip():
        st.warning("Please enter some notes first.")
    else:
        with st.spinner("Summarizing..."):
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": "Summarize the notes in 5-7 clear bullet points."},
                    {"role": "user", "content": notes}
                ]
            )
            st.markdown(f"<div class='result-card'>{resp.choices[0].message.content}</div>", unsafe_allow_html=True)

# ✅ Flashcards
if st.button("🔑 Flashcards"):
    if not notes.strip():
        st.warning("Please enter some notes first.")
    else:
        with st.spinner("Creating flashcards..."):
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": "Turn the notes into Q&A flashcards. Format: Q: ... A: ..."},
                    {"role": "user", "content": notes}
                ]
            )
            st.markdown(f"<div class='result-card'>{resp.choices[0].message.content}</div>", unsafe_allow_html=True)

# ✅ Quiz
if st.button("🎯 Quiz"):
    if not notes.strip():
        st.warning("Please enter some notes first.")
    else:
        with st.spinner("Generating quiz..."):
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": "Generate 5 multiple-choice questions. Don’t show answers until the end."},
                    {"role": "user", "content": notes}
                ]
            )
            st.markdown(f"<div class='result-card'>{resp.choices[0].message.content}</div>", unsafe_allow_html=True)

# ✅ Mock Exam
if st.button("📊 Mock Exam"):
    if not notes.strip():
        st.warning("Please enter some notes first.")
    else:
        with st.spinner("Building mock exam..."):
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": "Create a 10-question mock exam. At the end, provide the correct answers and score breakdown."},
                    {"role": "user", "content": notes}
                ]
            )
            st.markdown(f"<div class='result-card'>{resp.choices[0].message.content}</div>", unsafe_allow_html=True)



       
