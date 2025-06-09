import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# Konfigurasi logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Ganti dengan token bot kamu
BOT_TOKEN = 'YOUR_BOT_TOKEN'

# Ganti dengan ID channel kamu, format: '@nama_channel' atau ID negatif seperti -1001234567890
CHANNEL_ID = '@nama_channel_kamu'

# Command /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Halo! Kirim pesan apa pun, dan saya akan teruskan ke channel.")

# Handler untuk semua pesan
async def forward_to_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    await context.bot.send_message(chat_id=CHANNEL_ID, text=text)
    await update.message.reply_text("Pesanmu sudah dikirim ke channel.")

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), forward_to_channel))

    print("Bot berjalan...")
    app.run_polling()
