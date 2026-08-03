from datetime import date
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

SF_REPORT_URL = "https://candelamedical.my.salesforce.com/00OPY00000F4ckP"

# Firebase Admin SDK 서비스 계정 키 (2026-08-03 발급, .gitignore의 *firebase-adminsdk*.json
# 패턴으로 저장소에는 올라가지 않음).
FIREBASE_CRED_PATH = BASE_DIR / "sales-dashboard-d0d13-firebase-adminsdk-fbsvc-5d12204580.json"

DOWNLOAD_DIR = BASE_DIR / "downloads"
STATE_PATH = BASE_DIR / "state" / "state.json"

# Salesforce 로그인은 회사 SSO(OS 계정 토큰)로 처리되므로 아이디/비밀번호를 따로 코드에
# 두지 않는다 - RMA/ICBL 자동화와 동일하게 "전용 포트 + 전용 프로필"의 Edge 인스턴스를
# 한 번 띄워두면 이후 실행에서 로그인 없이 리포트가 바로 열린다
# (9333=Oracle/ICBL, 9334=RMA, 9335=forecast-sync - 서로 겹치지 않는 별도 값).
EDGE_DEBUG_PORT = 9335
EDGE_PROFILE_DIR = r"C:\Users\yoongil.chae\.forecast_sync_automation\browser_profile"

# Time Frame 필터: From은 고정, To는 최초 2028-12-31에서 시작해 매 실행마다 +30일씩 확장
FROM_FIXED = date(2026, 7, 1)
FIRST_TO = date(2028, 12, 31)
TO_STEP_DAYS = 30

DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
