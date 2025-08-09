import os, gspread
import json, os, tempfile
import streamlit as st
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

load_dotenv()
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
CREDS_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
WORKSHEET_NAME = os.getenv("WORKSHEET_NAME", "labels_log")

# If running on Streamlit Cloud, write service account JSON from secrets to a temp file
if "service_account" in st.secrets:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
    tmp.write(json.dumps(st.secrets["service_account"]).encode("utf-8"))
    tmp.flush()
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = tmp.name

# Also read spreadsheet settings from secrets if present
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID") or st.secrets.get("SPREADSHEET_ID")
WORKSHEET_NAME = os.getenv("WORKSHEET_NAME") or st.secrets.get("WORKSHEET_NAME", "labels_log")

def get_client():
    if not CREDS_PATH or not os.path.exists(CREDS_PATH):
        raise RuntimeError("Service account JSON not found. Set GOOGLE_APPLICATION_CREDENTIALS in .env and place the file there.")
    creds = Credentials.from_service_account_file(CREDS_PATH, scopes=SCOPES)
    return gspread.authorize(creds)
def migrate_headers_if_needed(ws):
    headers = ws.row_values(1)
    updated = False
    if "Video_Name" in headers:
        idx = headers.index("Video_Name") + 1
        ws.delete_columns(idx)
        headers.pop(idx-1); updated = True
    if "Video ID" in headers:
        col_idx = headers.index("Video ID") + 1
        ws.update_cell(1, col_idx, "video_id")
        headers[col_idx-1] = "video_id"; updated = True
    return updated, headers
def ensure_capacity(ws, min_rows=1000, min_cols=26):
    if ws.row_count < min_rows:
        ws.add_rows(min_rows - ws.row_count)
    if ws.col_count < min_cols:
        ws.add_cols(min_cols - ws.col_count)
def get_worksheet_and_ensure_headers(headers):
    if not SPREADSHEET_ID:
        raise RuntimeError("SPREADSHEET_ID not set in .env")
    gc = get_client()
    sh = gc.open_by_key(SPREADSHEET_ID)
    try:
        ws = sh.worksheet(WORKSHEET_NAME)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=WORKSHEET_NAME, rows=max(1000, 2), cols=max(26, len(headers)))
    ensure_capacity(ws, min_rows=1000, min_cols=max(26, len(headers)))
    migrated, current_headers = migrate_headers_if_needed(ws)
    if not current_headers or current_headers != headers or migrated:
        ws.update(range_name="A1", values=[headers])
    ensure_capacity(ws, min_rows=1000, min_cols=max(26, len(headers)))
    return ws
