import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Ganti dengan token asli bot kamu
BOT_TOKEN = '7973184485:AAHSRCxhazoqMm0TTOQ6ZNoiiCYe6UHkGeQ'

# Konfigurasi logging untuk membantu debugging di Render
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Fungsi yang dijalankan saat pengguna mengetik /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_full_name = update.effective_user.full_name
    await update.message.reply_text(f'Halo, {user_full_name}! Bot ini sudah aktif.')

# Inisialisasi aplikasi dan jalankan bot
if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.run_polling()
