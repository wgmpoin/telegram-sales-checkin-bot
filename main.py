import os
import json
import logging
import base64
from datetime import datetime
from flask import Flask
from google.oauth2 import service_account
import gspread
import asyncio # Tambahkan import asyncio

# Impor modul Telegram Bot
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes, ConversationHandler, filters
)

# Konfigurasi logging agar lebih mudah melihat pesan di log Render
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

logging.info("Memulai proses deployment bot...")

# --- States untuk ConversationHandler ---
NAMA_TOKO, ALAMAT_WILAYAH, LOKASI, JUMLAH_KUNJUNGAN = range(4)

# --- Variabel Global untuk gspread ---
gc = None
sheet = None
SPREADSHEET_ID = "1xx1WzEqrp2LYrg-VTgOPwAhk15DigpBodPM9Bm6pbD4" # ID Spreadsheet Anda
SPREADSHEET_NAME = "Checkin Sales" # Nama file Google Spreadsheet Anda (bukan ID)
SHEET_TAB_NAME = "Checkin" # Nama tab sheet di dalam spreadsheet. Pastikan ini sesuai!

# --- Variabel untuk Authorized Sales ---
AUTHORIZED_SALES_IDS = set() # Akan diisi dari environment variable

# --- Fungsi untuk Inisialisasi Google Sheets ---
def initialize_google_sheets():
    global gc, sheet
    creds_base64 = os.environ.get("GCP_CREDENTIALS_BASE64")

    if not creds_base64:
        logging.error("ERROR: Variabel environment 'GCP_CREDENTIALS_BASE64' tidak ditemukan atau kosong.")
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

        # Menggunakan SPREADSHEET_ID untuk membuka spreadsheet
        spreadsheet = gc.open_by_key(SPREADSHEET_ID)
        
        # Menggunakan nama tab sheet (misalnya "Checkin")
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
        logging.error("ERROR: Spreadsheet tidak ditemukan. Pastikan Spreadsheet ID sudah benar dan akun layanan memiliki akses ke spreadsheet.")
        return False
    except gspread.exceptions.WorksheetNotFound:
        logging.error(f"ERROR: Tab sheet '{SHEET_TAB_NAME}' tidak ditemukan dalam spreadsheet. Pastikan nama tab benar.")
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
            # Mengubah string '123,456,789' menjadi set {123, 456, 789}
            AUTHORIZED_SALES_IDS = set(map(int, authorized_ids_str.split(',')))
            logging.info(f"Authorized sales IDs loaded: {AUTHORIZED_SALES_IDS}")
        except ValueError:
            logging.error("ERROR: AUTHORIZED_SALES environment variable contains non-integer values. Please use comma-separated integers.")
            AUTHORIZED_SALES_IDS = set() # Reset to empty set on error
    else:
        logging.warning("WARNING: AUTHORIZED_SALES environment variable is not set. Bot will not restrict access.")
        # Jika tidak ada AUTHORIZED_SALES, bot akan bisa digunakan siapa saja
        # Jika Anda ingin bot tidak berfungsi jika tidak ada daftar, exit(1) di sini.

# --- Middleware untuk Memeriksa Otorisasi ---
async def check_authorization(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in AUTHORIZED_SALES_IDS and AUTHORIZED_SALES_IDS: # Hanya memfilter jika daftar tidak kosong
        logging.warning(f"Akses ditolak untuk user ID: {user_id} ({update.effective_user.full_name})")
        await update.message.reply_text("Maaf, Anda tidak memiliki izin untuk menggunakan bot ini.")
        return False # Tolak akses
    return True # Izinkan akses

# --- Fungsi-fungsi Handler Bot Telegram ---

# Handler untuk perintah /start
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mengirim pesan ketika perintah /start dikeluarkan."""
    if not await check_authorization(update, context):
        return
    
    user = update.effective_user
    logging.info(f"Perintah /start diterima dari user: {user.full_name} ({user.id})")
    await update.message.reply_html(
        f"Halo {user.mention_html()}! 👋\n"
        "Saya bot pencatat sales. Ketik /checkin untuk memulai pencatatan kunjungan."
    )
    logging.info(f"Pesan balasan /start dikirim ke: {user.full_name}")

# Handler untuk perintah /checkin (memulai percakapan)
async def checkin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Memulai percakapan check-in."""
    if not await check_authorization(update, context):
        return ConversationHandler.END # Akhiri percakapan jika tidak diotorisasi

    logging.info(f"Perintah /checkin diterima dari user: {update.effective_user.full_name}")
    await update.message.reply_text(
        "Baik, mari kita mulai check-in Anda.\n\n"
        "Silakan ketik **Nama Toko** yang Anda kunjungi:",
        parse_mode="Markdown"
    )
    return NAMA_TOKO

# Handler untuk menerima Nama Toko
async def nama_toko(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Menyimpan nama toko dan meminta alamat/wilayah."""
    # Karena ini adalah bagian dari ConversationHandler yang diawali /checkin,
    # kita tidak perlu check_authorization lagi di sini, karena sudah dilakukan di entry_point.
    user_data = context.user_data
    user_data['nama_toko'] = update.message.text
    logging.info(f"Nama Toko diterima: {user_data['nama_toko']} dari {update.effective_user.full_name}")
    
    await update.message.reply_text(
        "Sekarang, silakan ketik **Alamat/Wilayah** toko tersebut (contoh: Denpasar, Kuta, Jl. Teuku Umar):",
        parse_mode="Markdown"
    )
    return ALAMAT_WILAYAH

# Handler untuk menerima Alamat/Wilayah
async def alamat_wilayah(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Menyimpan alamat/wilayah dan meminta lokasi."""
    user_data = context.user_data
    user_data['alamat_wilayah'] = update.message.text
    logging.info(f"Alamat/Wilayah diterima: {user_data['alamat_wilayah']} dari {update.effective_user.full_name}")

    # Tombol untuk share lokasi
    keyboard = [[KeyboardButton("Share Lokasi", request_location=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

    await update.message.reply_text(
        "Selanjutnya, silakan **Share Lokasi** Anda saat ini melalui Telegram.\n"
        "Atau, jika tidak bisa share lokasi, kirim saja teks 'skip'.",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    return LOKASI

# Handler untuk menerima Lokasi (atau 'skip')
async def lokasi(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Menyimpan link lokasi dan meminta jumlah kunjungan."""
    user_data = context.user_data
    location_link = "Tidak Tersedia"

    if update.message.location:
        lat = update.message.location.latitude
        lon = update.message.location.longitude
        # Format link Google Maps yang lebih standar
        location_link = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
        logging.info(f"Lokasi diterima: Lat={lat}, Lon={lon} dari {update.effective_user.full_name}")
    elif update.message.text and update.message.text.lower() == 'skip':
        logging.info(f"Lokasi dilewati oleh {update.effective_user.full_name}")
    else:
        await update.message.reply_text("Maaf, saya tidak mengenali input lokasi Anda. Silakan kirim 'Share Lokasi' atau ketik 'skip'.")
        return LOKASI # Tetap di state LOKASI jika input tidak valid

    user_data['link_lokasi'] = location_link

    await update.message.reply_text(
        "Terima kasih!\nSekarang, masukkan **Jumlah Kunjungan Bulanan** ke toko ini (contoh: 1, 2, 3, dst.):",
        reply_markup=ReplyKeyboardRemove(), # Hapus keyboard lokasi
        parse_mode="Markdown"
    )
    return JUMLAH_KUNJUNGAN

# Handler untuk menerima Jumlah Kunjungan dan menyimpan ke Spreadsheet
async def jumlah_kunjungan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Menyimpan jumlah kunjungan dan mencatat semua data ke spreadsheet."""
    user_data = context.user_data
    jumlah_kunjungan_text = update.message.text

    try:
        jumlah_kunjungan_int = int(jumlah_kunjungan_text)
        user_data['jumlah_kunjungan'] = jumlah_kunjungan_int
        logging.info(f"Jumlah Kunjungan diterima: {jumlah_kunjungan_int} dari {update.effective_user.full_name}")
    except ValueError:
        await update.message.reply_text("Maaf, jumlah kunjungan harus berupa angka. Silakan coba lagi.")
        return JUMLAH_KUNJUNGAN # Tetap di state JUMLAH_KUNJUNGAN jika input tidak valid

    # Mendapatkan tanggal dan waktu saat ini (WITA)
    # Gunakan pytz untuk timezone yang akurat
    # import pytz # Anda perlu menambahkan 'pytz' ke requirements.txt jika menggunakannya
    # bali_tz = pytz.timezone('Asia/Makassar') # WITA
    # now = datetime.now(bali_tz)
    
    # Untuk kesederhanaan saat ini, kita gunakan waktu server Render (UTC)
    # Jika ingin WITA, Anda bisa menambahkan `pytz` ke `requirements.txt` dan uncomment kode di atas
    now = datetime.now() # Ini akan menggunakan waktu UTC di Render.com
    tanggal = now.strftime("%Y-%m-%d") # Format YYYY-MM-DD
    waktu = now.strftime("%H:%M:%S")    # Format HH:MM:SS

    # Mengumpulkan semua data
    row_data = [
        update.effective_user.full_name, # Nama sales
        update.effective_user.id,        # ID Sales
        user_data.get('nama_toko', ''),
        user_data.get('alamat_wilayah', ''),
        tanggal,
        waktu,
        user_data.get('link_lokasi', ''),
        user_data.get('jumlah_kunjungan', '')
    ]

    # Menulis ke Google Spreadsheet
    try:
        if sheet:
            sheet.append_row(row_data)
            logging.info(f"Data berhasil dicatat ke spreadsheet: {row_data}")
            await update.message.reply_text(
                "✅ Check-in berhasil dicatat!\n"
                f"Nama Sales: *{update.effective_user.full_name}*\n"
                f"ID Sales: *{update.effective_user.id}*\n"
                f"Nama Toko: *{user_data['nama_toko']}*\n"
                f"Alamat/Wilayah: *{user_data['alamat_wilayah']}*\n"
                f"Link Lokasi: {user_data['link_lokasi']}\n"
                f"Jumlah Kunjungan: *{user_data['jumlah_kunjungan']}*\n"
                f"Tanggal/Waktu: *{tanggal} {waktu}*\n\n"
                "Terima kasih atas check-in Anda!",
                parse_mode="Markdown"
            )
        else:
            logging.error("Koneksi Google Sheet belum terinisialisasi. Tidak dapat mencatat data.")
            await update.message.reply_text("Maaf, ada masalah dalam menghubungkan ke Google Sheet. Mohon coba lagi nanti.")
    except Exception as e:
        logging.error(f"Gagal mencatat data ke spreadsheet: {e}")
        await update.message.reply_text("Maaf, terjadi kesalahan saat mencoba mencatat data Anda ke spreadsheet. Silakan coba lagi.")

    # Akhiri percakapan
    context.user_data.clear() # Hapus data pengguna
    return ConversationHandler.END

# Handler untuk membatalkan percakapan
async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Membatalkan dan mengakhiri percakapan."""
    logging.info(f"Perintah /cancel diterima dari user: {update.effective_user.full_name}")
    user_data = context.user_data
    user_data.clear() # Hapus data pengguna
    await update.message.reply_text(
        "Pencatatan dibatalkan. Kapan-kapan kita bisa coba lagi! 👋",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


# --- Aplikasi Flask Sederhana (Web Server untuk Render) ---
app = Flask(__name__)

@app.route("/")
def index():
    return "Bot Telegram Sales Checkin sedang berjalan!"

# Fungsi utama untuk menjalankan bot Telegram (dengan Flask)
async def run_bot_telegram(): # Ganti nama fungsi untuk menghindari konflik dengan fungsi Flask
    """Menjalankan bot Telegram."""
    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not telegram_token:
        logging.error("ERROR: Variabel environment 'TELEGRAM_BOT_TOKEN' tidak ditemukan. Bot Telegram tidak dapat dijalankan.")
        return

    application = Application.builder().token(telegram_token).build()

    # Buat ConversationHandler untuk alur check-in
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("checkin", checkin_command)],
        states={
            NAMA_TOKO: [MessageHandler(filters.TEXT & ~filters.COMMAND, nama_toko)],
            ALAMAT_WILAYAH: [MessageHandler(filters.TEXT & ~filters.COMMAND, alamat_wilayah)],
            LOKASI: [
                MessageHandler(filters.LOCATION, lokasi),
                MessageHandler(filters.TEXT & ~filters.COMMAND, lokasi) # Untuk opsi 'skip'
            ],
            JUMLAH_KUNJUNGAN: [MessageHandler(filters.TEXT & ~filters.COMMAND, jumlah_kunjungan)],
        },
        fallbacks=[CommandHandler("cancel", cancel_command)],
    )

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("cancel", cancel_command)) # Handler cancel global

    logging.info("Bot Telegram mulai polling untuk update...")
    # Gunakan application.run_polling() secara langsung di dalam asyncio.run
    await application.run_polling(poll_interval=3.0, timeout=30)


if __name__ == "__main__":
    # Inis
