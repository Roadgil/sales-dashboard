"""
2주에 한 번 실행하는 진입점.
1) state.py로 이번 실행의 Time Frame 범위 (prev_to, new_to] 계산
2) Selenium으로 Salesforce 리포트 Time Frame을 From=고정, To=new_to 로 설정 후 export
3) 다운로드된 파일을 파싱해서 PTO103577/PTO103576 라인만, Close Date가 (prev_to, new_to] 인 것만 추림
   (Stage는 가리지 않고 전부 후보로 올림 - Closed Won 여부/분기/담당자/상태는 대시보드에서 사람이 확정)
4) Firestore sf_candidates 컬렉션에 신규 후보만 생성 (대시보드의 sales 컬렉션은 건드리지 않음)
5) state에 new_to 저장

--dry-run 옵션: Selenium/Firestore 업로드 없이, 이미 받아둔 파일을 파싱 결과만 출력.
    사용법: python run.py --dry-run "C:\\path\\to\\report.xls"
"""
import sys

import config
import parse_upload
import state


def main():
    if "--dry-run" in sys.argv:
        idx = sys.argv.index("--dry-run")
        xls_path = sys.argv[idx + 1]
        prev_to, new_to = state.compute_window()
        print(f"[dry-run] 대상 구간: ({prev_to} ~ {new_to}]")
        df = parse_upload.parse_report(xls_path)
        candidates, skipped_owners = parse_upload.build_candidates(df, prev_to, new_to, config.FROM_FIXED)
        print(f"[dry-run] 대상 후보 수: {len(candidates)}")
        if skipped_owners:
            print(f"[dry-run] 매핑 안 된 Owner (member_map.py에 추가 필요): {skipped_owners}")
        for d in candidates[:5]:
            print(d)
        return

    import firebase_admin
    from firebase_admin import credentials, firestore
    import selenium_export

    prev_to, new_to = state.compute_window()
    print(f"이번 실행 대상 구간: ({prev_to} ~ {new_to}]  (From 고정값: {config.FROM_FIXED})")

    xls_path = selenium_export.run_export(config.FROM_FIXED, new_to)

    df = parse_upload.parse_report(xls_path)
    candidates, skipped_owners = parse_upload.build_candidates(df, prev_to, new_to, config.FROM_FIXED)
    print(f"파싱된 대상 후보 수: {len(candidates)}")
    if skipped_owners:
        print(f"[경고] 매핑되지 않은 Owner가 있어 건너뛰었습니다: {skipped_owners}")
        print("        member_map.py의 OWNER_TO_MEMBER / OWNER_TO_TEAM 에 추가해주세요.")

    cred = credentials.Certificate(config.FIREBASE_CRED_PATH)
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    db = firestore.client()

    created, skipped_existing = parse_upload.upload_candidates(candidates, db)
    print(f"Firestore 업로드 완료: 신규 후보 {created}건, 기존 존재라 건너뜀 {skipped_existing}건")

    state.save_last_to(new_to.isoformat())
    print(f"state 저장 완료: last_to = {new_to.isoformat()}")


if __name__ == "__main__":
    main()
