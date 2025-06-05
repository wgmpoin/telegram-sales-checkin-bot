import os
import base64
import json
import gspread
from google.oauth2.service_account import Credentials

# Ambil isi base64 dari environment
encoded = os.environ.get("GCP_CREDENTIALS_BASE64")
if not encoded:
    raise Exception("GCP_CREDENTIALS_BASE64 is not set")

# Decode dan simpan ke file
json_str = base64.b64decode(encoded).decode("utf-8")

# Simpan ke file lokal
with open("service_account.json", "w") as f:
    f.write(json_str)

# Buat credentials dari file, BUKAN dari dict
scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
credentials = Credentials.from_service_account_file("service_account.json", scopes=scopes)

# Authorize
gc = gspread.authorize(credentials)
sheet = gc.open("Checkin Sales").sheet1  # Ganti dengan nama spreadsheet kamu
