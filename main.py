# main.py

from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
)
import asyncio
import os

# Ganti dengan token bot Anda
BOT_TOKEN = os.getenv("BOT_TOKEN", "ISI_TOKEN_BOT_ANDA")
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"https://yourdomain.com{WEBHOOK_PATH}"  # Ganti yourdomain.com sesuai URL Anda

app = FastAPI()
telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()

# Handler untuk /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Halo! Bot sudah aktif.")

# Tambahkan handler ke aplikasi Telegram
telegram_app.add_handler(CommandHandler("start", start))

# Endpoint webhook untuk menerima update dari Telegram
@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    update_dict = await request.json()
    update = Update.de_json(update_dict, telegram_app.bot)
    await telegram_app.process_update(update)
    return {"ok": True}

# Fungsi startup untuk mengatur webhook ke Telegram
@app.on_event("startup")
async def on_startup():
    await telegram_app.bot.set_webhook(WEBHOOK_URL)

# Fungsi shutdown untuk membersihkan webhook
@app.on_event("shutdown")
async def on_shutdown():
    await telegram_app.bot.delete_webhook()
