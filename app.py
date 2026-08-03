import streamlit as st
import subprocess
from pathlib import Path

st.set_page_config(page_title="namescheck", layout="wide")

st.markdown("""
<style>
body { font-family: monospace; }
h1 { font-size: 24px; font-weight: normal; letter-spacing: 2px; }
h2 { font-size: 16px; font-weight: normal; margin-top: 2em; }
.stButton button { font-family: monospace; }
.stTextArea textarea { font-family: monospace; font-size: 12px; }
</style>
""", unsafe_allow_html=True)

st.title("namescheck")
st.write("Find startup names with both .com and .ai domains available")

col1, col2 = st.columns([2, 1])

with col1:
    uploaded_file = st.file_uploader("Upload startup names (one per line)", type="txt")
    if uploaded_file:
        Path("startup_names.txt").write_text(uploaded_file.getvalue().decode())
        st.write("uploaded")

with col2:
    max_retries = st.number_input("Max retries", min_value=1, value=4)
    concurrency = st.number_input("Concurrency", min_value=1, value=100)

if st.button("start scan"):
    with st.spinner("scanning..."):
        result = subprocess.run(
            ["python", "scanner.py", "--max-retries", str(max_retries), "--concurrency", str(concurrency)],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            st.write(f"error: {result.stderr}")
        else:
            st.write("scan complete")

available_file = Path("available_both.txt")
if available_file.exists():
    results = available_file.read_text().strip().split("\n")
    results = [r for r in results if r]

    st.divider()
    st.write(f"Results ({len(results)} available)")

    col1, col2 = st.columns([3, 1])
    with col1:
        st.text_area("", "\n".join(results), height=300, disabled=True, label_visibility="collapsed")
    with col2:
        st.download_button(
            "download",
            "\n".join(results),
            file_name="available_both.txt",
            mime="text/plain",
            use_container_width=True
        )

progress_file = Path("startup_names.progress")
errors_file = Path("startup_names.errors")

if progress_file.exists() or errors_file.exists():
    st.divider()
    col1, col2 = st.columns(2)

    if progress_file.exists():
        processed = len(progress_file.read_text().strip().split("\n"))
        with col1:
            st.write(f"processed: {processed}")

    if errors_file.exists():
        errors = len(errors_file.read_text().strip().split("\n"))
        with col2:
            st.write(f"errors: {errors}")
