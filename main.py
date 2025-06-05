import os
import json
import base64
from google.oauth2.service_account import Credentials
import gspread
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ===== DECODE GCP CREDENTIALS =====
base64_creds = os.getenv("GCP_CREDENTIALS_BASE64")
if not base64_creds:
    raise Exception("GCP_CREDENTIALS_BASE64 environment variable not set")

creds_json = base64.b64decode(base64_creds).decode("utf-8")
creds_dict = json.loads(creds_json)

scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)

# ===== CONNECT TO GOOGLE SHEETS =====
gc = gspread.authorize(credentials)
sheet = gc.open("Checkin Sales").sheet1  # ganti dengan nama spreadsheet kamu

# ===== TELEGRAM BOT SETUP =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise Exception("BOT_TOKEN environment variable not set")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Halo! Kirimkan nama toko untuk check-in.")

async def checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nama_toko = update.message.text
    user_id = update.effective_user.id
    username = update.effective_user.username or "-"
    nama = update.effective_user.full_name

    sheet.append_row([
        str(user_id),
        username,
        nama,
        nama_toko,
        update.message.date.strftime("%Y-%m-%d %H:%M:%S")
    ])

    await update.message.reply_text("✅ Check-in dicatat untuk toko: " + nama_toko)

app = Application.builder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("checkin", checkin))
app.add_handler(CommandHandler("help", start))  # bantuan = /help

app.run_polling()
