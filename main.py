import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Set up logging (optional tapi disarankan)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Ganti dengan token bot kamu
BOT_TOKEN = 'YOUR_TELEGRAM_BOT_TOKEN_HERE'

# Contoh command handler /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Halo! Bot aktif.")

# Fungsi utama
def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Tambahkan handler command
    application.add_handler(CommandHandler("start", start))

    # Jalankan bot dengan polling
    application.run_polling()

# Hanya dijalankan kalau file ini dipanggil langsung
if __name__ == '__main__':
    main()
