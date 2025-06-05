import os
import json
import base64
import logging
from flask import Flask
from google.oauth2 import service_account
import gspread
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Konfigurasi logging
logging.basicConfig(level=logging.INFO)

# === Ambil kredensial dari environment dan decode ===
base64_creds = os.environ.get("GCP_CREDENTIALS_BASE64")
if not base64_creds:
    raise Exception("GCP_CREDENTIALS_BASE64 not set")

creds_json = base64.b64decode(base64_creds).decode("utf-8")
creds_dict = json.loads(creds_json)

# Setup Google Sheets client
scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
credentials = service_account.Credentials.from_service_account_info(
    creds_dict, scopes=scopes
)
gc = gspread.authorize(credentials)
sheet = gc.open("Checkin Sales").sheet1

# === Bot Telegram ===
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    raise Exception("TELEGRAM_TOKEN not set")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot aktif. Silakan kirim perintah check-in.")

# Setup Flask untuk healthcheck (dibutuhkan Render)
app = Flask(__name__)

@app.route("/")
def index():
    return "Bot aktif!"

# Jalankan bot Telegram
if __name__ == "__main__":
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.run_polling()
