import os
import json
import logging
import base64
from flask import Flask
from google.oauth2 import service_account
import gspread

# Konfigurasi logging agar lebih mudah melihat pesan di log Render
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

logging.info("Starting bot deployment process...")

# --- Bagian Kredensial GCP ---
creds_base64 = os.environ.get("GCP_CREDENTIALS_BASE64")

if not creds_base64:
    logging.error("ERROR: Variabel environment 'GCP_CREDENTIALS_BASE64' tidak ditemukan atau kosong. Pastikan sudah diatur di Render.")
    exit(1)

try:
    creds_decoded = base64.b64decode(creds_base64).decode('utf-8')
    logging.info("GCP_CREDENTIALS_BASE64 successfully decoded from Base64.")

    creds_dict = json.loads(creds_decoded)
    logging.info("GCP_CREDENTIALS_BASE64 successfully parsed as JSON.")

    if "private_key" in creds_dict:
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        logging.info("Replaced '\\n' with '\\n' in private_key.")
    else:
        logging.warning("Private key not found in credentials dictionary.")

    # Definisikan cakupan (scopes) untuk Google Sheets API dan Google Drive API
    # KEDUA SCOPE INI SANGAT PENTING
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets", # Untuk Google Sheets
        "https://www.googleapis.com/auth/drive"         # Untuk Google Drive (dibutuhkan gspread)
    ]
    credentials = service_account.Credentials.from_service_account_info(creds_dict, scopes=scopes)
    logging.info("Google service account credentials loaded successfully.")

    # Otentikasi dan koneksi ke Google Sheets
    gc = gspread.authorize(credentials)

    # --- PENTING: UBAH INI SESUAI NAMA SPREADSHEET ANDA DI GOOGLE SHEETS ---
    # Ganti dengan Spreadsheet ID yang Anda salin dari URL
SPREADSHEET_ID = "https://docs.google.com/spreadsheets/d/1xx1WzEqrp2LYrg-VTgOPwAhk15DigpBodPM9Bm6pbD4/edit?gid=0#gid=0"
sheet = gc.open_by_key(SPREADSHEET_ID).sheet1
logging.info(f"Successfully connected to Google Sheet via ID: '{SPREADSHEET_ID}'")
    logging.info(f"Successfully connected to Google Sheet: '{sheet.title}'")

except base64.binascii.Error as e:
    logging.error(f"ERROR: Gagal dekode Base64. Pastikan nilai GCP_CREDENTIALS_BASE64 adalah string Base64 yang valid. Error: {e}")
    exit(1)
except json.JSONDecodeError as e:
    logging.error(f"ERROR: Gagal parsing JSON. Pastikan nilai GCP_CREDENTIALS_BASE64 (setelah didekode) adalah JSON yang valid. Error: {e}")
    exit(1)
except gspread.exceptions.SpreadsheetNotFound:
    logging.error("ERROR: Spreadsheet tidak ditemukan. Pastikan 'Nama Spreadsheet Anda' sudah benar dan akun layanan memiliki akses.")
    exit(1)
except Exception as e:
    logging.error(f"ERROR: Terjadi kesalahan lain saat menyiapkan Google Sheets: {e}")
    logging.error(f"Detil error: {e.args[0] if e.args else 'Tidak ada detil tambahan'}")
    exit(1)

# --- Aplikasi Flask Sederhana (Web Server untuk Render) ---
app = Flask(__name__)

@app.route("/")
def index():
    return "Telegram Sales Checkin Bot is running!"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logging.info(f"Flask app starting on port {port}...")
    app.run(host="0.0.0.0", port=port)
