import os
import json
import logging
from flask import Flask
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters as tg_filters
)

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- Google Sheets Setup ---
json_creds = os.environ.get("GCP_CREDENTIALS_JSON")
if not json_creds:
    raise Exception("GCP_CREDENTIALS_JSON not found in environment variables.")
creds_dict = json.loads(json_creds)

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open('Checkin Sales').sheet1  # Ganti dengan nama sheet-mu jika berbeda

# --- Flask (untuk jaga-jaga Render butuh web server aktif) ---
app = Flask(__name__)
@app.route('/')
def home():
    return "Bot is running!"

# --- Telegram Bot Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Halo! Silakan ketik nama toko untuk check-in.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    store_name = update.message.text
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Simpan ke Google Sheets
    sheet.append_row([str(user.id), user.first_name, store_name, timestamp])

    await update.message.reply_text(
        f"Check-in disimpan!\nNama toko: {store_name}\nWaktu: {timestamp}"
    )

# --- Bot Entry Point ---
def main():
    TOKEN = os.getenv("BOT_TOKEN")
    if not TOKEN:
        raise Exception("BOT_TOKEN tidak ditemukan di environment variable.")

    app_bot = ApplicationBuilder().token
