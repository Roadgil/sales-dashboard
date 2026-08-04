import hashlib
from datetime import datetime

import pandas as pd

from member_map import OWNER_TO_MEMBER, OWNER_TO_TEAM

# 메인 시스템 라인의 Product Code -> 참고용 DCD/ACC 힌트.
# PTO103577(DCD)/PTO103576(ACC)는 과거에 혼용되던 코드로, 현재는 PTO103576을 쓰지 않도록
# 권장되고 있으나 미수정된 과거 데이터가 남아있을 수 있어 분석 시 둘 다 GMPP로 인식한다
# (DCD/ACC 구분은 이 코드가 아니라 아래 ACC_TYPE_CODES 옵션킷 조합으로 판단).
MAIN_PRODUCT_CODES = {
    "PTO103577": "DCD",
    "PTO103576": "ACC",
}

# GMPP 옵션킷 Product Code -> Acc Type 라벨. 한 Opportunity 안에 이 코드들이 몇 종류
# 섞여 들어왔는지 세어서 Acc Type을 만든다.
# - 1종류뿐이면 그 종류가 뭐든(AIO 포함) 그냥 "1"
# - 2종류 이상이면 "<종류 수>", AIO가 섞여있으면 뒤에 "<종류 수>, AIO(DCD)" / "AIO(ACC)" / 둘 다 있으면
#   "<종류 수>, AIO(DCD), AIO(ACC)"
# 예) Small+Medium+AIO(DCD) 3종 -> "3, AIO(DCD)" / Small+Medium+Large(DCD) 3종 -> "3" / AIO(DCD) 1종 -> "1"
ACC_TYPE_CODES = {
    "7123-CE-0650": "Small",
    "FIN103337": "Medium",
    "7123-CE-0652": "Large(DCD)",
    "7123-CE-0653": "Large(ACC)",
    "FIN101958": "AIO(DCD)",
    "FIN101959": "AIO(ACC)",
}


def compute_acc_type(group):
    codes_present = set(group["Product Code"].astype(str)) & set(ACC_TYPE_CODES.keys())
    labels = {ACC_TYPE_CODES[c] for c in codes_present}
    if not labels:
        return ""
    count = len(labels)
    if count == 1:
        return "1"
    aio_labels = [l for l in ("AIO(DCD)", "AIO(ACC)") if l in labels]
    if aio_labels:
        return f"{count}, " + ", ".join(aio_labels)
    return str(count)

# GMPP 오퍼튜니티 안에 같이 딸려오는, GMPP와는 별개의 시스템 상품 - Product Name이 이 정규식과
# 매치되면 GMPP 합계에서 빼서 별도의 후보(같은 Account/SO, 다른 product)로 분리한다.
# 순서가 중요함: 더 구체적인 패턴(Nordlys Mini)을 먼저 검사해서 일반 패턴(Nordlys)이 가로채지 않게 함.
# "GMP"는 "GMPP"의 부분 문자열이라 반드시 단어 경계(\b)로 매칭 - 그래야 GMPP 라인이 GMP로 오인되지 않음.
COMPANION_SYSTEMS = [
    ("Cryo7", r"\bcryo\s?7\b"),
    ("Nordlys Mini", r"\bnordlys\s+mini\b"),
    ("Nordlys", r"\bnordlys\b"),
    ("Picoway", r"\bpicoway\b"),
    ("VBP", r"\bvbp\b"),
    ("Hand Piece", r"\bhand\s?piece\b"),
    ("GMP", r"\bgmp\b"),
]


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


def _build_candidate(opp_name, owner, member, team, account, so_str, product, line_type_hint,
                      stage, sales_type, close_date, price_krw, price_usd, now_iso, id_key,
                      acc_type=""):
    return {
        "id": make_doc_id(owner, opp_name, id_key),
        "used": False,
        "suggestedQuarter": compute_quarter(close_date),
        "suggestedTeam": team,
        "suggestedMember": member,
        "owner": owner,
        "so": so_str,
        "account": account,
        "product": product,
        "lineTypeHint": line_type_hint,
        "accType": acc_type,
        "priceKRW": price_krw,
        "priceUSD": price_usd,
        "salesType": sales_type,
        "stage": stage,
        "opportunityName": opp_name,
        "closeDate": close_date.isoformat(),
        "importedAt": now_iso,
    }


def build_candidates(df, prev_to, new_to, from_fixed):
    """
    df: parse_report()의 결과.
    prev_to / new_to / from_fixed: date 객체. Close Date가 (prev_to, new_to] 구간이면서
    from_fixed 이상인 행만 대상으로 함. Stage(Closed Won 여부)는 가리지 않고 전부 포함 -
    최종 반영 여부/분기/담당자/상태는 대시보드에서 사람이 후보를 클릭해 확정한다.

    가격(KRW/USD)은 PTO103577/PTO103576 라인 하나가 아니라, 같은 Opportunity에 딸린
    라인들의 Total Price를 더한 값 - 실제 계약 총액. 단, COMPANION_SYSTEMS에 해당하는
    라인(예: Cryo7)은 GMPP와 별개 시스템이라 합계에서 빼고 같은 Account/SO의 별도
    후보(product=Cryo7 등)로 분리한다.
    Opportunity 안에 PTO103577/PTO103576 라인이 하나라도 있어야 GMPP 후보로 인정한다.

    반환: (candidates, skipped_unmapped_owners)
    """
    df = df.copy()
    df["_close_date"] = pd.to_datetime(df["Close Date"], format="%Y. %m. %d", errors="coerce").dt.date

    candidates = []
    skipped_owners = set()
    now_iso = datetime.utcnow().isoformat()

    for opp_name, group in df.groupby("Opportunity Name"):
        main_rows = group[group["Product Code"].astype(str).isin(MAIN_PRODUCT_CODES.keys())]
        if main_rows.empty:
            continue
        main_row = main_rows.iloc[0]

        close_date = main_row["_close_date"]
        if pd.isna(close_date) or not (prev_to < close_date <= new_to and close_date >= from_fixed):
            continue

        owner = str(main_row["Opportunity Owner"]).strip()
        member = OWNER_TO_MEMBER.get(owner)
        team = OWNER_TO_TEAM.get(owner)
        if member is None or team is None:
            skipped_owners.add(owner)
            continue

        product_code = str(main_row["Product Code"])
        line_type_hint = MAIN_PRODUCT_CODES[product_code]
        so_num = main_row.get("Oracle Sales Order Number")
        so_str = "" if pd.isna(so_num) else str(int(so_num))
        account = str(main_row.get("Account Name", ""))
        stage = str(main_row.get("Stage", ""))
        sales_type = str(main_row.get("Sales Type", "") or "")

        names = group["Product Name"].astype(str).str.lower()
        companion_mask = pd.Series(False, index=group.index)
        companion_candidates = []
        for sys_name, pattern in COMPANION_SYSTEMS:
            sys_mask = names.str.contains(pattern, regex=True) & ~companion_mask
            if not sys_mask.any():
                continue
            companion_mask = companion_mask | sys_mask
            sys_price_krw = round(float(group.loc[sys_mask, "Total Price"].fillna(0).sum()))
            sys_price_usd = round(float(group.loc[sys_mask, "Total Price (converted)"].fillna(0).sum()), 2)
            companion_candidates.append(_build_candidate(
                opp_name, owner, member, team, account, so_str, sys_name, "",
                stage, sales_type, close_date, sys_price_krw, sys_price_usd, now_iso, sys_name.upper(),
            ))

        gmpp_rows = group[~companion_mask]
        price_krw = round(float(gmpp_rows["Total Price"].fillna(0).sum()))
        price_usd = round(float(gmpp_rows["Total Price (converted)"].fillna(0).sum()), 2)
        acc_type = compute_acc_type(gmpp_rows)

        candidates.append(_build_candidate(
            opp_name, owner, member, team, account, so_str, "GMPP", line_type_hint,
            stage, sales_type, close_date, price_krw, price_usd, now_iso, product_code,
            acc_type=acc_type,
        ))
        candidates.extend(companion_candidates)

    return candidates, skipped_owners


def upload_candidates(candidates, db):
    """새 후보는 생성하고, 아직 안 쓴(used=false) 기존 후보는 최신 Salesforce 값으로 덮어쓴다.
    이미 사용(used=true, 즉 sales로 이미 넘어간) 후보는 건드리지 않는다.

    같은 Opportunity의 다른 후보(예: GMPP)가 이미 sales로 넘어갔는데 이 후보(예: 나중에
    나타난 Cryo7)는 아직이면, 자동으로 합치지 않고 relatedToRegisteredDeal=True로 표시만
    해서 대시보드에서 사람이 보고 판단하게 한다 (자동 병합은 검토 없이 매출이 생기는
    위험이 있어 배제함)."""
    ref = db.collection("sf_candidates")
    snapshots = {c["id"]: ref.document(c["id"]).get() for c in candidates}

    used_by_opp = {}
    for c in candidates:
        snap = snapshots[c["id"]]
        is_used = snap.exists and snap.to_dict().get("used", False)
        used_by_opp.setdefault(c["opportunityName"], []).append(is_used)

    created, updated, skipped_used = 0, 0, 0
    for c in candidates:
        snap = snapshots[c["id"]]
        already_used = snap.exists and snap.to_dict().get("used", False)
        c["relatedToRegisteredDeal"] = (not already_used) and any(used_by_opp.get(c["opportunityName"], []))

        doc_ref = ref.document(c["id"])
        if not snap.exists:
            doc_ref.set(c)
            created += 1
            continue
        if already_used:
            skipped_used += 1
            continue
        doc_ref.set(c)
        updated += 1
    return created, updated, skipped_used


def sync_price_updates(candidates, db):
    """이미 sales로 넘어간 건(같은 id의 sales 문서가 존재)에 대해:
    - Salesforce 금액이 바뀌었으면 priceKRW/priceUSD를 자동 갱신
    - Salesforce가 제안하는 분기가 현재 등록된 분기와 달라졌으면, 분기를 직접 바꾸지는 않고
      _sfQuarterMismatch 필드에 새 제안 분기를 남겨 대시보드에서 확인 후 사람이 판단하게 함
      (다시 일치하면 _sfQuarterMismatch 제거)
    status/계약일/납품예정일/Dealer 등 수기 입력 필드는 그대로 둔다."""
    from firebase_admin import firestore

    sales_ref = db.collection("sales")
    updated = 0
    now_iso = datetime.utcnow().isoformat()
    for c in candidates:
        doc_ref = sales_ref.document(c["id"])
        snap = doc_ref.get()
        if not snap.exists:
            continue
        existing = snap.to_dict()
        patch = {}

        if existing.get("priceKRW") != c["priceKRW"]:
            patch["priceKRW"] = c["priceKRW"]
            patch["priceUSD"] = c["priceUSD"]
            patch["_sfPriceUpdatedAt"] = now_iso
            patch["_sfPriceUpdatedFrom"] = existing.get("priceKRW")

        if existing.get("quarter") != c["suggestedQuarter"]:
            if existing.get("_sfQuarterMismatch") != c["suggestedQuarter"]:
                patch["_sfQuarterMismatch"] = c["suggestedQuarter"]
        elif existing.get("_sfQuarterMismatch"):
            patch["_sfQuarterMismatch"] = firestore.DELETE_FIELD

        if patch:
            doc_ref.update(patch)
            updated += 1
    return updated
