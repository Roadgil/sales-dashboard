"""
Salesforce 리포트(KS_251219, 00OPY00000F4ckP)를 열어서 Time Frame(Close Date) 필터를
From=고정값 / To=계산된 날짜로 맞추고 Excel(.xls, Korean 인코딩)로 Export/다운로드하는 스크립트.

로그인은 회사 SSO(OS 계정 토큰)에 맡긴다 - RMA/ICBL 자동화와 동일한 "전용 포트(9335) +
전용 프로필"의 Edge 인스턴스를 재사용하면, 첫 실행 이후로는 로그인 화면 자체가 뜨지 않는다
(실측 확인됨, 2026-08-03). 이 리포트는 Classic UI(Lightning 아님)로 렌더링되므로 선택자도
전부 Classic 구조(quarter_s/quarter_e/quarter_q input, "Export Details"/"Export" 버튼) 기준.
"""
import socket
import subprocess
import shutil
from pathlib import Path
import time

from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select

import config

EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"


def fmt_date_kr(d):
    # 리포트 From/To 입력창 포맷("2026. 7. 1")과 동일하게 (0 패딩 없이)
    return f"{d.year}. {d.month}. {d.day}"


def ensure_edge_running(initial_url="about:blank"):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1)
    try:
        s.connect(("127.0.0.1", config.EDGE_DEBUG_PORT))
        s.close()
        return True
    except Exception:
        s.close()

    subprocess.Popen([
        EDGE_PATH,
        f"--remote-debugging-port={config.EDGE_DEBUG_PORT}",
        f"--user-data-dir={config.EDGE_PROFILE_DIR}",
        "--profile-directory=Default",
        "--start-maximized",
        initial_url,
    ])
    time.sleep(10)
    return True


def get_driver():
    from selenium import webdriver
    from selenium.webdriver.edge.options import Options

    options = Options()
    options.add_experimental_option("debuggerAddress", f"127.0.0.1:{config.EDGE_DEBUG_PORT}")
    return webdriver.Edge(options=options)


def screenshot(driver, name):
    path = config.BASE_DIR / f"error_{name}.png"
    try:
        driver.save_screenshot(str(path))
        print(f"  (스크린샷 저장: {path})")
    except Exception:
        pass


def open_report(driver):
    driver.get(config.SF_REPORT_URL)
    for _ in range(15):
        if "KS_251219" in driver.title:
            return
        time.sleep(1)
    screenshot(driver, "report_load_unrecognized")
    raise TimeoutException(f"KS_251219 리포트 페이지를 확인하지 못했습니다 (title={driver.title!r}).")


def set_time_frame_and_run(driver, from_date, to_date):
    """quarter_q를 Custom으로, quarter_s/quarter_e를 지정값으로 설정하고 Run Report."""
    try:
        Select(driver.find_element(By.ID, "quarter_q")).select_by_value("custom")
        driver.execute_script(
            "document.getElementById('quarter_s').value = arguments[0];"
            "document.getElementById('quarter_e').value = arguments[1];",
            fmt_date_kr(from_date), fmt_date_kr(to_date),
        )
        run_btn = driver.find_element(By.XPATH, "//input[@value='Run Report']")
        driver.execute_script("arguments[0].click();", run_btn)
        time.sleep(8)
        print(f"  Time Frame 설정 완료: {fmt_date_kr(from_date)} ~ {fmt_date_kr(to_date)}")
        return
    except (NoSuchElementException, TimeoutException) as e:
        screenshot(driver, "time_frame_fail")
        raise RuntimeError(f"Time Frame 자동 설정 실패 ({e.__class__.__name__}) - 화면을 확인해주세요.") from e


def export_xls(driver):
    """Export Details -> Korean 인코딩 -> Export 로 .xls 다운로드 트리거."""
    before = set(p.name for p in config.DOWNLOAD_DIR.glob("*"))

    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    try:
        # 좌표 기반 네이티브 클릭(.click())이 이 버튼에서만 씹히는 게 실측 확인돼
        # JS 이벤트 디스패치로 바꿔서 해결함(전용 프로필 특성으로 추정, 확실한 원인은
        # 못 찾음). 그래도 혹시 한 번 더 씹힐 경우를 대비해 재시도 루프는 남겨둔다.
        for attempt in range(2):
            btn = driver.find_element(By.XPATH, "//input[@value='Export Details']")
            driver.execute_script("arguments[0].click();", btn)
            try:
                WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, "enc")))
                break
            except TimeoutException:
                if attempt == 1:
                    raise
                print("  Export Details 클릭이 반영 안 됨 - 재시도합니다...")

        Select(driver.find_element(By.ID, "enc")).select_by_visible_text("Korean")

        final_btn = driver.find_element(By.XPATH, "//input[@value='Export']")
        driver.execute_script("arguments[0].click();", final_btn)
        print("  Export 클릭 완료. 다운로드 대기 중...")
    except (NoSuchElementException, TimeoutException) as e:
        screenshot(driver, "export_fail")
        raise RuntimeError(f"Export 자동 클릭 실패 ({e.__class__.__name__}) - 화면을 확인해주세요.") from e

    return wait_for_new_file(before)


USER_DOWNLOADS = Path.home() / "Downloads"


def wait_for_new_file(before_names, timeout=90):
    started = time.time()
    deadline = started + timeout
    while time.time() < deadline:
        current = list(config.DOWNLOAD_DIR.glob("*"))
        new_files = [p for p in current if p.name not in before_names and not p.name.endswith(".crdownload")]
        if new_files:
            newest = max(new_files, key=lambda p: p.stat().st_mtime)
            return newest
        # 안전망: 다운로드 경로 지정이 안 먹고 Edge 기본 Downloads로 떨어진 경우(10/22, 11/2 실측)
        # 이번 실행 이후 생긴 리포트 파일을 찾아 DOWNLOAD_DIR로 옮겨온다.
        stray = [p for p in USER_DOWNLOADS.glob("KS_251219*.xls")
                 if p.stat().st_mtime >= started - 5]
        if stray:
            src = max(stray, key=lambda p: p.stat().st_mtime)
            time.sleep(2)  # 쓰기 마무리 대기
            dst = config.DOWNLOAD_DIR / src.name
            shutil.move(str(src), str(dst))
            print(f"  (기본 Downloads 폴더로 받아져서 옮겨옴: {src.name})")
            return dst
        time.sleep(1)
    raise TimeoutError(f"{config.DOWNLOAD_DIR} 에서 새 다운로드 파일을 찾지 못했습니다 ({timeout}초 대기).")


def close_stray_tabs(driver):
    """오래 켜두는 전용 프로필 특성상 실패한 이전 실행의 탭이 계속 쌓일 수 있어,
    매 실행 시작 시 다른 탭을 전부 닫고 하나만 남긴다(그 탭은 새 작업용 탭을 만들기
    전까지 about:blank로 정리) - 배경 탭 포커스 문제로 클릭이 씹히는 걸 방지."""
    # edge://downloads-hub 같은 내부 페이지 탭은 WebDriver close가 20초 멈춘 뒤 실패한다
    # (2026-11-02 실측) → DevTools HTTP 엔드포인트로 먼저 닫는다.
    try:
        import json, urllib.request
        base = f"http://127.0.0.1:{config.EDGE_DEBUG_PORT}/json"
        for t in json.load(urllib.request.urlopen(base + "/list", timeout=5)):
            if t.get("type") == "page" and str(t.get("url", "")).startswith("edge://"):
                urllib.request.urlopen(f"{base}/close/{t['id']}", timeout=5).read()
                print(f"  (Edge 내부 탭 닫음: {t.get('url')})")
    except Exception as e:
        print(f"  (Edge 내부 탭 정리 실패, 계속 진행: {e.__class__.__name__})")
    handles = driver.window_handles
    for h in handles[1:]:
        try:
            driver.switch_to.window(h)
            driver.close()
        except Exception as e:
            print(f"  (남은 탭 닫기 실패, 계속 진행: {e.__class__.__name__})")
    driver.switch_to.window(driver.window_handles[0])
    driver.get("about:blank")


def run_export(from_date, to_date):
    ensure_edge_running(config.SF_REPORT_URL)
    driver = get_driver()
    close_stray_tabs(driver)
    driver.switch_to.new_window("tab")
    # ensure_edge_running()은 subprocess.Popen으로 그냥 띄우기만 해서 Selenium의
    # download.default_directory prefs가 적용 안 됨 - CDP로 이 세션의 다운로드 경로를
    # 직접 지정해야 기본 Downloads 폴더가 아니라 config.DOWNLOAD_DIR로 떨어진다.
    # 2026-10-22/11-02: Page.setDownloadBehavior(탭 단위, deprecated)만으로는 가끔 기본
    # Downloads 폴더로 떨어져 90초 타임아웃 → 브라우저 전체 설정도 같이 건다.
    for cmd in ("Browser.setDownloadBehavior", "Page.setDownloadBehavior"):
        try:
            driver.execute_cdp_cmd(cmd, {"behavior": "allow", "downloadPath": str(config.DOWNLOAD_DIR)})
        except Exception as e:
            print(f"  ({cmd} 설정 실패: {e.__class__.__name__} - 다른 방식으로 계속)")
    try:
        print("1) 리포트 페이지 여는 중...")
        open_report(driver)
        print("2) Time Frame 필터 설정 중...")
        set_time_frame_and_run(driver, from_date, to_date)
        print("3) Export 실행 중...")
        path = export_xls(driver)
        print(f"4) 다운로드 완료: {path}")
        return path
    finally:
        driver.close()
