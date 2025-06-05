import os
import json
import logging
from flask import Flask
from google.oauth2 import service_account
import gspread

logging.basicConfig(level=logging.INFO)

# Load credentials from ENV and convert to dict
creds_raw = os.environ.get("GCP_CREDENTIALS_BASE64")
creds_dict = json.loads(creds_raw)

# Convert \\n to \n in private_key
creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")

# Define scopes and credentials
scopes = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = service_account.Credentials.from_service_account_info(creds_dict, scopes=scopes)

# Connect to Google Sheets
gc = gspread.authorize(credentials)
sheet = gc.open("Nama Spreadsheet Anda").sheet1  # Ubah sesuai nama spreadsheet Anda

# Simple Flask app
app = Flask(__name__)

@app.route("/")
def index():
    return "Bot is running!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
