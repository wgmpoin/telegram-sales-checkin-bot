import logging
import asyncio
from datetime import datetime, timedelta, timezone

from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)

import gspread
from google.oauth2.service_account import Credentials

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Konfigurasi ---
TELEGRAM_TOKEN = "ISI_TOKEN_BOT_MU"
GOOGLE_SHEET_ID = "ISI_ID_SHEET_MU"
AUTHORIZED_SALES_IDS = [123456789, 987654321]  # Ganti dengan user_id yang diizinkan
WEBHOOK_URL = "https://NAMA-RENDER.onrender.com"

# --- Google Sheets ---
worksheet = None
try:
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_file("credentials.json", scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(GOOGLE_SHEET_ID)
    worksheet = sh.sheet1
    logger.info("Google Sheets terhubung.")
except Exception as e:
    logger.error(f"Gagal terhubung ke Google Sheets: {e}")

# --- Telegram Handlers ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Halo! Kirim data dengan format: Nama, 1000000")

async def checkin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Silakan kirim: Nama, jumlah sales. Contoh:\n\nJohn Doe, 5000000")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_full_name = update.effective_user.full_name

    if user_id not in AUTHORIZED_SALES_IDS:
        logger.warning(f"Unauthorized user {user_id} ({user_full_name})")
        await update.message.reply_text("Maaf, Anda tidak memiliki izin untuk menggunakan bot ini.")
        return

    text = update.message.text
    if not text:
        await update.message.reply_text("Pesan kosong tidak valid.")
        return

    try:
        parts = text.split(',')
        if len(parts) != 2:
            raise ValueError("Format tidak sesuai. Contoh: Nama Lengkap, 1000000")

        sales_person_name = pa
