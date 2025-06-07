import os
import json
import logging
import base64 # Penting: untuk dekode base64
from flask import Flask
from google.oauth2 import service_account
import gspread

# Konfigurasi logging agar lebih mudah melihat pesan di log Render
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

logging.info("Starting bot deployment process...")

# --- Bagian Kredensial GCP ---
# Ambil kredensial yang sudah di-base64-encode dari variabel environment
creds_base64 = os.environ.get("GCP_CREDENTIALS_BASE64")

if not creds_base64:
    logging.error("ERROR: Variabel environment 'GCP_CREDENTIALS_BASE64' tidak ditemukan atau kosong. Pastikan sudah diatur di Render.")
    exit(1) # Keluar dari aplikasi jika kredensial tidak ada

try:
    # Dekode string base64 menjadi string JSON murni
    creds_decoded = base64.b64decode(creds_base64).decode('utf-8')
    logging.info("GCP_CREDENTIALS_BASE64 successfully decoded from Base64.")

    # Parsing string JSON menjadi dictionary Python
    creds_dict = json.loads(creds_decoded) # Perbaiki typo 'creeds_decoded' menjadi 'creds_decoded'
    logging.info("GCP_CREDENTIALS_BASE64 successfully parsed as JSON.")

    # Mengganti karakter escape \\n menjadi \n di private_key
    # Ini penting karena base64 mungkin mengubah \n menjadi \\n
    if "private_key" in creds_dict:
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        logging.info("Replaced '\\n' with '\\n' in private_key.")
    else:
        logging.warning("Private key not found in credentials dictionary.")

    # Definisikan cakupan (scopes) untuk Google Sheets API
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    credentials = service_account.Credentials.from_service_account_info(creds_dict, scopes=scopes)
    logging.info("Google service account credentials loaded successfully.")

    # Otentikasi dan koneksi ke Google Sheets
    gc = gspread.authorize(credentials)

    # --- PENTING: UBAH INI SESUAI NAMA SPREADSHEET ANDA DI GOOGLE SHEETS ---
    # Contoh: sheet = gc.open("Data Penjualan Bot").sheet1
    sheet = gc.open("Nama Spreadsheet Anda").sheet1
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
    exit(1)

# --- Aplikasi Flask Sederhana (Web Server untuk Render) ---
app = Flask(__name__)

@app.route("/")
def index():
    # Ini akan menunjukkan bahwa bot Anda berjalan dan web service-nya aktif
    return "Telegram Sales Checkin Bot is running!"

if __name__ == "__main__":
    # Render.com akan menyediakan port melalui variabel environment PORT
    # Kita harus menggunakan port ini, bukan port statis seperti 10000
    port = int(os.environ.get("PORT", 5000)) # Default ke 5000 jika PORT tidak ada (untuk pengujian lokal)
    logging.info(f"Flask app starting on port {port}...")
    app.run(host="0.0.0.0", port=port)
