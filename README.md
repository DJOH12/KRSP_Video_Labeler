# Driver Emotion Labeler — README

A Streamlit app for labeling short driver videos and saving the results to **Google Sheets**.
Works fully offline for video files (they never leave the machine) and writes only the labels to your Sheet.

---

## What you’ll need

- **Python** 3.9–3.11 (recommended 3.11)
- **Google Service Account JSON** (for Sheets write access)
- A Google Sheet you control (its **Spreadsheet ID**)
- The two schema files in the project folder:
  - `Features.xlsx`
  - `Example_of_Video_Labelling.xlsx`

> The app reads allowed dropdown values from `Features.xlsx` and column names (plus fallback choices) from `Example_of_Video_Labelling.xlsx`.

---

## Google setup (one time)

1. **Create / locate** a Service Account in Google Cloud  
   - Console → IAM & Admin → Service Accounts → *your project*.
   - Keys → **Add key** → **Create new key** → **JSON** → download.
   - Save as `service_account.json` in the app folder.

2. **Share your Google Sheet** with the service account’s **email**  
   - It looks like: `your-sa@your-project.iam.gserviceaccount.com`  
   - Give **Editor** permission.

3. **Get the Spreadsheet ID**  
   - From the Sheet URL: `https://docs.google.com/spreadsheets/d/<THIS_PART>/edit#gid=0`.

4. Create `.env` from the template:
   ```
   SPREADSHEET_ID=YOUR_SPREADSHEET_ID
   WORKSHEET_NAME=labels_log
   GOOGLE_APPLICATION_CREDENTIALS=service_account.json
   ```

---

## Install & run

### macOS

1. Install Python if needed (recommended via Homebrew):
   ```bash
   brew install python@3.11
   ```
2. In Terminal, cd into the project folder and run:
   ```bash
   python3 -m venv .venv

   source .venv/bin/activate

   python -m pip install --upgrade pip

   pip install -r requirements.txt

   streamlit run app.py
   ```
3. The app opens in your browser at `http://localhost:8501`.

**Using the macOS launcher**  
- Double-click `start_mac.command` to launch the app automatically.  
- If macOS blocks it, run:
  ```bash
  chmod +x start_mac.command
  xattr -d com.apple.quarantine start_mac.command
  ./start_mac.command
  ```

### Windows

1. Install Python 3.11 from python.org (tick **Add Python to PATH**).
2. In **Command Prompt** (or PowerShell), inside the project folder:
   ```bat
   py -3 -m venv .venv

   .venv\Scripts\activate

   python -m pip install --upgrade pip

   pip install -r requirements.txt

   streamlit run app.py

   ```
3. Or double-click `start_windows.bat`.

### Linux (Ubuntu example)

```bash
sudo apt update && sudo apt install -y python3-venv python3-pip
cd /path/to/driver_emotion_labeler
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

**Using the Linux launcher**  
- Make it executable:
  ```bash
  chmod +x start_linux.sh
  ./start_linux.sh
  ```

---

## Using the app

1. Click **Load schema** (left sidebar) to read `Features.xlsx` + `Example_of_Video_Labelling.xlsx`.
2. **Upload** one or more `.mp4` files (local only; not uploaded anywhere).
3. The **video_id** defaults to the file name (you can edit it).
4. Fill label **dropdowns** (populated from the Excel files).
5. Use **Submit & Next**, **Skip**, **Previous/Next** to navigate.
6. Rows append to your Google Sheet under the headers the app set:
   - `video_id` is the **first column** and the only video identifier saved.

---

## Dependencies

Pinned in `requirements.txt` for reliable installs:
```
streamlit==1.36.0
pandas==2.2.2
gspread==6.1.2
google-auth==2.32.0
google-auth-oauthlib==1.2.1
oauth2client==4.1.3
python-dotenv==1.0.1
openpyxl==3.1.5
```

---

## Troubleshooting

- **“No secrets files found … st.secrets”**  
  You’re running locally. We use **.env** locally; no `secrets.toml` is needed.

- **Permission error on `start_mac.command`**  
  ```bash
  chmod +x start_mac.command
  xattr -d com.apple.quarantine start_mac.command
  ./start_mac.command
  ```

- **Google write fails / permission denied**  
  Ensure the **service account email** has **Editor** access to the sheet.

---
