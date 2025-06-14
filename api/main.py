import os
import json
import base64
import logging
import sys
import asyncio
import traceback # Untuk debugging error lebih detail

# Import Flask
from flask import Flask, request, abort

# Import dari python-telegram-bot
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, ConversationHandler, filters
from telegram.error import InvalidToken, TelegramError # Tambahkan TelegramError

from datetime import datetime

# --- Konfigurasi Logging ---
# Mengarahkan logging ke stdout agar terlihat di Vercel logs
logging.basicConfig(level=logging.INFO, stream=sys.stdout, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

logger.info("Script bot starting up...")

# --- ENVIRONMENT VARIABLES ---
# Ambil dari Environment Variables Vercel
BOT_TOKEN = os.getenv("BOT_TOKEN")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
GOOGLE_SERVICE_ACCOUNT_B64 = os.getenv("GOOGLE_SERVICE_ACCOUNT")
VERCEL_URL = os.getenv("VERCEL_URL") # Vercel secara otomatis menyediakan variabel ini

# --- GOOGLE SHEET TAB NAMES ---
TAB_NAME_CHECKIN = "Sheet1" # Nama sheet untuk data check-in
AUTHORIZED_USERS_TAB_NAME = "AUTHORIZED_USERS" # Nama sheet untuk daftar sales yang diotorisasi

# Global variables untuk koneksi Google Sheets
gc = None
worksheet_checkin_data = None
worksheet_authorized_users = None

# Global variable untuk instance Application
application = None

# --- Inisialisasi Google Sheets ---
async def initialize_google_sheets():
    """Menginisialisasi koneksi Google Sheets."""
    global gc, worksheet_checkin_data, worksheet_authorized_users

    if gc and worksheet_checkin_data and worksheet_authorized_users:
        logger.info("Google Sheets sudah diinisialisasi.")
        return

    logger.info("Memulai inisialisasi Google Sheets...")
    
    if not GOOGLE_SERVICE_ACCOUNT_B64:
        logger.error("GOOGLE_SERVICE_ACCOUNT (Base64) belum diatur di environment.")
        raise ValueError("GOOGLE_SERVICE_ACCOUNT (Base64) belum diatur di environment")

    logger.info("Mencoba mendekode kredensial Google Service Account...")
    try:
        credentials_json = base64.b64decode(GOOGLE_SERVICE_ACCOUNT_B64).decode("utf-8")
        creds_dict = json.loads(credentials_json)
        logger.info("Kredensial berhasil didekode.")
    except Exception as e:
        logger.error(f"Error saat mendekode kredensial: {e}. Trace: {traceback.format_exc()}")
        raise RuntimeError(f"Gagal mendekode kredensial Google: {e}")

    logger.info("Mencoba mengotorisasi gspread...")
    try:
        import gspread # Import gspread di sini juga untuk memastikan
        gc = gspread.service_account_from_dict(creds_dict)
        logger.info("Otorisasi gspread berhasil.")
    except Exception as e:
        logger.error(f"Error saat otorisasi gspread: {e}. Trace: {traceback.format_exc()}")
        raise RuntimeError(f"Gagal otorisasi gspread: {e}")

    if not SPREADSHEET_ID:
        logger.error("SPREADSHEET_ID belum diatur di environment.")
        raise ValueError("SPREADSHEET_ID belum diatur di environment")

    logger.info(f"Mencoba membuka spreadsheet dengan ID: {SPREADSHEET_ID}...")
    try:
        spreadsheet = gc.open_by_key(SPREADSHEET_ID)
        logger.info("Spreadsheet berhasil dibuka.")
    except Exception as e:
        logger.error(f"Error saat membuka spreadsheet: {e}. Trace: {traceback.format_exc()}")
        raise RuntimeError(f"Gagal membuka spreadsheet: {e}")

    logger.info(f"Mencoba membuka worksheet data utama: {TAB_NAME_CHECKIN}...")
    try:
        worksheet_checkin_data = spreadsheet.worksheet(TAB_NAME_CHECKIN)
        logger.info(f"Worksheet '{TAB_NAME_CHECKIN}' berhasil dibuka.")
    except Exception as e:
        logger.error(f"Error saat membuka worksheet '{TAB_NAME_CHECKIN}': {e}. Trace: {traceback.format_exc()}")
        raise RuntimeError(f"Gagal membuka worksheet '{TAB_NAME_CHECKIN}': {e}")

    logger.info(f"Mencoba membuka worksheet pengguna yang diotorisasi: {AUTHORIZED_USERS_TAB_NAME}...")
    try:
        worksheet_authorized_users = spreadsheet.worksheet(AUTHORIZED_USERS_TAB_NAME)
        logger.info(f"Worksheet '{AUTHORIZED_USERS_TAB_NAME}' berhasil dibuka.")
    except Exception as e:
        logger.error(f"Error saat membuka worksheet '{AUTHORIZED_USERS_TAB_NAME}': {e}. Trace: {traceback.format_exc()}")
        raise RuntimeError(f"Gagal membuka worksheet '{AUTHORIZED_USERS_TAB_NAME}': {e}")

    logger.info("Semua koneksi Google Sheet berhasil diinisialisasi.")


# --- Inisialisasi Aplikasi Bot ---
async def init_application():
    """Menginisialisasi instance ApplicationBuilder dan menambahkan handlers."""
    global application

    if application is not None:
        logger.info("Application sudah diinisialisasi.")
        return

    logger.info("Memulai inisialisasi Telegram Application...")
    
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN belum diatur di environment.")
        raise ValueError("BOT_TOKEN belum diatur di environment")

    try:
        application = ApplicationBuilder().token(BOT_TOKEN).build()
        logger.info("ApplicationBuilder berhasil dibangun.")
    except InvalidToken:
        logger.error("BOT_TOKEN tidak valid. Periksa BOT_TOKEN Anda.")
        raise ValueError("BOT_TOKEN tidak valid")
    except Exception as e:
        logger.error(f"Error saat membangun ApplicationBuilder: {e}. Trace: {traceback.format_exc()}")
        raise RuntimeError(f"Gagal menginisialisasi bot Telegram: {e}")

    # ConversationHandler states
    GET_STORE_NAME, GET_STORE_REGION, GET_LOCATION = range(3)

    # Handlers
    start_handler = CommandHandler("start", start)
    checkin_handler = ConversationHandler(
        entry_points=[CommandHandler("checkin", checkin_start)],
        states={
            GET_STORE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_store_name)],
            GET_STORE_REGION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_store_region)],
            GET_LOCATION: [MessageHandler(filters.LOCATION, receive_location),
                           MessageHandler(filters.TEXT & ~filters.COMMAND, cancel_checkin)] # Mencegah hang jika user kirim teks
        },
        fallbacks=[CommandHandler("cancel", cancel_checkin),
                   MessageHandler(filters.COMMAND, unknown)], # Tangani command lain saat conversation
        allow_reentry=True # Izinkan user memulai conversation lagi jika terhenti
    )
    unknown_handler = MessageHandler(filters.COMMAND, unknown) # Tangani command yang tidak dikenal

    application.add_handler(start_handler)
    application.add_handler(checkin_handler)
    application.add_handler(unknown_handler)

    logger.info("Handlers berhasil ditambahkan.")

    # Inisialisasi Google Sheets setelah application dibangun
    await initialize_google_sheets()

    # Set webhook (Ini akan dipanggil setiap kali fungsi di-load, tapi Telegram API akan mengabaikannya jika sudah sama)
    if VERCEL_URL:
        webhook_url = f"{VERCEL_URL}/api/webhook"
        logger.info(f"Mencoba menyetel webhook ke: {webhook_url}")
        try:
            await application.bot.set_webhook(url=webhook_url)
            logger.info("Webhook berhasil disetel.")
        except TelegramError as e:
            logger.error(f"Error saat menyetel webhook: {e}. Trace: {traceback.format_exc()}")
            # Ini bisa terjadi jika token tidak valid atau URL tidak bisa dijangkau dari Telegram
            raise RuntimeError(f"Gagal menyetel webhook: {e}")
        except Exception as e:
            logger.error(f"Unexpected error when setting webhook: {e}. Trace: {traceback.format_exc()}")
            raise RuntimeError(f"Unexpected error when setting webhook: {e}")
    else:
        logger.warning("VERCEL_URL tidak diatur. Webhook tidak akan disetel secara otomatis.")


# --- Fungsi-fungsi Bot Telegram ---

async def get_authorized_sales_list():
    """Mengambil daftar username sales yang diotorisasi dari Google Sheet."""
    if worksheet_authorized_users is None:
        logger.error("worksheet_authorized_users belum diinisialisasi. Tidak dapat mengambil daftar sales.")
        return []

    try:
        all_values = worksheet_authorized_users.get_all_values()
        if not all_values:
            logger.warning(f"Sheet '{AUTHORIZED_USERS_TAB_NAME}' kosong atau tidak dapat diakses.")
            return []

        authorized_sales = [row[0].strip() for row in all_values if row and row[0].strip() and row[0].strip() != 'Username']
        logger.info(f"Daftar sales yang diotorisasi: {authorized_sales}")
        return authorized_sales
    except Exception as e:
        logger.error(f"Error saat mengambil daftar sales yang diotorisasi dari sheet: {e}. Trace: {traceback.format_exc()}")
        return []

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menanggapi perintah /start."""
    user = update.effective_user
    username = user.username or user.first_name # Gunakan first_name jika username tidak ada
    logger.info(f"[{username}] Menerima perintah /start")
    await update.message.reply_text("Gunakan /checkin untuk absen.")

async def checkin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Memulai proses check-in dan meminta nama toko."""
    user = update.effective_user
    username = user.username or user.first_name

    logger.info(f"[{username}] Menerima perintah /checkin")

    authorized_sales_list = await get_authorized_sales_list()

    # Periksa apakah username ada dalam daftar yang diotorisasi
    if username not in authorized_sales_list:
        logger.warning(f"[{username}] Percobaan check-in tidak sah. Bukan dalam daftar: {authorized_sales_list}")
        await update.message.reply_text("Maaf, Anda tidak diizinkan untuk check-in. Silakan hubungi admin.")
        return ConversationHandler.END # Akhiri percakapan jika tidak diotorisasi

    context.user_data['username'] = username
    await update.message.reply_text("Baik, silakan masukkan **Nama Toko**:", parse_mode='Markdown')
    logger.info(f"[{username}] Meminta nama toko.")
    return 1 # Mengacu ke GET_STORE_NAME

async def get_store_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menerima nama toko dan meminta wilayah toko."""
    current_username = context.user_data.get('username', 'N/A')
    logger.info(f"[{current_username}] Menerima nama toko: '{update.message.text}'")
    context.user_data['store_name'] = update.message.text
    await update.message.reply_text("Sekarang, silakan masukkan **Wilayah Toko**:", parse_mode='Markdown')
    logger.info(f"[{current_username}] Meminta wilayah toko.")
    return 2 # Mengacu ke GET_STORE_REGION

async def get_store_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menerima wilayah toko dan meminta lokasi."""
    current_username = context.user_data.get('username', 'N/A')
    logger.info(f"[{current_username}] Menerima wilayah toko: '{update.message.text}'")
    context.user_data['store_region'] = update.message.text
    
    keyboard = [[KeyboardButton("Bagikan Lokasi Saya", request_location=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

    await update.message.reply_text(
        "Terima kasih. Sekarang, silakan bagikan **Lokasi** Anda dengan menekan tombol di bawah.",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    logger.info(f"[{current_username}] Meminta lokasi.")
    return 3 # Mengacu ke GET_LOCATION

async def receive_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menerima lokasi dan mencatat check-in."""
    current_username = context.user_data.get('username', 'N/A')
    logger.info(f"[{current_username}] Menerima lokasi.")
    user_location = update.message.location
    username = context.user_data.get('username')
    store_name = context.user_data.get('store_name')
    store_region = context.user_data.get('store_region')

    if not all([username, store_name, store_region]):
        logger.error(f"[{current_username}] Data tidak lengkap untuk check-in: username={username}, store_name={store_name}, store_region={store_region}")
        await update.message.reply_text("Terjadi kesalahan: Data check-in tidak lengkap. Silakan mulai ulang dengan /checkin.")
        return ConversationHandler.END

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    latitude = user_location.latitude
    longitude = user_location.longitude
    Maps_link = f"https://www.google.com/maps/search/?api=1&query={latitude},{longitude}"

    data_to_write = [
        timestamp,
        username,
        store_name,
        store_region,
        latitude,
        longitude,
        Maps_link
    ]

    try:
        await asyncio.to_thread(worksheet_checkin_data.append_row, data_to_write)
        logger.info(f"[{current_username}] Check-in berhasil dicatat ke Google Sheet: {data_to_write}")
        await update.message.reply_text(
            f"Terima kasih, **{username}**!\n\n"
            f"Anda telah berhasil check-in di **{store_name}** ({store_region}).\n"
            f"Lokasi Anda: [Lihat di Google Maps]({Maps_link})",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"[{current_username}] Error saat menulis ke Google Sheet: {e}. Data: {data_to_write}. Trace: {traceback.format_exc()}")
        await update.message.reply_text("Maaf, terjadi kesalahan saat mencatat check-in Anda. Silakan coba lagi nanti.")

    context.user_data.clear() # Bersihkan data pengguna setelah check-in selesai
    return ConversationHandler.END

async def cancel_checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Membatalkan proses check-in."""
    current_username = context.user_data.get('username', 'N/A')
    logger.info(f"[{current_username}] Proses check-in dibatalkan.")
    await update.message.reply_text("Proses check-in dibatalkan. Anda bisa mulai lagi dengan /checkin.")
    context.user_data.clear()
    return ConversationHandler.END

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menanggapi perintah yang tidak dikenal."""
    user = update.effective_user
    username = user.username or user.first_name
    logger.warning(f"[{username}] Menerima perintah tidak dikenal: {update.message.text}")
    await update.message.reply_text("Maaf, perintah itu tidak dikenal. Gunakan /checkin untuk memulai absen atau /cancel untuk membatalkan.")


# --- Flask App untuk Vercel ---
app = Flask(__name__)

@app.route('/api/webhook', methods=['POST'])
async def webhook_handler():
    """Endpoint untuk menerima update dari Telegram."""
    global application

    # Pastikan aplikasi dan koneksi Google Sheets sudah diinisialisasi
    if application is None:
        try:
            await init_application()
            logger.info("Application dan Google Sheets berhasil diinisialisasi saat runtime.")
        except Exception as