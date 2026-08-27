import hashlib
from datetime import datetime

import pandas as pd

from member_map import OWNER_TO_MEMBER, OWNER_TO_TEAM

# GMPP 메인 시스템 라인의 Product Code -> 참고용 DCD/ACC 힌트.
# PTO103577(DCD)/PTO103576(ACC)는 과거에 혼용되던 코드로, 현재는 PTO103576을 쓰지 않도록
# 권장되고 있으나 미수정된 과거 데이터가 남아있을 수 있어 분석 시 둘 다 GMPP로 인식한다
# (DCD/ACC 구분은 이 코드가 아니라 아래 ACC_TYPE_CODES 옵션킷 조합으로 판단).
# "GMPP CE WITH DCD"는 Product Code 자리에 코드 대신 제품명이 그대로 들어온 변칙 데이터인데,
# 실제로는 GMPP 메인 라인이라 동일하게 취급한다(2026-08-27 확인).
MAIN_PRODUCT_CODES = {
    "PTO103577": "DCD",
    "PTO103576": "ACC",
    "GMPP CE WITH DCD": "DCD",
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

# GMPP 외의 시스템 상품 - Product Name이 이 정규식과 매치되는 라인은 해당 제품 버킷으로
# 묶여 별도의 후보(같은 Account/SO, 다른 product)가 된다. GMPP 오퍼튜니티에 딸려온 경우엔
# GMPP 합계에서 빠지고, 이 제품만 있는 오퍼튜니티면 그 자체가 후보가 된다.
# 제품명은 대시보드 index.html의 allProducts와 정확히 같은 8개 버킷을 쓴다.
#
# 순서가 중요함: 더 구체적인 패턴(Nordlys Mini)을 먼저 검사해서 일반 패턴(Nordlys)이 가로채지 않게 함.
# Picoway를 Hand Piece보다 먼저 둔 것도 같은 이유 - 피코웨이 핸드피스 킷이 Hand Piece로 새지 않게 함.
# "GMP"는 "GMPP"의 부분 문자열이라 반드시 단어 경계(\b)로 매칭 - 그래야 GMPP 라인이 GMP로 오인되지 않음.
#
# 실제 Salesforce 리포트의 제품명은 약어가 아니라 풀네임으로 들어오므로 별칭을 같이 매칭한다
# (2026-08-27 확인): VBP는 "VBEAM PERFECTA VT 9914-0300 with COT",
# GMP는 "GENTLEMAX PRO LASER SYSTEM W/ DCD" 형태로 들어와서, 약어만으로는 한 건도 안 잡혔었다.
SYSTEM_PATTERNS = [
    ("Cryo7", r"\bcryo\s?7\b"),
    ("Nordlys Mini", r"\bnordlys\s+mini\b"),
    ("Nordlys", r"\bnordlys\b"),
    ("Picoway", r"\bpicoway\b"),
    ("VBP", r"\bvbeam\b|\bvbp\b"),
    ("Hand Piece", r"\bhand\s?piece\b"),
    ("GMP", r"\bgentlemax\s+pro\b|\bgmp\b"),
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


def split_into_product_buckets(group):
    """한 Opportunity의 라인들을 제품 버킷으로 나눈다.

    반환: (buckets, primary) - buckets는 {제품명: boolean mask}, primary는 이 Opportunity의
    대표 제품명. 시스템 라인이 하나도 없으면 (None, None).

    규칙:
    - MAIN_PRODUCT_CODES 라인은 무조건 GMPP 버킷 (제품명 패턴 검사를 아예 거치지 않음).
    - 나머지는 SYSTEM_PATTERNS를 순서대로 검사해서 먼저 매치된 제품 버킷에 담는다.
    - 대표 제품 = GMPP 메인 라인이 있으면 GMPP, 없으면 금액(Total Price 합)이 가장 큰 시스템.
    - 어느 제품에도 안 잡힌 라인(운임 FREIGHT CHARGE ONLY, 옵션킷, 애플리케이터 등)은
      대표 제품에 귀속시킨다 - 그래야 계약 총액이 어느 한 제품에 온전히 잡힌다.
    """
    main_mask = group["Product Code"].astype(str).isin(MAIN_PRODUCT_CODES.keys())
    names = group["Product Name"].astype(str).str.lower()

    # GMPP 메인 라인은 처음부터 "이미 가져간" 것으로 두어 다른 패턴이 채가지 못하게 한다.
    taken = main_mask.copy()
    buckets = {}
    for sys_name, pattern in SYSTEM_PATTERNS:
        sys_mask = names.str.contains(pattern, regex=True) & ~taken
        if not sys_mask.any():
            continue
        taken = taken | sys_mask
        buckets[sys_name] = sys_mask

    if main_mask.any():
        buckets["GMPP"] = main_mask
        primary = "GMPP"
    elif buckets:
        primary = max(
            buckets,
            key=lambda s: float(group.loc[buckets[s], "Total Price"].fillna(0).sum()),
        )
    else:
        # 시스템 라인이 전혀 없는 Opportunity(운임/부속만 있는 건 등) - 귀속시킬 제품이 없어 건너뜀
        return None, None

    leftover = ~taken
    if leftover.any():
        buckets[primary] = buckets[primary] | leftover

    return buckets, primary


def build_candidates(df, prev_to, new_to, from_fixed):
    """
    df: parse_report()의 결과.
    prev_to / new_to / from_fixed: date 객체. Close Date가 (prev_to, new_to] 구간이면서
    from_fixed 이상인 행만 대상으로 함. Stage(Closed Won 여부)는 가리지 않고 전부 포함 -
    최종 반영 여부/분기/담당자/상태는 대시보드에서 사람이 후보를 클릭해 확정한다.

    Opportunity 하나를 split_into_product_buckets()로 제품별로 쪼갠 뒤, 각 제품마다 후보를
    하나씩 만든다. 가격(KRW/USD)은 그 제품 버킷에 속한 라인들의 Total Price 합 - 즉 GMPP
    후보의 금액에는 옵션킷/운임까지 포함된 실제 계약 총액이 들어가고, 같이 딸려온 Cryo7 같은
    별개 시스템은 그 합계에서 빠져 같은 Account/SO의 별도 후보가 된다.

    GMPP 라인이 없는 Opportunity(순수 Picoway/Nordlys/VBP 건 등)도 그 제품 자체를 후보로
    만든다 - 2026-08-27 이전에는 GMPP 메인 라인이 없으면 Opportunity를 통째로 버렸다.

    반환: (candidates, skipped_unmapped_owners)
    """
    df = df.copy()
    df["_close_date"] = pd.to_datetime(df["Close Date"], format="%Y. %m. %d", errors="coerce").dt.date

    candidates = []
    skipped_owners = set()
    now_iso = datetime.utcnow().isoformat()

    for opp_name, group in df.groupby("Opportunity Name"):
        buckets, primary = split_into_product_buckets(group)
        if buckets is None:
            continue

        # 대표 제품의 첫 라인에서 Opportunity 공통 정보(마감일/담당자/거래처 등)를 읽는다.
        header_row = group[buckets[primary]].iloc[0]

        close_date = header_row["_close_date"]
        if pd.isna(close_date) or not (prev_to < close_date <= new_to and close_date >= from_fixed):
            continue

        owner = str(header_row["Opportunity Owner"]).strip()
        member = OWNER_TO_MEMBER.get(owner)
        team = OWNER_TO_TEAM.get(owner)
        if member is None or team is None:
            skipped_owners.add(owner)
            continue

        so_num = header_row.get("Oracle Sales Order Number")
        so_str = "" if pd.isna(so_num) else str(int(so_num))
        account = str(header_row.get("Account Name", ""))
        stage = str(header_row.get("Stage", ""))
        sales_type = str(header_row.get("Sales Type", "") or "")

        # 대표 제품을 먼저, 나머지는 SYSTEM_PATTERNS 순서대로 - 실행할 때마다 순서가 흔들리지 않게.
        ordered = [primary] + [n for n, _ in SYSTEM_PATTERNS if n in buckets and n != primary]
        for product in ordered:
            rows = group[buckets[product]]
            price_krw = round(float(rows["Total Price"].fillna(0).sum()))
            price_usd = round(float(rows["Total Price (converted)"].fillna(0).sum()), 2)

            if product == "GMPP":
                # 후보 id는 예전부터 GMPP 메인 라인의 Product Code로 만들어 왔다 - 이미 등록된
                # 후보/매출과 id가 어긋나지 않도록 그대로 유지한다.
                product_code = str(rows[rows["Product Code"].astype(str).isin(MAIN_PRODUCT_CODES.keys())]
                                   .iloc[0]["Product Code"])
                id_key = product_code
                line_type_hint = MAIN_PRODUCT_CODES[product_code]
                acc_type = compute_acc_type(rows)
            else:
                id_key = product.upper()
                line_type_hint = ""
                acc_type = ""

            candidates.append(_build_candidate(
                opp_name, owner, member, team, account, so_str, product, line_type_hint,
                stage, sales_type, close_date, price_krw, price_usd, now_iso, id_key,
                acc_type=acc_type,
            ))

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
    - SO(Oracle Sales Order Number)가 대시보드엔 비어있는데 Salesforce엔 생겼으면 채워넣음.
      등록 시점엔 아직 오라클 오더가 없어서 SO 없이 넘어간 건이 많은데(미래 분기일수록 많음),
      그대로 두면 영영 빈칸으로 남아 커미션 정산 등에서 이 건을 짚어낼 방법이 없어진다.
      이미 값이 있으면(수기 입력 포함) 절대 덮어쓰지 않는다.
    - Salesforce가 제안하는 분기가 현재 등록된 분기와 달라졌으면, 분기를 직접 바꾸지는 않고
      _sfQuarterMismatch 필드에 새 제안 분기를 남겨 대시보드에서 확인 후 사람이 판단하게 함
      (다시 일치하면 _sfQuarterMismatch 제거)
    status/계약일/납품예정일/Dealer 등 수기 입력 필드는 그대로 둔다.

    반환: (금액 등 갱신 건수, SO 신규 기입 건수)"""
    from firebase_admin import firestore

    sales_ref = db.collection("sales")
    updated = 0
    so_filled = 0
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

        # 비어있을 때만 채운다 - 사람이 넣은 값을 Salesforce가 밀어내면 안 됨
        if c.get("so") and not str(existing.get("so") or "").strip():
            patch["so"] = c["so"]
            patch["_sfSoFilledAt"] = now_iso
            so_filled += 1

        if existing.get("quarter") != c["suggestedQuarter"]:
            if existing.get("_sfQuarterMismatch") != c["suggestedQuarter"]:
                patch["_sfQuarterMismatch"] = c["suggestedQuarter"]
        elif existing.get("_sfQuarterMismatch"):
            patch["_sfQuarterMismatch"] = firestore.DELETE_FIELD

        if patch:
            doc_ref.update(patch)
            updated += 1
    return updated, so_filled
