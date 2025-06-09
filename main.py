# main.py

import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from fastapi import FastAPI
from starlette.requests import Request
from telegram.ext.webhook import WebhookServer

import os

# Konfigurasi logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Inisialisasi FastAPI
app = FastAPI()

# TOKEN Telegram Anda
TELEGRAM_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"

# Handler command `/start`
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Halo! Bot berhasil dijalankan.")

# Handler untuk pesan biasa
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    await update.message.reply_text(f"Kamu mengirim: {user_message}")

# Jalankan aplikasi Telegram Bot sebagai background task di FastAPI
@app.on_event("startup")
async def startup():
    application = (
        ApplicationBuilder()
        .token(TELEGRAM_TOKEN)
        .build()
    )

    # Tambahkan handler
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Jalankan polling bot
    # Ganti dengan webhook jika dibutuhkan
    await application.initialize()
    await application.start()
    app.bot_app = application

@app.on_event("shutdown")
async def shutdown():
    await app.bot_app.stop()
    await app.bot_app.shutdown()
