import os
import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from flask import Flask, request

# Setup logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- GOOGLE SHEETS SETUP ---
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
import json
import os

from oauth2client.service_account import ServiceAccountCredentials

# Ambil isi credential dari environment variable
json_creds = os.environ.get("GCP_CREDENTIALS_JSON")

# Ubah string JSON ke dictionary
creds_dict = json.loads(json_creds)

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open('Checkin Sales').sheet1  # Ganti nama jika beda

# --- TELEGRAM HANDLER ---
def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text("Halo! Silakan ketik nama toko untuk check-in.")

def handle_message(update: Update, context: CallbackContext) -> None:
    user = update.message.from_user
    store_name = update.message.text
    timestamp = update.message.date.strftime('%Y-%m-%d %H:%M:%S')

    # Simpan ke Google Sheets
    sheet.append_row([str(user.id), user.first_name, store_name, timestamp])

    update.message.reply_text(f"Check-in disimpan!\nNama toko: {store_name}\nWaktu: {timestamp}")

# --- MAIN ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def main():
    TOKEN = os.getenv("BOT_TOKEN")
    updater = Updater(TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
