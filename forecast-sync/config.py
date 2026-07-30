import os
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

SF_USERNAME = os.environ["SF_USERNAME"]
SF_PASSWORD = os.environ["SF_PASSWORD"]
SF_REPORT_URL = os.environ.get("SF_REPORT_URL", "https://candelamedical.my.salesforce.com/00OPY00000F4ckP")
FIREBASE_CRED_PATH = os.environ["FIREBASE_CRED_PATH"]
DOWNLOAD_DIR = Path(os.environ.get("DOWNLOAD_DIR", BASE_DIR / "downloads"))
HEADLESS = os.environ.get("HEADLESS", "false").lower() == "true"

STATE_PATH = BASE_DIR / "state" / "state.json"

# Time Frame 필터: From은 고정, To는 최초 2028-12-31에서 시작해 매 실행마다 +30일씩 확장
FROM_FIXED = date(2026, 7, 1)
FIRST_TO = date(2028, 12, 31)
TO_STEP_DAYS = 30

DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
