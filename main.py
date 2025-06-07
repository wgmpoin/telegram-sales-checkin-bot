import os
import json
import logging
import base64
from datetime import datetime
from flask import Flask, request, abort
from google.oauth2 import service_account
import gspread
import asyncio

# Pastikan import ini ada dan benar di awal file
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
        location_link = f"http://maps.google.com/maps?q={lat},{lon}" 
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
        await update.message.reply_text("Maaf, jumlah kunjungan harus berupa angka. Silakan coba lagi.")
        return JUMLAH_KUNJUNGAN 

    now = datetime.now() 
    tanggal = now.strftime("%Y-%m-%d")
    waktu = now.strftime("%H:%M:%S")

    # Mengumpulkan semua data
    # Pastikan urutan ini sesuai dengan kolom di Google Sheet Anda
    row_data = [
        update.effective_user.full_name, # Nama Sales
        update.effective_user.id,        # ID Sales
        user_data.get('nama_toko', ''),
        user_data.get('alamat_wilayah', ''),
        tanggal,
        waktu,
        user_data.get('link_lokasi', ''),
        user_data.get('jumlah_kunjungan', '')
    ]
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
            logging.error("Koneksi Google Sheet belum terinisialisasi saat mencoba mencatat data. Tidak dapat mencatat data.")
            await update.message.reply_text("Maaf, ada masalah dalam menghubungkan ke Google Sheet. Mohon coba lagi nanti.")
    except Exception as e:
        logging.error(f"Gagal mencatat data ke spreadsheet: {e}")
        await update.message.reply_text("Maaf, terjadi kesalahan saat mencoba mencatat data Anda ke spreadsheet. Silakan coba lagi.")
    context.user_data.clear()
    return ConversationHandler.END

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logging.info(f"Perintah /cancel diterima dari user: {update.effective_user.full_name}")
    user_data = context.user_data
    user_data.clear()
    await update.message.reply_text(
        "Pencatatan dibatalkan. Kapan-kapan kita bisa coba lagi! 👋",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


# --- Aplikasi Flask (Web Server untuk Render) ---
app = Flask(__name__)

# Endpoint untuk menerima update webhook dari Telegram
@app.route("/telegram", methods=["POST"])
async def telegram_webhook():
    global application
    if application is None:
        logging.error("ERROR: Telegram Application belum diinisialisasi.")
        abort(500) # Internal Server Error

    # Ambil update dari request body
    update_json = request.get_json(force=True)
    update = Update.de_json(update_json, application.bot)

    # Proses update secara async
    async with application: # Pastikan application context manager digunakan
        await application.process_update(update)
    
    return "ok"

# Endpoint default untuk health check Render
@app.route("/")
def index():
    return "Bot Telegram Sales Checkin sedang berjalan! Webhook aktif di /telegram."

# Fungsi untuk menginisialisasi bot Telegram (WEBHOOK MODE)
async def initialize_telegram_bot():
    global application
    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    webhook_url = os.environ.get("WEBHOOK_URL") # URL dasar dari Render

    if not telegram_token:
        logging.error("ERROR: Variabel environment 'TELEGRAM_BOT_TOKEN' tidak ditemukan. Bot Telegram tidak dapat dijalankan.")
        return False
    if not webhook_url:
        logging.error("ERROR: Variabel environment 'WEBHOOK_URL' tidak ditemukan. Webhook tidak dapat diatur.")
        return False

    application = Application.builder().token(telegram_token).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("checkin", checkin_command)],
        states={
            NAMA_TOKO: [MessageHandler(filters.TEXT & ~filters.COMMAND, nama_toko)],
            ALAMAT_WILAYAH: [MessageHandler(filters.TEXT & ~filters.COMMAND, alamat_wilayah)],
            LOKASI: [
                MessageHandler(filters.LOCATION, lokasi),
                MessageHandler(filters.TEXT & ~filters.COMMAND, lokasi)
            ],
            JUMLAH_KUNJUNGAN: [MessageHandler(filters.TEXT & ~filters.COMMAND, jumlah_kunjungan)],
        },
        fallbacks=[CommandHandler("cancel", cancel_command)],
    )

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("cancel", cancel_command))

    # Hapus webhook lama jika ada dan set webhook baru
    try:
        # Perhatikan: webhook_url sudah harus menyertakan '/telegram' di akhirnya
        # Jadi tidak perlu menambahkan '/telegram' lagi di sini
        await application.bot.set_webhook(url=webhook_url) 
        logging.info(f"Webhook berhasil diatur ke URL: {webhook_url}")
        return True
    except Exception as e:
        logging.error(f"Gagal mengatur webhook Telegram: {e}")
        return False

# Fungsi untuk menjalankan Flask dan Bot Telegram
def main():
    # Inisialisasi Google Sheets dan Authorized Sales IDs
    logging.info("Menginisialisasi koneksi Google Sheets...")
    if not initialize_google_sheets():
        logging.error("Gagal menginisialisasi Google Sheets. Bot mungkin tidak dapat mencatat data.")
    
    logging.info("Memuat daftar authorized sales IDs...")
    load_authorized_sales_ids()

    # Jalankan inisialisasi bot Telegram secara async dalam event loop baru
    logging.info("Menginisialisasi bot Telegram (webhook mode)...")
    try:
        # Panggil asyncio.run pada fungsi async
        asyncio.run(initialize_telegram_bot())
        logging.info("Inisialisasi bot Telegram selesai. Webhook aktif.")
    except Exception as e:
        logging.error(f"Gagal menginisialisasi bot Telegram (webhook mode): {e}")

    # Jalankan aplikasi Flask
    port = int(os.environ.get("PORT", 5000))
    logging.info(f"Aplikasi Flask dimulai di port {port}...")
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()
