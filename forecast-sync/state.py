import json
from datetime import timedelta

import config


def load_last_to():
    if not config.STATE_PATH.exists():
        return None
    data = json.loads(config.STATE_PATH.read_text(encoding="utf-8"))
    return data.get("last_to")


def save_last_to(iso_date_str):
    config.STATE_PATH.write_text(
        json.dumps({"last_to": iso_date_str}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def compute_window():
    """
    반환값: (prev_to, new_to) - 둘 다 date 객체.
    이번 실행에서 새로 가져올 데이터의 Close Date 범위는 (prev_to, new_to] (prev_to 초과, new_to 이하).

    최초 실행: new_to = 2028-12-31, prev_to = FROM_FIXED 하루 전 (즉 FROM_FIXED부터 전부 포함)
    이후 실행: prev_to = 지난 실행의 new_to, new_to = prev_to + 30일
    """
    last_to = load_last_to()
    if last_to is None:
        prev_to = config.FROM_FIXED - timedelta(days=1)
        new_to = config.FIRST_TO
    else:
        from datetime import date as _date
        prev_to = _date.fromisoformat(last_to)
        new_to = prev_to + timedelta(days=config.TO_STEP_DAYS)
    return prev_to, new_to
