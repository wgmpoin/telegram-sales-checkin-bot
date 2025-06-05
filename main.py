import os
import json
import base64
from google.oauth2 import service_account

# Ambil string BASE64 dari environment
creds_base64 = os.getenv("GCP_CREDENTIALS_BASE64")

# Decode base64 ke JSON
creds_json = base64.b64decode(creds_base64).decode("utf-8")
creds_dict = json.loads(creds_json)

# Fix untuk multiline private_key
if "private_key" in creds_dict:
    creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")

# Buat credentials Google
scopes = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = service_account.Credentials.from_service_account_info(
    creds_dict, scopes=scopes
)
