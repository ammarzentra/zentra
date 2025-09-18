from openai import OpenAI

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

try:
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role":"user","content":"Say 'Zentra connected!'"}]
    )
    st.success("OpenAI test: " + resp.choices[0].message.content)
except Exception as e:
    st.error(f"OpenAI error: {e}")
