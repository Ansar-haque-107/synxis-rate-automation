import os
import datetime
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://controlcenter-p1.synxis.com"
SAVE_URL = f"{BASE_URL}/HMS/manager/Save"
GETRATES_URL = f"{BASE_URL}/HMS/manager/GetRates"
REFERER = f"{BASE_URL}/hms/manager/channel?pageNavId=202391"

# Fresh values required each run — see README for how to capture them.
COOKIE = os.environ["SYNXIS_COOKIE"]
CSRF_TOKEN = os.environ["SYNXIS_CSRF_TOKEN"]

EXCEL_PATH = os.environ.get("SYNXIS_EXCEL_PATH", "Synxis_Rates.xlsx")
SHEET_NAME = "Rates"

EXPORT_START_DATE = datetime.date(2027, 6, 1)
EXPORT_END_DATE = datetime.date(2027, 9, 30)
EXPORT_RATE_CODES: list[str] = []  # empty = export all rate codes

DRY_RUN = True
VERIFY_AFTER_SAVE = True
PUSH_ON_MISMATCH = False
REQUEST_DELAY_SECONDS = 1.0

# Synxis uses relative day IDs instead of real dates — this anchor converts
# between them. Recapture from a live request if a save ever lands on the
# wrong date.
CALENDAR_ANCHOR_DATE = datetime.date(2026, 7, 3)
CALENDAR_ANCHOR_ID = 9546
WINDOW_BACK = 7
WINDOW_FORWARD = 35

# One captured GetRates payload per rate plan you manage (DevTools → Network
# → GetRates → Payload → "view source"). Leave empty to use a minimal
# built-in payload instead.
GETRATES_PAYLOAD_TEMPLATES: list[str] = [
    # r"""{...paste captured payload here...}""",
]
