import streamlit as st
import json, os, tempfile, streamlit as st

# Load Google Service Account credentials from Streamlit Secrets
if "service_account" in st.secrets:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp:
        tmp.write(json.dumps(dict(st.secrets["service_account"])).encode())
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = tmp.name

from gsheets_client import get_worksheet_and_ensure_headers
import pandas as pd
from schema_loader import load_schema_from_excels
from gsheets_client import get_worksheet_and_ensure_headers
from excel_writer import build_row
st.set_page_config(page_title="Driver Emotion Labeler — Google Sheets", layout="wide")
st.title("Driver Emotion Labeler — Google Sheets")
with st.sidebar:
    st.header("Schema & Storage")
    features_path = st.text_input("Features.xlsx path", value="Features.xlsx")
    example_path = st.text_input("Example_of_Video_Labelling.xlsx path", value="Example_of_Video_Labelling.xlsx")
    if st.button("Load schema"):
        try:
            schema = load_schema_from_excels(features_path, example_path)
            st.session_state.schema = schema
            st.success(f"Loaded schema. Columns: {len(schema['columns'])}")
        except Exception as e:
            st.error(str(e))
if "schema" not in st.session_state:
    st.warning("Load the schema from your Excel files on the left."); st.stop()
schema = st.session_state.schema
try:
    ws = get_worksheet_and_ensure_headers(schema["columns"])
    st.success("Connected to Google Sheets and ensured headers (migration applied if needed).")
except Exception as e:
    st.error(f"Google Sheets setup failed: {e}"); st.stop()
if "files" not in st.session_state: st.session_state.files = []
if "idx" not in st.session_state: st.session_state.idx = 0
if "skipped" not in st.session_state: st.session_state.skipped = set()
st.header("Upload Videos")
uploads = st.file_uploader("Upload one or more .mp4 files", type=["mp4"], accept_multiple_files=True)
if uploads: st.session_state.files, st.session_state.idx = uploads, 0
total = len(st.session_state.files); current = st.session_state.idx + 1 if total>0 else 0
saved_rows = max(len(ws.get_all_values()) - 1, 0)
st.write(f"**Progress:** {current}/{total} | **Saved rows:** {saved_rows} | **Skipped:** {len(st.session_state.skipped)}")
if total == 0: st.info("Upload at least one .mp4 to begin labeling."); st.stop()
file = st.session_state.files[st.session_state.idx]
st.subheader(f"Now labeling: {file.name}")
st.video(file)
default_id = file.name[:-4] if file.name.lower().endswith(".mp4") else file.name
video_id = st.text_input("video_id", value=default_id)
st.subheader("Labels")
form_vals = {}
for col in schema["columns"]:
    if col == "timestamp_utc": continue
    opts = [""] + schema["choices"].get(col, [])
    if col == "video_id":
        default = video_id or ""
        if default and default not in opts: opts.insert(1, default)
        form_vals[col] = st.selectbox(col, options=opts, index=opts.index(default) if default in opts else 0, key=f"sb_{col}")
    else:
        form_vals[col] = st.selectbox(col, options=opts, index=0, key=f"sb_{col}")
uncertain = st.checkbox("Mark as uncertain")
def next_clip():
    if st.session_state.idx < len(st.session_state.files) - 1: st.session_state.idx += 1
def prev_clip():
    if st.session_state.idx > 0: st.session_state.idx -= 1
col1, col2, col3, col4 = st.columns(4)
with col1:
    if st.button("⟵ Previous", use_container_width=True): prev_clip()
with col2:
    if st.button("Skip", use_container_width=True):
        st.session_state.skipped.add(file.name); next_clip()
with col3:
    if st.button("Submit & Next", use_container_width=True):
        if not video_id: st.error("Please set a video_id before submitting.")
        else:
            if uncertain:
                if "label_confidence" in schema["columns"]:
                    form_vals["label_confidence"] = "uncertain"
                elif "notes" in schema["columns"]:
                    existing = form_vals.get("notes", ""); form_vals["notes"] = (existing + "; " if existing else "") + "uncertain"
            try:
                form_vals["video_id"] = video_id
                row = build_row(schema["columns"], form_vals)
                ws.append_row(row, value_input_option="USER_ENTERED")
                st.success("Saved to Google Sheets ✅"); next_clip()
            except Exception as e:
                st.error(f"Append failed: {e}")
with col4:
    if st.button("⟶ Next", use_container_width=True): next_clip()
st.caption("Fix applied: we now use append_row and keep ample grid size to avoid 'Range exceeds grid limits'.")
