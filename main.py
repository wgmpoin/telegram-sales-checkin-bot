import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Konfigurasi logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Token bot Telegram kamu
BOT_TOKEN = '7973184485:AAHSRCxhazoqMm0TTOQ6ZNoiiCYe6UHkGeQ'

# Fungsi saat /start dikirim
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Halo {user_full_name}, selamat datang!")

# Fungsi utama
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.run_polling()

if __name__ == '__main__':
    main()
