import base64
import json

# Ambil isi base64 dari environment
encoded = os.getenv("GCP_CREDENTIALS_BASE64")

if not encoded:
    raise Exception("GCP_CREDENTIALS_BASE64 not set")

# Decode dan simpan ke file
decoded = base64.b64decode(encoded)
with open("service_account.json", "wb") as f:
    f.write(decoded)
    
import os
import json
import base64
import logging
import gspread
from flask import Flask
from datetime import datetime
from google.oauth2 import service_account
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters as tg_filters
)

# Logging setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Flask route (for Render keep-alive)
app = Flask(__name__)
@app.route('/')
def home():
    return "Bot is running!"

# Load and decode base64 Google credentials
base64_creds = os.environ.get("GCP_CREDENTIALS_BASE64")
if not base64_creds:
    raise Exception("GCP_CREDENTIALS_BASE64 not found in environment!")

json_str = base64.b64decode(base64_creds).decode("utf-8")
creds_dict = json.loads(json_str)

# Use google-auth (not oauth2client)
scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
credentials = service_account.Credentials.from_service_account_file("service_account.json", scopes=scopes)
client = gspread.authorize(credentials)
sheet = client.open('Checkin Sales').sheet1

# Telegram Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Halo! Silakan ketik nama toko untuk check-in.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    store_name = update.message.text
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    sheet.append_row([str(user.id), user.first_name, store_name, timestamp])
    await update.message.reply_text(f"Check-in disimpan!\nNama toko: {store_name}\nWaktu: {timestamp}")

# Main bot function
def main():
    TOKEN = os.environ.get("BOT_TOKEN")
    if not TOKEN:
        raise Exception("BOT_TOKEN environment variable not found!")

    app_bot = ApplicationBuilder().token(TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(MessageHandler(tg_filters.TEXT & ~tg_filters.COMMAND, handle_message))

    print("Bot started...")
    app_bot.run_polling()

if __name__ == '__main__':
    main()
