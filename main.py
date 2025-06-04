import os
import json
import base64
from google.oauth2 import service_account
import gspread

# Ambil base64 dari environment
encoded = os.getenv("GCP_CREDENTIALS_BASE64")
if not encoded:
    raise Exception("GCP_CREDENTIALS_BASE64 not set")

# Decode base64 jadi JSON string
json_str = base64.b64decode(encoded).decode("utf-8")

# Parse jadi dictionary
creds_dict = json.loads(json_str)

# Buat credentials dari dictionary
scopes = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]
credentials = service_account.Credentials.from_service_account_info(creds_dict, scopes=scopes)

# Authorisasi gspread
gc = gspread.authorize(credentials)

# Buka spreadsheet (ganti dengan nama file spreadsheet kamu)
sheet = gc.open("Checkin Sales").sheet1

# Tes akses sheet
print("✅ Berhasil terhubung ke Google Sheets.")
print("Contoh data dari baris pertama:")
print(sheet.row_values(1))
