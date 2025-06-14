import os
import json
import base64
import logging
import sys
import asyncio
import traceback # For more detailed error debugging

# Import Flask
from flask import Flask, request, abort

# Import from python-telegram-bot (version 22.x)
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)
from telegram.error import InvalidToken, TelegramError

from datetime import datetime

# Import for Google Sheets
import gspread
from google.oauth2 import service_account

# --- Logging Configuration ---
# Directing logging to stdout for visibility in Vercel logs
logging.basicConfig(level=logging.INFO, stream=sys.stdout, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

logger.info("Script bot starting up...")

# --- ENVIRONMENT VARIABLES ---
# Retrieve from Vercel Environment Variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
GOOGLE_SERVICE_ACCOUNT_B64 = os.getenv("GOOGLE_SERVICE_ACCOUNT")
VERCEL_URL = os.getenv("VERCEL_URL") # Vercel automatically provides this variable

# --- GOOGLE SHEET TAB NAMES ---
TAB_NAME_CHECKIN = "Sheet1" # Sheet name for check-in data
AUTHORIZED_USERS_TAB_NAME = "AUTHORIZED_USERS" # Sheet name for authorized sales list

# Global variables for Google Sheets connection
gc = None
worksheet_checkin_data = None
worksheet_authorized_users = None

# Global variable for the Application instance
application = None

# --- Initialize Google Sheets ---
async def initialize_google_sheets():
    """Initializes Google Sheets connection."""
    global gc, worksheet_checkin_data, worksheet_authorized_users

    if gc and worksheet_checkin_data and worksheet_authorized_users:
        logger.info("Google Sheets already initialized.")
        return

    logger.info("Starting Google Sheets initialization...")
    
    if not GOOGLE_SERVICE_ACCOUNT_B64:
        logger.error("GOOGLE_SERVICE_ACCOUNT (Base64) is not set in environment.")
        raise ValueError("GOOGLE_SERVICE_ACCOUNT (Base64) is not set in environment.")

    logger.info("Attempting to decode Google Service Account credentials...")
    try:
        credentials_json = base64.b64decode(GOOGLE_SERVICE_ACCOUNT_B64).decode("utf-8")
        creds_dict = json.loads(credentials_json)
        logger.info("Credentials successfully decoded.")
    except Exception as e:
        logger.error(f"Error decoding credentials: {e}. Trace: {traceback.format_exc()}")
        raise RuntimeError(f"Failed to decode Google credentials: {e}")

    logger.info("Attempting to authorize gspread...")
    try:
        # Use service_account.Credentials explicitly for Google Auth
        credentials = service_account.Credentials.from_service_account_info(creds_dict, scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive'])
        gc = gspread.authorize(credentials)
        logger.info("gspread authorization successful.")
    except Exception as e:
        logger.error(f"Error authorizing gspread: {e}. Trace: {traceback.format_exc()}")
        raise RuntimeError(f"Failed to authorize gspread: {e}")

    if not SPREADSHEET_ID:
        logger.error("SPREADSHEET_ID is not set in environment.")
        raise ValueError("SPREADSHEET_ID is not set in environment.")

    logger.info(f"Attempting to open spreadsheet with ID: {SPREADSHEET_ID}...")
    try:
        spreadsheet = gc.open_by_key(SPREADSHEET_ID)
        logger.info("Spreadsheet successfully opened.")
    except Exception as e:
        logger.error(f"Error opening spreadsheet: {e}. Trace: {traceback.format_exc()}")
        raise RuntimeError(f"Failed to open spreadsheet: {e}")

    logger.info(f"Attempting to open main data worksheet: {TAB_NAME_CHECKIN}...")
    try:
        worksheet_checkin_data = spreadsheet.worksheet(TAB_NAME_CHECKIN)
        logger.info(f"Worksheet '{TAB_NAME_CHECKIN}' successfully opened.")
    except Exception as e:
        logger.error(f"Error opening worksheet '{TAB_NAME_CHECKIN}': {e}. Trace: {traceback.format_exc()}")
        raise RuntimeError(f"Failed to open worksheet '{TAB_NAME_CHECKIN}': {e}")

    logger.info(f"Attempting to open authorized users worksheet: {AUTHORIZED_USERS_TAB_NAME}...")
    try:
        worksheet_authorized_users = spreadsheet.worksheet(AUTHORIZED_USERS_TAB_NAME)
        logger.info(f"Worksheet '{AUTHORIZED_USERS_TAB_NAME}' successfully opened.")
    except Exception as e:
        logger.error(f"Error opening worksheet '{AUTHORIZED_USERS_TAB_NAME}': {e}. Trace: {traceback.format_exc()}")
        raise RuntimeError(f"Failed to open worksheet '{AUTHORIZED_USERS_TAB_NAME}': {e}")

    logger.info("All Google Sheet connections successfully initialized.")


# --- Initialize Bot Application ---
async def init_application():
    """Initializes the ApplicationBuilder instance and adds handlers."""
    global application

    if application is not None:
        logger.info("Application already initialized.")
        return

    logger.info("Starting Telegram Application initialization...")
    
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is not set in environment.")
        raise ValueError("BOT_TOKEN is not set in environment.")

    try:
        # Use ApplicationBuilder for ptb 22.x
        application = ApplicationBuilder().token(BOT_TOKEN).build()
        logger.info("ApplicationBuilder successfully built.")
    except InvalidToken:
        logger.error("Invalid BOT_TOKEN. Please check your BOT_TOKEN.")
        raise ValueError("Invalid BOT_TOKEN.")
    except Exception as e:
        logger.error(f"Error building ApplicationBuilder: {e}. Trace: {traceback.format_exc()}")
        raise RuntimeError(f"Failed to initialize Telegram bot: {e}")

    # ConversationHandler states
    GET_STORE_NAME, GET_STORE_REGION, GET_LOCATION = range(3)

    # Handlers
    start_handler = CommandHandler("start", start)
    checkin_handler = ConversationHandler(
        entry_points=[CommandHandler("checkin", checkin_start)],
        states={
            GET_STORE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_store_name)],
            GET_STORE_REGION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_store_region)],
            GET_LOCATION: [MessageHandler(filters.LOCATION, receive_location),
                           MessageHandler(filters.TEXT & ~filters.COMMAND, cancel_checkin_text)] # Handle text if location expected
        },
        fallbacks=[CommandHandler("cancel", cancel_checkin),
                   MessageHandler(filters.COMMAND, unknown_command)], # Handle other commands during conversation
        allow_reentry=True # Allow user to restart conversation if interrupted
    )
    unknown_command_handler = MessageHandler(filters.COMMAND, unknown_command) # Handle unknown commands
    unknown_message_handler = MessageHandler(filters.TEXT & ~filters.COMMAND, unknown_message) # Handle unknown text messages

    application.add_handler(start_handler)
    application.add_handler(checkin_handler)
    application.add_handler(unknown_command_handler)
    application.add_handler(unknown_message_handler)

    logger.info("Handlers successfully added.")

    # Initialize Google Sheets after application is built
    await initialize_google_sheets()

    # Set webhook (This will be called every time the function loads, but Telegram API will ignore it if already set)
    if VERCEL_URL:
        webhook_url = f"{VERCEL_URL}/api/webhook"
        logger.info(f"Attempting to set webhook to: {webhook_url}")
        try:
            # Use 'httpx' for aiohttp compatibility in Vercel
            await application.bot.set_webhook(url=webhook_url, allowed_updates=Update.ALL_TYPES)
            logger.info("Webhook successfully set.")
        except TelegramError as e:
            logger.error(f"Error setting webhook: {e}. Trace: {traceback.format_exc()}")
            raise RuntimeError(f"Failed to set webhook: {e}")
        except Exception as e:
            logger.error(f"Unexpected error when setting webhook: {e}. Trace: {traceback.format_exc()}")
            raise RuntimeError(f"Unexpected error when setting webhook: {e}")
    else:
        logger.warning("VERCEL_URL is not set. Webhook will not be set automatically.")


# --- Telegram Bot Functions ---
# All handlers are now async for ptb 22.x

async def get_authorized_sales_list():
    """Retrieves the list of authorized sales usernames from Google Sheet."""
    if worksheet_authorized_users is None:
        logger.error("worksheet_authorized_users not initialized. Cannot fetch sales list.")
        return []

    try:
        # Use asyncio.to_thread for potentially blocking Gspread operations
        all_values = await asyncio.to_thread(worksheet_authorized_users.get_all_values)
        if not all_values:
            logger.warning(f"Sheet '{AUTHORIZED_USERS_TAB_NAME}' is empty or inaccessible.")
            return []

        authorized_sales = [row[0].strip() for row in all_values if row and row[0].strip() and row[0].strip().lower() != 'username']
        logger.info(f"Authorized sales list: {authorized_sales}")
        return authorized_sales
    except Exception as e:
        logger.error(f"Error fetching authorized sales list from sheet: {e}. Trace: {traceback.format_exc()}")
        return []

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Responds to the /start command."""
    user = update.effective_user
    username = user.username or user.first_name # Use first_name if username is not set
    logger.info(f"[{username}] Received /start command")
    await update.message.reply_text("Gunakan /checkin untuk absen.")

async def checkin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts the check-in process and asks for store name."""
    user = update.effective_user
    username = user.username or user.first_name

    logger.info(f"[{username}] Received /checkin command")

    authorized_sales_list = await get_authorized_sales_list() # Call async function

    # Check if username is in the authorized list
    if username not in authorized_sales_list:
        logger.warning(f"[{username}] Unauthorized check-in attempt. Not in list: {authorized_sales_list}")
        await update.message.reply_text("Maaf, Anda tidak diizinkan untuk check-in. Silakan hubungi admin.")
        return ConversationHandler.END # End conversation if not authorized

    context.user_data['username'] = username
    await update.message.reply_text("Baik, silakan masukkan **Nama Toko**:", parse_mode='Markdown')
    logger.info(f"[{username}] Asking for store name.")
    return GET_STORE_NAME # Refers to GET_STORE_NAME state

async def get_store_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives store name and asks for store region."""
    current_username = context.user_data.get('username', 'N/A')
    logger.info(f"[{current_username}] Received store name: '{update.message.text}'")
    context.user_data['store_name'] = update.message.text
    await update.message.reply_text("Sekarang, silakan masukkan **Wilayah Toko**:", parse_mode='Markdown')
    logger.info(f"[{current_username}] Asking for store region.")
    return GET_STORE_REGION # Refers to GET_STORE_REGION state

async def get_store_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives store region and asks for location."""
    current_username = context.user_data.get('username', 'N/A')
    logger.info(f"[{current_username}] Received store region: '{update.message.text}'")
    context.user_data['store_region'] = update.message.text
    
    keyboard = [[KeyboardButton("Bagikan Lokasi Saya", request_location=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

    await update.message.reply_text(
        "Terima kasih. Sekarang, silakan bagikan **Lokasi** Anda dengan menekan tombol di bawah.",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    logger.info(f"[{current_username}] Asking for location.")
    return GET_LOCATION # Refers to GET_LOCATION state

async def receive_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives location and records check-in."""
    current_username = context.user_data.get('username', 'N/A')
    logger.info(f"[{current_username}] Received location.")
    user_location = update.message.location
    username = context.user_data.get('username')
    store_name = context.user_data.get('store_name')
    store_region = context.user_data.get('store_region')

    if not all([username, store_name, store_region]):
        logger.error(f"[{current_username}] Incomplete data for check-in: username={username}, store_name={store_name}, store_region={store_region}")
        await update.message.reply_text("Terjadi kesalahan: Data check-in tidak lengkap. Silakan mulai ulang dengan /checkin.")
        return ConversationHandler.END

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    latitude = user_location.latitude
    longitude = user_location.longitude
    # Corrected Google Maps link - ensure the format is right
    Maps_link = f"https://www.google.com/maps?q={latitude},{longitude}"

    data_to_write = [
        timestamp,
        username,
        store_name,
        store_region,
        latitude,
        longitude,
        Maps_link
    ]

    try:
        # Use asyncio.to_thread for potentially blocking Gspread operations
        await asyncio.to_thread(worksheet_checkin_data.append_row, data_to_write)
        logger.info(f"[{current_username}] Check-in successfully recorded to Google Sheet: {data_to_write}")
        await update.message.reply_text(
            f"Terima kasih, **{username}**!\n\n"
            f"Anda telah berhasil check-in di **{store_name}** ({store_region}).\n"
            f"Lokasi Anda: [Lihat di Google Maps]({Maps_link})",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"[{current_username}] Error writing to Google Sheet: {e}. Data: {data_to_write}. Trace: {traceback.format_exc()}")
        await update.message.reply_text("Maaf, terjadi kesalahan saat mencatat check-in Anda. Silakan coba lagi nanti.")

    context.user_data.clear() # Clear user data after check-in is complete
    return ConversationHandler.END

async def cancel_checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancels the check-in process."""
    current_username = context.user_data.get('username', 'N/A')
    logger.info(f"[{current_username}] Check-in process cancelled.")
    await update.message.reply_text("Proses check-in dibatalkan. Anda bisa mulai lagi dengan /checkin.")
    context.user_data.clear()
    return ConversationHandler.END

async def cancel_checkin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for text when location is expected, will cancel check-in."""
    current_username = context.user_data.get('username', 'N/A')
    logger.info(f"[{current_username}] Received text '{update.message.text}' when location was expected. Cancelling check-in.")
    await update.message.reply_text("Anda mengirim teks alih-alih lokasi. Proses check-in dibatalkan. Silakan mulai lagi dengan /checkin.")
    context.user_data.clear()
    return ConversationHandler.END


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Responds to unknown commands."""
    user = update.effective_user
    username = user.username or user.first_name
    logger.warning(f"[{username}] Received unknown command: {update.message.text}")
    await update.message.reply_text("Maaf, perintah itu tidak dikenal. Gunakan /checkin untuk memulai absen atau /cancel untuk membatalkan.")

async def unknown_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Responds to unknown text messages (not commands)."""
    user = update.effective_user
    username = user.username or user.first_name
    logger.info(f"[{username}] Received unknown message: '{update.message.text}'")
    # Only reply if not part of an active conversation handler
    if context.in_conversation:
        pass # Let the conversation handler manage it
    else:
        await update.message.reply_text("Maaf, saya tidak mengerti pesan Anda. Gunakan /start untuk memulai atau /checkin untuk absen.")


# --- Flask App for Vercel ---
app = Flask(__name__)

@app.route('/api/webhook', methods=['POST'])
async def webhook_handler():
    """Endpoint to receive updates from Telegram."""
    global application

    # Ensure the bot and Google Sheets connections are initialized
    # This will run on every cold start of the serverless function
    if application is None:
        try:
            await init_application()
            logger.info("Application and Google Sheets successfully initialized during runtime.")
        except Exception as e:
            logger.error(f"Fatal error during initial application setup: {e}. Trace: {traceback.format_exc()}")
            # Important: Return a response indicating a server error
            return {"error": "Internal server error during setup"}, 500

    if request.method == "POST":
        update_json = request.get_json(force=True)
        if not update_json:
            logger.warning("Received empty JSON from webhook.")
            return "No JSON received", 200 # Telegram expects 200 OK even for empty updates
        
        try:
            update = Update.de_json(update_json, application.bot)
            await application.process_update(update)
            logger.info(f"Processed update from Telegram: {update_json.get('update_id')}")
        except TelegramError as e:
            logger.error(f"Error processing Telegram update: {e}. Update: {update_json}. Trace: {traceback.format_exc()}")
            return "Telegram error", 200 # Telegram expects 200 even on some errors
        except Exception as e:
            logger.error(f"Unexpected error processing update: {e}. Update: {update_json}. Trace: {traceback.format_exc()}")
            return {"error": "Internal server error processing update"}, 500
        
        return "ok", 200 # Telegram expects 'ok' or 200 OK
    else:
        # Handle non-POST requests (e.g., GET from browser)
        logger.warning(f"Received non-POST request to webhook: {request.method}")
        return "Please use POST requests for the webhook.", 405

# --- Important for Vercel: No if __name__ == "__main__": app.run() ---