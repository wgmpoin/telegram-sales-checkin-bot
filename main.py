import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Konfigurasi logging untuk memantau aktivitas bot
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Ganti dengan token bot Telegram kamu
BOT_TOKEN = '7973184485:AAHSRCxhazoqMm0TTOQ6ZNoiiCYe6UHkGeQ'

# Fungsi saat pengguna kirim /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_full_name = update.effective_user.full_name
    await update.message.reply_text(f"Halo {user_full_name}, selamat datang!")

# Fungsi utama untuk menjalankan bot
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.run_polling()

# Menjalankan fungsi utama saat file dieksekusi
if __name__ == '__main__':
    main()
