import streamlit as st
from openai import OpenAI
import os

# 🔑 API key from Streamlit secrets (not hardcoded)
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
MODEL = "gpt-4o-mini"

st.set_page_config(page_title="⚡ Zentra — AI Study Buddy", layout="wide")
st.title("⚡ Zentra — Your AI Study Buddy")
st.caption("Upload notes → Summaries, Flashcards, Quiz, Mock Exam.")

notes = st.text_area("Paste your notes here:", height=200)

if st.button("Summarize"):
    with st.spinner("Summarizing..."):
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "Summarize clearly in 5–8 bullet points."},
                {"role": "user", "content": notes}
            ]
        )
        st.markdown(resp.choices[0].message.content)

if st.button("Flashcards"):
    with st.spinner("Generating flashcards..."):
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "Generate 5 flashcards in Q&A format."},
                {"role": "user", "content": notes}
            ]
        )
        st.markdown(resp.choices[0].message.content)

if st.button("Quiz"):
    with st.spinner("Making quiz..."):
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "Create 5 MCQs with options. At the end, provide correct answers separately."},
                {"role": "user", "content": notes}
            ]
        )
        st.markdown(resp.choices[0].message.content)

if st.button("Mock Exam"):
    with st.spinner("Building mock exam..."):
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "Create 3 MCQs, 2 short answers, 1 essay. Provide answers + feedback."},
                {"role": "user", "content": notes}
            ]
        )
        st.markdown(resp.choices[0].message.content)
