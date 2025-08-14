import os, gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

# Load .env (local) and env vars
load_dotenv()

# Pure .env / env-based config for local runs
CREDS_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "service_account.json")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
WORKSHEET_NAME = os.getenv("WORKSHEET_NAME", "labels_log")

def get_client():
    if not CREDS_PATH or not os.path.exists(CREDS_PATH):
        raise RuntimeError(
            "Service account JSON not found. Set GOOGLE_APPLICATION_CREDENTIALS in .env "
            "and place the JSON file at that path (e.g., service_account.json)."
        )
    creds = Credentials.from_service_account_file(CREDS_PATH, scopes=["https://www.googleapis.com/auth/spreadsheets"])
    return gspread.authorize(creds)

def get_worksheet_and_ensure_headers(headers):
    if not SPREADSHEET_ID:
        raise RuntimeError("SPREADSHEET_ID not set in .env")
    gc = get_client()
    sh = gc.open_by_key(SPREADSHEET_ID)
    try:
        ws = sh.worksheet(WORKSHEET_NAME)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=WORKSHEET_NAME, rows=max(1000, 2), cols=max(26, len(headers)))
    # ensure header row
    ws.update(range_name="A1", values=[headers])
    return ws
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

