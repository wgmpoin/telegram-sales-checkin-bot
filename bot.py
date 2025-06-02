import os
import logging
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, ConversationHandler

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# State definitions for ConversationHandler
NAMA_TOKO, ALAMAT, GPS = range(3)

# Load Google Sheets creds from environment variable JSON string
import json
creds_json = os.environ.get('GOOGLE_CREDS_JSON')
if not creds_json:
    raise Exception("Google credentials not found in env variable 'GOOGLE_CREDS_JSON'")
creds_dict = json.loads(creds_json)

scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
credentials = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
gc = gspread.authorize(credentials)

# Open your Google Sheet by name
SPREADSHEET_NAME = os.environ.get('SPREADSHEET_NAME', 'SalesCheckin')
sheet = gc.open(SPREADSHEET_NAME).sheet1

# Store sales Telegram IDs who can use bot (for simplicity, read from env)
AUTHORIZED_SALES = os.environ.get('AUTHORIZED_SALES', '')
AUTHORIZED_SALES_IDS = [int(x.strip()) for x in AUTHORIZED_SALES.split(',') if x.strip()]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in AUTHORIZED_SALES_IDS:
        await update.message.reply_text("Maaf, Anda tidak terdaftar sebagai sales.")
        return ConversationHandler.END

    await update.message.reply_text(
        "Halo Sales! Silakan ketik nama toko yang ingin Anda check-in."
    )
    return NAMA_TOKO

async def nama_toko(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['nama_toko'] = update.message.text
    await update.message.reply_text("Masukkan alamat/wilayah toko (bisa kota, kecamatan, jalan, dsb):")
    return ALAMAT

async def alamat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['alamat'] = update.message.text
    await update.message.reply_text("Kirimkan lokasi GPS toko dengan fitur 'Share Location' Telegram:")
    return GPS

async def gps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.location is None:
        await update.message.reply_text("Tolong kirim lokasi GPS dengan benar (gunakan fitur 'Share Location').")
        return GPS

    lokasi = update.message.location
    latitude = lokasi.latitude
    longitude = lokasi.longitude
    lokasi_link = f"https://maps.google.com/?q={latitude},{longitude}"

    user_data = context.user_data
    nama_toko = user_data['nama_toko']
    alamat = user_data['alamat']

    now = datetime.now()
    tanggal = now.strftime("%Y-%m-%d")
    waktu = now.strftime("%H:%M:%S")

    # Hitung berapa kali sudah dikunjungi bulan ini
    all_records = sheet.get_all_records()
    bulan_ini = now.strftime("%Y-%m")
    kunjungan_bulan_ini = 0
    for row in all_records:
        # Format tanggal di sheet harus yyyy-mm-dd
        if row['Nama Toko'] == nama_toko and row['Tanggal'].startswith(bulan_ini):
            kunjungan_bulan_ini += 1

    # Masukkan data baru
    sheet.append_row([
        nama_toko,
        alamat,
        tanggal,
        waktu,
        lokasi_link,
        kunjungan_bulan_ini + 1
    ])

    await update.message.reply_text(
        f"Check-in berhasil untuk toko *{nama_toko}*.\n"
        f"Alamat: {alamat}\n"
        f"Tanggal: {tanggal}\n"
        f"Waktu: {waktu}\n"
        f"Lokasi: {lokasi_link}\n"
        f"Ini adalah kunjungan ke-{kunjungan_bulan_ini + 1} Anda bulan ini.",
        parse_mode='Markdown'
    )

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Check-in dibatalkan.")
    return ConversationHandler.END

def main():
    TOKEN = os.environ.get('TELEGRAM_TOKEN')
    if not TOKEN:
        raise Exception("Token Telegram tidak ditemukan di environment variable 'TELEGRAM_TOKEN'")

    application = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            NAMA_TOKO: [MessageHandler(filters.TEXT & ~filters.COMMAND, nama_toko)],
            ALAMAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, alamat)],
            GPS: [MessageHandler(filters.LOCATION, gps)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(conv_handler)

    print("Bot started...")
    application.run_polling()

if __name__ == '__main__':
    main()