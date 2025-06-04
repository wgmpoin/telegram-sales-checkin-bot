import os
import base64
from google.oauth2 import service_account
import gspread

# Ambil isi base64 dari environment
encoded = os.getenv("GCP_CREDENTIALS_BASE64")
if not encoded:
    raise Exception("GCP_CREDENTIALS_BASE64 not set")

# Decode dan simpan ke file
decoded = base64.b64decode(encoded)
with open("service_account.json", "wb") as f:
    f.write(decoded)

# Buat kredensial dari file
scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
credentials = service_account.Credentials.from_service_account_file("service_account.json", scopes=scopes)

# Authorisasi ke Google Sheets
gc = gspread.authorize(credentials)
sheet = gc.open("Checkin Sales").sheet1  # ganti sesuai nama spreadsheet kamu
