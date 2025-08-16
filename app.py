import os, io, json, tempfile
from typing import List, Dict
import streamlit as st
from dotenv import load_dotenv

from schema_loader import load_schema_from_excels
from excel_writer import build_row

# -----------------------------
# Auth: Cloud (st.secrets) or Local (.env)
# -----------------------------
def _setup_auth_env():
    load_dotenv()
    # Prefer Streamlit secrets (Cloud)
    try:
        if "service_account" in st.secrets:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp:
                tmp.write(json.dumps(dict(st.secrets["service_account"])).encode())
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = tmp.name
    except Exception:
        pass

_setup_auth_env()

# Lazy import after auth env set
from gsheets_client import get_worksheet_and_ensure_headers

st.set_page_config(page_title="Driver Emotion Labeler — Google Sheets", layout="wide")
st.title("Driver Emotion Labeler — Google Sheets")

# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------
def _normalize_drive_link(url: str) -> str:
    """
    Accepts a Google Drive 'share' link and returns a streamable URL.
    Requires the file to be shared as 'Anyone with the link'.
    Formats handled:
      https://drive.google.com/file/d/<FILE_ID>/view?usp=...
      https://drive.google.com/open?id=<FILE_ID>
      https://drive.google.com/uc?id=<FILE_ID>&export=download
    """
    url = (url or "").strip()
    if not url:
        return url
    if "drive.google.com" not in url:
        return url
    file_id = None
    # /file/d/<ID>/
    if "/file/d/" in url:
        try:
            file_id = url.split("/file/d/")[1].split("/")[0]
        except Exception:
            file_id = None
    # open?id=<ID>
    if not file_id and "open?id=" in url:
        try:
            file_id = url.split("open?id=")[1].split("&")[0]
        except Exception:
            file_id = None
    # id=<ID>
    if not file_id and "id=" in url:
        try:
            file_id = url.split("id=")[1].split("&")[0]
        except Exception:
            file_id = None
    if file_id:
        return f"https://drive.google.com/uc?export=download&id={file_id}"
    return url

def _bytes_from_uploads(uploads) -> List[Dict[str, bytes]]:
    return [{"name": f.name, "data": f.getvalue()} for f in uploads]

# -----------------------------------------------------------------------------
# Tabs: Setup / Label
# -----------------------------------------------------------------------------
tab_setup, tab_label = st.tabs(["🧰 Setup", "🎬 Label"])

# --------------------------------------------------------------------------------
# 🧰 SETUP TAB
# --------------------------------------------------------------------------------
with tab_setup:
    st.subheader("Project Settings")

    # Initialize settings dict
    if "settings" not in st.session_state:
        st.session_state.settings = {
            "SPREADSHEET_ID": os.getenv("SPREADSHEET_ID", ""),
            "WORKSHEET_NAME": os.getenv("WORKSHEET_NAME", "labels_log"),
        }

    with st.form("setup_form"):
        st.markdown("**Google Sheet**")
        SPREADSHEET_ID = st.text_input(
            "Spreadsheet ID",
            value=st.session_state.settings.get("SPREADSHEET_ID", ""),
            help="The long ID in the Google Sheet URL between /d/ and /edit",
        )
        WORKSHEET_NAME = st.text_input(
            "Worksheet name",
            value=st.session_state.settings.get("WORKSHEET_NAME", "labels_log"),
        )

        st.markdown("---")
        st.markdown("**Schema files** (upload or keep defaults from repo)")
        features_file = st.file_uploader("Features.xlsx", type=["xlsx"], key="features_up")
        example_file = st.file_uploader("Example_of_Video_Labelling.xlsx", type=["xlsx"], key="example_up")

        st.markdown("---")
        st.markdown("**Video source**")
        source = st.radio(
            "Choose a source",
            options=["Upload files", "Paste URLs (one per line)"],
            index=0,
            horizontal=True,
        )

        url_text = ""
        uploads = None
        if source == "Upload files":
            uploads = st.file_uploader(
                "Upload one or more .mp4 files (they stay local/client-side)",
                type=["mp4"], accept_multiple_files=True, key="video_up"
            )
        else:
            url_text = st.text_area(
                "Video URLs (HTTP/HTTPS). For Google Drive links, ensure 'Anyone with the link' and paste the share links (one per line).",
                placeholder="https://drive.google.com/file/d/FILE_ID/view?usp=sharing\nhttps://example.com/video2.mp4\n...",
                height=120,
            )

        submitted = st.form_submit_button("Save setup")
        if submitted:
            # Persist settings
            st.session_state.settings["SPREADSHEET_ID"] = SPREADSHEET_ID.strip()
            st.session_state.settings["WORKSHEET_NAME"] = WORKSHEET_NAME.strip()

            # Save schema into session as bytes (or note file paths if not uploaded)
            if "schema_bufs" not in st.session_state:
                st.session_state.schema_bufs = {"features": None, "example": None}

            st.session_state.schema_bufs["features"] = features_file.getvalue() if features_file else None
            st.session_state.schema_bufs["example"] = example_file.getvalue() if example_file else None

            # Build the video list (bytes or URLs)
            if "files" not in st.session_state: st.session_state.files = []
            if "use_urls" not in st.session_state: st.session_state.use_urls = False
            if "idx" not in st.session_state: st.session_state.idx = 0

            if source == "Upload files":
                st.session_state.use_urls = False
                st.session_state.files = _bytes_from_uploads(uploads) if uploads else []
            else:
                st.session_state.use_urls = True
                urls = [u.strip() for u in (url_text or "").splitlines() if u.strip()]
                # normalize Drive links to streamable
                urls = [_normalize_drive_link(u) for u in urls]
                st.session_state.files = [{"name": f"URL {i+1}", "url": u} for i, u in enumerate(urls)]

            st.session_state.idx = 0
            st.success("Setup saved. Switch to the **Label** tab to start.")
            st.query_params.update(tab="label")

# --------------------------------------------------------------------------------
# 🎬 LABEL TAB
# --------------------------------------------------------------------------------
with tab_label:
    # Quick guardrails
    if "settings" not in st.session_state or not st.session_state.settings.get("SPREADSHEET_ID"):
        st.warning("Open the **Setup** tab first and save your Spreadsheet ID.")
        st.stop()

    # Load schema (from uploaded bytes or from default files on disk)
    # Cache in session so we don’t re-read on every rerun
    if "schema" not in st.session_state:
        try:
            if st.session_state.get("schema_bufs", {}).get("features") or st.session_state.get("schema_bufs", {}).get("example"):
                # Read from uploaded buffers
                import pandas as pd
                from io import BytesIO
                features_buf = st.session_state.schema_bufs.get("features")
                example_buf = st.session_state.schema_bufs.get("example")
                # For schema_loader, we need temp files or we can adapt loader; simplest: write temp files
                tmp_dir = tempfile.mkdtemp()
                f_path = os.path.join(tmp_dir, "Features.xlsx")
                e_path = os.path.join(tmp_dir, "Example_of_Video_Labelling.xlsx")
                if features_buf:
                    with open(f_path, "wb") as f:
                        f.write(features_buf)
                if example_buf:
                    with open(e_path, "wb") as f:
                        f.write(example_buf)
                schema = load_schema_from_excels(
                    f_path if features_buf else "Features.xlsx",
                    e_path if example_buf else "Example_of_Video_Labelling.xlsx"
                )
            else:
                # Fall back to repo files
                schema = load_schema_from_excels("Features.xlsx", "Example_of_Video_Labelling.xlsx")

            # Ensure `video_id` first (safety)
            if "video_id" in schema["columns"]:
                schema["columns"] = ["video_id"] + [c for c in schema["columns"] if c != "video_id"]
            st.session_state.schema = schema
        except Exception as e:
            st.error(f"Failed to load schema: {e}")
            st.stop()

    schema = st.session_state.schema

    # Connect to Google Sheets using stored IDs
    try:
        os.environ["SPREADSHEET_ID"] = st.session_state.settings["SPREADSHEET_ID"]
        os.environ["WORKSHEET_NAME"] = st.session_state.settings["WORKSHEET_NAME"]
        ws = get_worksheet_and_ensure_headers(schema["columns"])
        st.success(f"Connected to Google Sheet • Worksheet: {st.session_state.settings['WORKSHEET_NAME']}")
    except Exception as e:
        st.error(f"Google Sheets setup failed: {e}")
        st.stop()

    # Ensure files and idx exist
    if "files" not in st.session_state: st.session_state.files = []
    if "idx" not in st.session_state: st.session_state.idx = 0
    if "use_urls" not in st.session_state: st.session_state.use_urls = False

    total = len(st.session_state.files)
    if total == 0:
        st.info("No videos loaded. Go back to **Setup** and add uploads or URLs.")
        st.stop()

    # Clamp idx
    if st.session_state.idx < 0: st.session_state.idx = 0
    if st.session_state.idx > total - 1: st.session_state.idx = total - 1

    current_i = st.session_state.idx
    saved_rows = max(len(ws.get_all_values()) - 1, 0)
    st.write(f"**Clip:** {current_i+1}/{total} | **Saved rows:** {saved_rows}")

    # Current clip
    cur = st.session_state.files[current_i]
    st.subheader(f"Now labeling: {cur.get('name','(video)')}")

    if st.session_state.use_urls:
        st.video(cur["url"])
        default_id = cur["url"]
    else:
        st.video(cur["data"], format="video/mp4", start_time=0)
        default_id = cur["name"][:-4] if cur["name"].lower().endswith(".mp4") else cur["name"]

    # -----------------------------
    # Labels (inside a form to avoid reruns while selecting)
    # -----------------------------
    with st.form(f"label_form_{current_i}", clear_on_submit=False):
        st.subheader("Labels")
        video_id = st.text_input("video_id", value=default_id, key=f"vidid_{current_i}")

        form_vals = {}
        for col in schema["columns"]:
            if col == "timestamp_utc":
                continue
            opts = [""] + schema["choices"].get(col, [])
            if col == "video_id":
                default = video_id or ""
                if default and default not in opts:
                    opts.insert(1, default)
                form_vals[col] = st.selectbox(
                    col,
                    options=opts,
                    index=opts.index(default) if default in opts else 0,
                    key=f"sb_{col}_{current_i}"
                )
            else:
                form_vals[col] = st.selectbox(
                    col,
                    options=opts,
                    index=0,
                    key=f"sb_{col}_{current_i}"
                )

        uncertain = st.checkbox("Mark as uncertain", key=f"unc_{current_i}")
        submitted = st.form_submit_button("Submit & Next")

    # Handle submit
    if submitted:
        if not video_id:
            st.error("Please set a video_id before submitting.")
        else:
            try:
                form_vals["video_id"] = video_id
                if uncertain:
                    if "label_confidence" in schema["columns"]:
                        form_vals["label_confidence"] = "uncertain"
                    elif "notes" in schema["columns"]:
                        existing = form_vals.get("notes", "")
                        form_vals["notes"] = (existing + "; " if existing else "") + "uncertain"

                row = build_row(schema["columns"], form_vals)
                ws.append_row(row, value_input_option="USER_ENTERED")
                st.success("Saved to Google Sheets ✅")

                if st.session_state.idx < len(st.session_state.files) - 1:
                    st.session_state.idx += 1
                st.rerun()
            except Exception as e:
                st.error(f"Append failed: {e}")

    # Navigation (outside form)
    c1, c2 = st.columns(2)
    with c1:
        if st.button("⟵ Previous", use_container_width=True, disabled=(current_i == 0)):
            if st.session_state.idx > 0:
                st.session_state.idx -= 1
            st.rerun()
    with c2:
        if st.button("Next (without saving)", use_container_width=True, disabled=(current_i == total - 1)):
            if st.session_state.idx < len(st.session_state.files) - 1:
                st.session_state.idx += 1
            st.rerun()