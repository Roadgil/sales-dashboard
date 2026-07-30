import hashlib
from datetime import datetime

import pandas as pd

from member_map import OWNER_TO_MEMBER, OWNER_TO_TEAM

# 메인 시스템 라인의 Product Code -> 참고용 DCD/ACC 힌트 (최종 Acc type 필드 포맷과는 다름 - 수기 확정 필요)
MAIN_PRODUCT_CODES = {
    "PTO103577": "DCD",
    "PTO103576": "ACC",
}


def parse_report(xls_path):
    """Salesforce에서 export한 .xls(실제로는 HTML 표) 파일을 읽어 DataFrame으로 반환."""
    tables = pd.read_html(xls_path)
    return tables[0]


def compute_quarter(d):
    q = (d.month - 1) // 3 + 1
    return f"{d.year} Q{q}"


def make_doc_id(owner, opportunity_name, product_code):
    key = f"{owner}|{opportunity_name}|{product_code}"
    return "sfimport_" + hashlib.md5(key.encode("utf-8")).hexdigest()


def build_candidates(df, prev_to, new_to, from_fixed):
    """
    df: parse_report()의 결과.
    prev_to / new_to / from_fixed: date 객체. Close Date가 (prev_to, new_to] 구간이면서
    from_fixed 이상인 행만 대상으로 함. Stage(Closed Won 여부)는 가리지 않고 전부 포함 -
    최종 반영 여부/분기/담당자/상태는 대시보드에서 사람이 후보를 클릭해 확정한다.

    반환: (candidates, skipped_unmapped_owners)
    """
    df = df.copy()
    df["_close_date"] = pd.to_datetime(df["Close Date"], format="%Y. %m. %d", errors="coerce").dt.date

    mask_code = df["Product Code"].astype(str).isin(MAIN_PRODUCT_CODES.keys())
    mask_date = (df["_close_date"] > prev_to) & (df["_close_date"] <= new_to) & (df["_close_date"] >= from_fixed)
    rows = df[mask_code & mask_date]

    candidates = []
    skipped_owners = set()
    now_iso = datetime.utcnow().isoformat()

    for _, row in rows.iterrows():
        owner = str(row["Opportunity Owner"]).strip()
        member = OWNER_TO_MEMBER.get(owner)
        team = OWNER_TO_TEAM.get(owner)
        if member is None or team is None:
            skipped_owners.add(owner)
            continue

        product_code = str(row["Product Code"])
        line_type_hint = MAIN_PRODUCT_CODES[product_code]
        close_date = row["_close_date"]

        so_num = row.get("Oracle Sales Order Number")
        so_str = "" if pd.isna(so_num) else str(int(so_num))

        price_krw = row.get("Total Price")
        price_krw = 0 if pd.isna(price_krw) else round(float(price_krw))
        price_usd = row.get("Total Price (converted)")
        price_usd = 0.0 if pd.isna(price_usd) else round(float(price_usd), 2)

        candidate = {
            "id": make_doc_id(owner, row["Opportunity Name"], product_code),
            "used": False,
            "suggestedQuarter": compute_quarter(close_date),
            "suggestedTeam": team,
            "suggestedMember": member,
            "owner": owner,
            "so": so_str,
            "account": str(row.get("Account Name", "")),
            "product": "GMPP",
            "lineTypeHint": line_type_hint,
            "priceKRW": price_krw,
            "priceUSD": price_usd,
            "salesType": str(row.get("Sales Type", "") or ""),
            "stage": str(row.get("Stage", "")),
            "opportunityName": str(row.get("Opportunity Name", "")),
            "closeDate": close_date.isoformat(),
            "importedAt": now_iso,
        }
        candidates.append(candidate)

    return candidates, skipped_owners


def upload_candidates(candidates, db):
    """이미 있는 후보(id)는 건너뛰고 새 후보만 sf_candidates 컬렉션에 생성한다."""
    ref = db.collection("sf_candidates")
    created, skipped_existing = 0, 0
    for c in candidates:
        doc_ref = ref.document(c["id"])
        if doc_ref.get().exists:
            skipped_existing += 1
            continue
        doc_ref.set(c)
        created += 1
    return created, skipped_existing
