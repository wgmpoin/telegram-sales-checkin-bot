import logging
import os
import asyncio
from datetime import datetime, timedelta, timezone

from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters
)

import gspread
from google.oauth2.service_account import Credentials

# --- Konfigurasi Logging ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Load ENV Variables ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GOOGLE_SHEET_ID = os.environ.get("GOOGLE_SHEET_ID")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
AUTHORIZED_IDS = os.environ.get("AUTHORIZED_SALES_IDS", "")
authorized_sales_ids = list(map(int, AUTHORIZED_IDS.split(','))) if AUTHORIZED_IDS else []

# --- Setup Google Sheets ---
worksheet = None
try:
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_file("credentials.json", scopes=scopes)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(GOOGLE_SHEET_ID)
    worksheet = spreadsheet.sheet1
    logger.info("Google Sheet berhasil terhubung.")
except Exception as e:
    logger.error(f"Gagal menghubungkan ke Google Sheets: {e}")

# --- Setup Telegram Bot ---
application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

# --- Command Handlers ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Selamat datang! Kirim pesan dengan format:\n`Nama Lengkap, 1000000`", parse_mode="Markdown")

async def checkin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Silakan kirim nama dan jumlah sales:\nContoh: `Nama Lengkap, 1000000`", parse_mode="Markdown")

# --- Message Handler ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_T
