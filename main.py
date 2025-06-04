import base64
import json

# Ambil isi base64 dari environment
encoded = os.getenv("GCP_CREDENTIALS_BASE64")

if not encoded:
    raise Exception("GCP_CREDENTIALS_BASE64 not set")

# Decode dan simpan ke file
decoded = base64.b64decode(encoded)
with open("service_account.json", "wb") as f:
    f.write(decoded)
    
import os
import json
import base64
from google.oauth2 import service_account
import gspread

# Ambil base64 JSON dari environment
base64_creds = os.environ.get("GCP_CREDENTIALS_BASE64")
if not base64_creds:
    raise Exception("GCP_CREDENTIALS_BASE64 not set")

# Decode & parse
json_str = base64.b64decode(base64_creds).decode("utf-8")
creds_dict = json.loads(json_str)

# Gunakan google-auth (BUKAN oauth2client)
scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
credentials = service_account.Credentials.from_service_account_file("service_account.json", scopes=scopes)

# Authorize ke Google Sheets
gc = gspread.authorize(credentials)
sheet = gc.open("Checkin Sales").sheet1
