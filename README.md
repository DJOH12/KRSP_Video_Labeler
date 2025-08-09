# Driver Emotion Labeler — Google Sheets (v6)

- Removes **Video_Name** column entirely from schema and sheet
- Renames **Video ID** → **video_id** in sheet if old format detected
- Migration runs only when old headers are present
- Features: batch upload, next/prev, skip, uncertain, progress

## Run
```
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```
