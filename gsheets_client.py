import os
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

# Try to import streamlit to access secrets when running on Streamlit Cloud
try:
    import streamlit as st
    HAS_ST = True
except Exception:
    HAS_ST = False

# Load .env for local runs
load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

def _make_creds():
    """
    Prefer Streamlit secrets (Cloud). Fallback to local JSON via .env (GOOGLE_APPLICATION_CREDENTIALS).
    """
    # 1) Streamlit Cloud: service account in secrets
    if HAS_ST and "gcp_service_account" in st.secrets:
        sa_info = dict(st.secrets["gcp_service_account"])  # TOML -> dict
        return Credentials.from_service_account_info(sa_info, scopes=SCOPES)

    # 2) Local: service_account.json path from .env (or default name)
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "service_account.json")
    if not creds_path or not os.path.exists(creds_path):
        raise RuntimeError(
            "Service account not found. On Streamlit Cloud, set [gcp_service_account] in Secrets. "
            "Locally, put service_account.json next to app.py and set GOOGLE_APPLICATION_CREDENTIALS in .env."
        )
    return Credentials.from_service_account_file(creds_path, scopes=SCOPES)

def get_client():
    creds = _make_creds()
    return gspread.authorize(creds)

def _get_sheet_ids():
    """
    Return (SPREADSHEET_ID, WORKSHEET_NAME) from env first, else secrets.
    """
    spreadsheet_id = os.getenv("SPREADSHEET_ID")
    worksheet_name = os.getenv("WORKSHEET_NAME")

    if (not spreadsheet_id or not worksheet_name) and HAS_ST:
        spreadsheet_id = spreadsheet_id or st.secrets.get("SPREADSHEET_ID")
        worksheet_name = worksheet_name or st.secrets.get("WORKSHEET_NAME", "labels_log")

    if not spreadsheet_id:
        raise RuntimeError("SPREADSHEET_ID not set (env or secrets).")
    if not worksheet_name:
        worksheet_name = "labels_log"

    return spreadsheet_id, worksheet_name

def ensure_capacity(ws, min_rows=1000, min_cols=26):
    """Grow the sheet if needed (never shrinks)."""
    try:
        if ws.row_count < min_rows:
            ws.add_rows(min_rows - ws.row_count)
        if ws.col_count < min_cols:
            ws.add_cols(min_cols - ws.col_count)
    except Exception:
        # Some accounts/sheets may deny resize; ignore silently
        pass

def migrate_headers_if_needed(ws):
    """
    One-time migration:
    - Remove 'Video_Name' column entirely
    - Rename 'Video ID' -> 'video_id'
    """
    headers = ws.row_values(1)
    updated = False
    if "Video_Name" in headers:
        idx = headers.index("Video_Name") + 1
        ws.delete_columns(idx)
        headers.pop(idx - 1)
        updated = True
    if "Video ID" in headers:
        col_idx = headers.index("Video ID") + 1
        ws.update_cell(1, col_idx, "video_id")
        headers[col_idx - 1] = "video_id"
        updated = True
    return updated, headers

def get_worksheet_and_ensure_headers(headers):
    """
    Open the target worksheet (create if missing), ensure capacity and exact header row.
    """
    spreadsheet_id, worksheet_name = _get_sheet_ids()
    gc = get_client()
    sh = gc.open_by_key(spreadsheet_id)

    try:
        ws = sh.worksheet(worksheet_name)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=worksheet_name, rows=max(1000, 2), cols=max(26, len(headers)))

    # Capacity first
    ensure_capacity(ws, min_rows=1000, min_cols=max(26, len(headers)))

    # Migrate old headers if needed, then ensure current headers
    try:
        migrate_headers_if_needed(ws)
    except Exception:
        # If we can't migrate (permissions), continue with normal header ensure
        pass

    current_headers = ws.row_values(1)
    if current_headers != headers:
        ws.update(range_name="A1", values=[headers])

    return ws

def append_row_safe(ws, row):
    """Append a row with user-entered formatting."""
    ws.append_row(row, value_input_option="USER_ENTERED")