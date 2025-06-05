main.py

import os import base64 import json import logging

from flask import Flask from telegram import Update from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters from google.oauth2 import service_account import gspread

====== Setup Logging ======

logging.basicConfig(level=logging.INFO) logger = logging.getLogger(name)

====== Load Google Credentials from base64 ENV ======

creds_b64 = os.getenv("GCP_CREDENTIALS_BASE64") if not creds_b64: raise Exception("GCP_CREDENTIALS_BASE64 not set")

creds_dict = json.loads(base64.b64decode(creds_b64).decode("utf-8")) scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"] credentials = service_account.Credentials.from_service_account_info(creds_dict, scopes=scopes)

gc = gspread.authorize(credentials) sheet = gc.open("Checkin Sales").sheet1  # ganti sesuai spreadsheet

====== Setup Bot ======

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") if not BOT_TOKEN: raise Exception("TELEGRAM_BOT_TOKEN not set")

app = Application.builder().token(BOT_TOKEN).build()

====== Bot Handlers ======

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE): await update.message.reply_text("Halo! Kirim nama toko untuk check-in.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE): user = update.effective_user store_name = update.message.text.strip()

# Simpan ke Google Sheets
sheet.append_row([
    user.full_name,
    store_name,
    update.message.date.strftime("%Y-%m-%d %H:%M:%S"),
    str(user.id)
])

await update.message.reply_text(f"Check-in dicatat untuk toko: {store_name}")

====== Flask Webhook ======

flask_app = Flask(name)

@flask_app.route("/") def index(): return "Bot is running!"

====== Register Bot Handlers ======

app.add_handler(CommandHandler("start", start)) app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

====== Run Bot ======

if name == "main": import asyncio asyncio.run(app.run_polling())

