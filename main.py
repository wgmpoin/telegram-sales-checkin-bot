import os
import json
import logging
import base64
from datetime import datetime
from flask import Flask, request, abort
from google.oauth2 import service_account
import gspread
import asyncio

# Konfigurasi logging agar lebih mudah melihat pesan di log Render
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

logging.info("Memulai proses deployment bot...")

# --- States untuk ConversationHandler ---
NAMA_TOKO, ALAMAT_WILAYAH, LOKASI, JUMLAH_KUNJUNGAN = range(4)

# --- Variabel Global untuk gspread ---
gc = None
sheet = None
# PASTIKAN SPREADSHEET_ID INI SESUAI DENGAN ID GOOGLE SHEET ANDA
# Contoh: "1xx1WzEqrp2LYrg-VTpOPQAhk15DigpBodPM9Bm6pbD4"
SPREADSHEET_ID = os.environ.get("GOOGLE_SHEET_ID") # Mengambil dari Environment Variable
# PASTIKAN SHEET_TAB_NAME INI SESUAI DENGAN NAMA TAB DI GOOGLE SHEET ANDA (contoh: "Checkin")
SHEET_TAB_NAME = os.environ.get("GOOGLE_SHEET_TAB_NAME", "Checkin") # Mengambil dari Environment Variable, default "Checkin"

# --- Variabel untuk Authorized Sales ---
AUTHORIZED_SALES_IDS = set() # Akan diisi dari environment variable

# --- Inisialisasi Aplikasi Bot Telegram (akan di-pass ke Flask) ---
application = None # Akan diinisialisasi nanti

# --- Fungsi untuk Inisialisasi Google Sheets ---
def initialize_google_sheets():
    global gc, sheet
    creds_base64 = os.environ.get("GCP_CREDENTIALS_BASE64")

    if not creds_base64:
        logging.error("ERROR: Variabel environment 'GCP_CREDENTIALS_BASE64' tidak ditemukan atau kosong. Tidak dapat terhubung ke Google Sheets.")
        return False
    
    if not SPREADSHEET_ID:
        logging.error("ERROR: Variabel environment 'GOOGLE_SHEET_ID' tidak ditemukan atau kosong. Tidak dapat terhubung ke Google Sheets.")
        return False

    try:
        creds_decoded = base64.b64decode(creds_base64).decode('utf-8')
        creds_dict = json.loads(creds_decoded)

        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        credentials = service_account.Credentials.from_service_account_info(creds_dict, scopes=scopes)
        gc = gspread.authorize(credentials)

        spreadsheet = gc.open_by_key(SPREADSHEET_ID)
        sheet = spreadsheet.worksheet(SHEET_TAB_NAME)
        
        logging.info(f"Berhasil terhubung ke Google Sheet (ID: '{SPREADSHEET_ID}', Tab: '{SHEET_TAB_NAME}')")
        return True

    except base64.binascii.Error as e:
        logging.error(f"ERROR: Gagal dekode Base64. Error: {e}")
        return False
    except json.JSONDecodeError as e:
        logging.error(f"ERROR: Gagal parsing JSON. Error: {e}")
        return False
    except gspread.exceptions.SpreadsheetNotFound:
        logging.error("ERROR: Spreadsheet tidak ditemukan. Pastikan Google Sheet ID sudah benar dan akun layanan memiliki akses ke spreadsheet.")
        return False
    except gspread.exceptions.WorksheetNotFound:
        logging.error(f"ERROR: Tab sheet '{SHEET_TAB_NAME}' tidak ditemukan dalam spreadsheet. Pastikan nama tab benar dan case-sensitive.")
        return False
    except gspread.exceptions.APIError as e:
        logging.error(f"ERROR: Terjadi kesalahan API Google Sheets/Drive. Pesan: {e}")
        logging.error("Penyebab mungkin: API belum diaktifkan, izin akun layanan tidak cukup, atau ada masalah dengan koneksi.")
        return False
    except Exception as e:
        logging.error(f"ERROR: Terjadi kesalahan tidak terduga saat menyiapkan Google Sheets: {e}")
        return False

# --- Fungsi untuk Memuat Authorized Sales IDs ---
def load_authorized_sales_ids():
    global AUTHORIZED_SALES_IDS
    authorized_ids_str = os.environ.get("AUTHORIZED_SALES")
    if authorized_ids_str:
        try:
            AUTHORIZED_SALES_IDS = set(map(int, authorized_ids_str.split(',')))
            logging.info(f"Authorized sales IDs loaded: {AUTHORIZED_SALES_IDS}")
        except ValueError:
            logging.error("ERROR: AUTHORIZED_SALES environment variable contains non-integer values. Please use comma-separated integers.")
            AUTHORIZED_SALES_IDS = set()
    else:
        logging.warning("WARNING: AUTHORIZED_SALES environment variable is not set. Bot will not restrict access.")

# --- Middleware untuk Memeriksa Otorisasi ---
async def check_authorization(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if AUTHORIZED_SALES_IDS and user_id not in AUTHORIZED_SALES_IDS:
        logging.warning(f"Akses ditolak untuk user ID: {user_id} ({update.effective_user.full_name})")
        await update.message.reply_text("Maaf, Anda tidak memiliki izin untuk menggunakan bot ini.")
        return False
    return True

# --- Fungsi-fungsi Handler Bot Telegram ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await check_authorization(update, context):
        return
    user = update.effective_user
    logging.info(f"Perintah /start diterima dari user: {user.full_name} ({user.id})")
    await update.message.reply_html(
        f"Halo {user.mention_html()}! 👋\n"
        "Saya bot pencatat sales. Ketik /checkin untuk memulai pencatatan kunjungan."
    )
    logging.info(f"Pesan balasan /start dikirim ke: {user.full_name}")

async def checkin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await check_authorization(update, context):
        return ConversationHandler.END
    
    # Pastikan Google Sheet sudah terinisialisasi sebelum memulai percakapan
    if sheet is None:
        logging.error(f"Perintah /checkin diterima, tetapi Google Sheet belum terinisialisasi.")
        await update.message.reply_text("Maaf, bot sedang mengalami masalah koneksi dengan Google Sheet. Mohon coba lagi nanti.")
        return ConversationHandler.END

    logging.info(f"Perintah /checkin diterima dari user: {update.effective_user.full_name}")
    await update.message.reply_text(
        "Baik, mari kita mulai check-in Anda.\n\n"
        "Silakan ketik **Nama Toko** yang Anda kunjungi:",
        parse_mode="Markdown"
    )
    return NAMA_TOKO

async def nama_toko(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = context.user_data
    user_data['nama_toko'] = update.message.text
    logging.info(f"Nama Toko diterima: {user_data['nama_toko']} dari {update.effective_user.full_name}")
    await update.message.reply_text(
        "Sekarang, silakan ketik **Alamat/Wilayah** toko tersebut (contoh: Denpasar, Kuta, Jl. Teuku Umar):",
        parse_mode="Markdown"
    )
    return ALAMAT_WILAYAH

async def alamat_wilayah(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = context.user_data
    user_data['alamat_wilayah'] = update.message.text
    logging.info(f"Alamat/Wilayah diterima: {user_data['alamat_wilayah']} dari {update.effective_user.full_name}")
    keyboard = [[KeyboardButton("Share Lokasi", request_location=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        "Selanjutnya, silakan **Share Lokasi** Anda saat ini melalui Telegram.\n"
        "Atau, jika tidak bisa share lokasi, kirim saja teks 'skip'.",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    return LOKASI

async def lokasi(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = context.user_data
    location_link = "Tidak Tersedia"
    if update.message.location:
        lat = update.message.location.latitude
        lon = update.message.location.longitude
        # Format yang lebih umum dan disarankan untuk Google Maps
        location_link = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}" 
        logging.info(f"Lokasi diterima: Lat={lat}, Lon={lon} dari {update.effective_user.full_name}")
    elif update.message.text and update.message.text.lower() == 'skip':
        logging.info(f"Lokasi dilewati oleh {update.effective_user.full_name}")
    else:
        await update.message.reply_text("Maaf, saya tidak mengenali input lokasi Anda. Silakan kirim 'Share Lokasi' atau ketik 'skip'.")
        return LOKASI
    user_data['link_lokasi'] = location_link
    await update.message.reply_text(
        "Terima kasih!\nSekarang, masukkan **Jumlah Kunjungan Bulanan** ke toko ini (contoh: 1, 2, 3, dst.):",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )
    return JUMLAH_KUNJUNGAN

async def jumlah_kunjungan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = context.user_data
    jumlah_kunjungan_text = update.message.text
    try:
        jumlah_kunjungan_int = int(jumlah_kunjungan_text)
        user_data['jumlah_kunjungan'] = jumlah_kunjungan_int
        logging.info(f"Jumlah Kunjungan diterima: {jumlah_kunjungan_int} dari {update.effective_user.full_name}")
    except ValueError:
        await update.message.reply_text("Maaf, jumlah kunjungan harus berupa angka. Silakan coba lagi
