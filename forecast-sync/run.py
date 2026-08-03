"""
매달 1회(Windows 작업 스케줄러 "Forecast_Sync", 매달 1일 16:00) 실행하는 진입점.
1) state.py로 이번 실행의 Time Frame 상한(new_to) 계산 - 처음 2028-12-31, 이후 +30일씩
2) Selenium으로 Salesforce 리포트 Time Frame을 From=고정, To=new_to 로 설정 후 export
3) 다운로드된 파일을 파싱해서 PTO103577/PTO103576 라인이 있는 Opportunity만, Close Date가
   From 고정값 ~ new_to 사이인 것 전부(Stage 무관) 후보로 만듦 - 매번 전체 구간을 다시 훑는다
   (이미 있는 후보/이미 sales로 넘어간 건은 아래 4)/5)에서 각각 안전하게 처리되므로 괜찮음)
4) Firestore sf_candidates 컬렉션에 반영 - 신규 후보는 생성, 아직 안 쓴(used=false) 기존
   후보는 최신 Salesforce 값으로 덮어씀, 이미 사용된(used=true) 후보는 건드리지 않음
5) 이미 sales로 넘어간 건(같은 id의 sales 문서 존재)의 Salesforce 금액이 바뀌었으면
   priceKRW/priceUSD만 자동 갱신 (수기 입력 필드는 그대로 둠)
6) state에 new_to 저장

--dry-run 옵션: Selenium/Firestore 업로드 없이, 이미 받아둔 파일을 파싱 결과만 출력.
    사용법: python run.py --dry-run "C:\\path\\to\\report.xls"
"""
import sys
from datetime import timedelta

import config
import parse_upload
import state


def main():
    if "--dry-run" in sys.argv:
        idx = sys.argv.index("--dry-run")
        xls_path = sys.argv[idx + 1]
        _, new_to = state.compute_window()
        scan_from = config.FROM_FIXED - timedelta(days=1)
        print(f"[dry-run] 대상 구간: (전체 {config.FROM_FIXED} ~ {new_to}]")
        df = parse_upload.parse_report(xls_path)
        candidates, skipped_owners = parse_upload.build_candidates(df, scan_from, new_to, config.FROM_FIXED)
        print(f"[dry-run] 대상 후보 수: {len(candidates)}")
        if skipped_owners:
            print(f"[dry-run] 매핑 안 된 Owner (member_map.py에 추가 필요): {skipped_owners}")
        for d in candidates[:5]:
            print(d)
        return

    import firebase_admin
    from firebase_admin import credentials, firestore
    import selenium_export

    _, new_to = state.compute_window()
    scan_from = config.FROM_FIXED - timedelta(days=1)
    print(f"이번 실행 대상 구간: (전체 {config.FROM_FIXED} ~ {new_to}]")

    xls_path = selenium_export.run_export(config.FROM_FIXED, new_to)

    df = parse_upload.parse_report(xls_path)
    candidates, skipped_owners = parse_upload.build_candidates(df, scan_from, new_to, config.FROM_FIXED)
    print(f"파싱된 대상 후보 수: {len(candidates)}")
    if skipped_owners:
        print(f"[경고] 매핑되지 않은 Owner가 있어 건너뛰었습니다: {skipped_owners}")
        print("        member_map.py의 OWNER_TO_MEMBER / OWNER_TO_TEAM 에 추가해주세요.")

    cred = credentials.Certificate(config.FIREBASE_CRED_PATH)
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    db = firestore.client()

    created, updated, skipped_used = parse_upload.upload_candidates(candidates, db)
    print(f"Firestore 후보 동기화 완료: 신규 {created}건, 갱신 {updated}건, 이미 사용됨(건너뜀) {skipped_used}건")

    price_updated = parse_upload.sync_price_updates(candidates, db)
    print(f"이미 sales로 넘어간 건 중 금액 변경 감지되어 갱신: {price_updated}건")

    state.save_last_to(new_to.isoformat())
    print(f"state 저장 완료: last_to = {new_to.isoformat()}")


if __name__ == "__main__":
    main()
