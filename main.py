import os
import base64
import json
from datetime import datetime
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
import gspread
from google.oauth2.service_account import Credentials

# === Setup Google Sheets credentials ===
encoded = os.environ.get("GCP_CREDENTIALS_BASE64")
if not encoded:
    raise Exception("GCP_CREDENTIALS_BASE64 is not set")

json_str = base64.b64decode(encoded).decode("utf-8")
creds_dict = json.loads(json_str)

scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
gc = gspread.authorize(credentials)

# === Open Spreadsheet ===
sheet = gc.open("Checkin Sales").sheet1  # Ganti dengan nama spreadsheet kamu

# === Telegram Bot ===
BOT_TOKEN = os.environ.get("BOT_TOKEN")

app = Flask(__name__)

# Simpan sementara nama toko dari user
user_states = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Halo! Gunakan /checkin untuk mulai check-in.")

async def checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_states[update.effective_user.id] = "awaiting_store_name"
    await update.message.reply_text("Silakan kirim nama toko yang kamu kunjungi.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_states.get(user_id) == "awaiting_store_name":
        store_name = update.message.text.strip()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        user_name = update.effective_user.full_name
        sheet.append_row([user_name, str(user_id), store_name, timestamp])
        user_states[user_id] = None
        await update.message.reply_text(f"Check-in untuk *{store_name}* berhasil dicatat.", parse_mode="Markdown")

# Start bot
telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("checkin", checkin))
telegram_app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

# Run Flask for uptime ping
@app.route("/")
def index():
    return "Bot is running!"

if __name__ == "__main__":
    import threading
    threading.Thread(target=telegram_app.run_polling, daemon=True).start()
    app.run(host="0.0.0.0", port=8000)
