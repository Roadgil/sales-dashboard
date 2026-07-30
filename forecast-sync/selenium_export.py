"""
Salesforce 리포트(KS_251219, 00OPY00000F4ckP)에 로그인해서
Time Frame(Close Date) 필터를 From=고정값 / To=계산된 날짜로 맞추고
엑셀(.xls) 형태로 Export/다운로드하는 스크립트.

주의: Lightning 리포트 필터/Export UI의 정확한 선택자는 실제 조직(org) 화면을
직접 보고 검증한 것이 아니라 Salesforce 표준 Lightning 컴포넌트 패턴을 기반으로
작성했습니다. 조직의 커스터마이징에 따라 동작하지 않을 수 있어, 자동화가 실패하는
단계에서는 화면을 캡처하고 사용자가 브라우저에서 직접 마무리할 수 있도록 일시정지합니다.
"""
import time
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

import config

LOGIN_URL = "https://candelamedical.my.salesforce.com"


def fmt_date_kr(d):
    # 리포트에 표시되는 "2026. 7. 3" 포맷과 동일하게 (0 패딩 없이)
    return f"{d.year}. {d.month}. {d.day}"


def build_driver():
    # 회사 PC의 Windows 보안 정책이 Selenium이 자동 다운로드하는 chromedriver.exe 실행을
    # 차단해서, 대신 Windows에 기본 내장되어 신뢰된 Edge(msedgedriver)를 사용한다.
    options = webdriver.EdgeOptions()
    if config.HEADLESS:
        options.add_argument("--headless=new")
    options.add_experimental_option(
        "prefs",
        {
            "download.default_directory": str(config.DOWNLOAD_DIR),
            "download.prompt_for_download": False,
            "safebrowsing.enabled": True,
        },
    )
    return webdriver.Edge(options=options)


def screenshot(driver, name):
    path = config.BASE_DIR / f"error_{name}.png"
    try:
        driver.save_screenshot(str(path))
        print(f"  (스크린샷 저장: {path})")
    except Exception:
        pass


def _already_logged_in(driver):
    url = driver.current_url
    return any(k in url for k in ["/home/home.jsp", "/lightning/", "/one/one.app"])


def login(driver):
    driver.get(LOGIN_URL)
    wait = WebDriverWait(driver, 20)

    # 회사 SSO로 이미 로그인된 세션이면 곧바로 홈/Lightning으로 리다이렉트되어
    # username 입력창 자체가 안 나타날 수 있다 - 그 경우는 그대로 통과.
    try:
        wait.until(lambda d: d.find_elements(By.ID, "username") or _already_logged_in(d))
    except TimeoutException:
        pass

    if _already_logged_in(driver):
        print("  이미 로그인된 세션이라 로그인 단계 건너뜀.")
        return

    username_fields = driver.find_elements(By.ID, "username")
    if not username_fields:
        screenshot(driver, "login_page_unrecognized")
        input(
            "\n[확인 필요] 로그인 입력창을 못 찾았습니다. 브라우저에서 상태를 확인하고, "
            "로그인되어 있다면 그냥 Enter, 로그인 화면이면 직접 로그인 후 Enter를 눌러주세요...\n"
        )
        return

    username_fields[0].send_keys(config.SF_USERNAME)
    driver.find_element(By.ID, "password").send_keys(config.SF_PASSWORD)
    driver.find_element(By.ID, "Login").click()

    time.sleep(3)
    if any(k in driver.current_url for k in ["/secur/", "identity", "challenge"]) or _has_text(driver, "Verify"):
        screenshot(driver, "mfa_prompt")
        input(
            "\n[MFA 확인 필요] 브라우저에서 2단계 인증을 완료한 뒤, "
            "정상적으로 로그인된 화면이 보이면 여기서 Enter를 눌러주세요...\n"
        )


def _has_text(driver, text):
    try:
        return text in driver.page_source
    except Exception:
        return False


def open_report(driver):
    driver.get(config.SF_REPORT_URL)
    WebDriverWait(driver, 30).until(
        lambda d: "Report" in d.current_url or _has_text(d, "Time Frame")
    )
    time.sleep(3)


def set_time_frame(driver, from_date, to_date):
    """Time Frame 필터의 Custom 범위를 From/To로 설정. 실패 시 수동 개입으로 폴백."""
    wait = WebDriverWait(driver, 15)
    try:
        # Time Frame 필터 행의 편집(연필) 버튼 찾기
        edit_btn = wait.until(
            EC.element_to_be_clickable(
                (By.XPATH, "//*[contains(text(),'Time Frame')]/ancestor::*[self::li or self::div][1]//button")
            )
        )
        edit_btn.click()
        time.sleep(1)

        # Range 콤보박스에서 Custom 선택
        range_combo = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//label[contains(text(),'Range')]/following::select[1]"))
        )
        for option in range_combo.find_elements(By.TAG_NAME, "option"):
            if "Custom" in option.text:
                option.click()
                break
        time.sleep(0.5)

        from_input = driver.find_element(
            By.XPATH, "//label[contains(text(),'Start') or contains(text(),'From')]/following::input[1]"
        )
        from_input.clear()
        from_input.send_keys(fmt_date_kr(from_date))
        from_input.send_keys(Keys.TAB)

        to_input = driver.find_element(
            By.XPATH, "//label[contains(text(),'End') or contains(text(),'To')]/following::input[1]"
        )
        to_input.clear()
        to_input.send_keys(fmt_date_kr(to_date))
        to_input.send_keys(Keys.TAB)

        apply_btn = driver.find_element(By.XPATH, "//button[contains(text(),'Apply')]")
        apply_btn.click()
        time.sleep(3)
        print(f"  Time Frame 자동 설정 완료: {fmt_date_kr(from_date)} ~ {fmt_date_kr(to_date)}")
        return
    except (NoSuchElementException, TimeoutException) as e:
        screenshot(driver, "time_frame_fail")
        print(f"  Time Frame 자동 설정 실패 ({e.__class__.__name__}).")

    input(
        f"\n[수동 설정 필요] 브라우저에서 직접 Time Frame 필터를 "
        f"From = {fmt_date_kr(from_date)}, To = {fmt_date_kr(to_date)} 로 설정하고 "
        f"Apply까지 누른 뒤, 여기서 Enter를 눌러주세요...\n"
    )


def export_xls(driver):
    """Export 메뉴에서 Formatted Report(.xls)로 다운로드 트리거. 실패 시 수동 폴백."""
    before = set(p.name for p in config.DOWNLOAD_DIR.glob("*"))
    wait = WebDriverWait(driver, 15)
    try:
        menu_btn = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//button[@title='List View Controls' or @title='Show more actions']"))
        )
        menu_btn.click()
        time.sleep(1)
        export_item = driver.find_element(By.XPATH, "//*[contains(text(),'Export')]")
        export_item.click()
        time.sleep(1)

        export_confirm_btn = driver.find_element(By.XPATH, "//button[contains(text(),'Export')]")
        export_confirm_btn.click()
        print("  Export 자동 클릭 완료. 다운로드 대기 중...")
    except (NoSuchElementException, TimeoutException) as e:
        screenshot(driver, "export_fail")
        print(f"  Export 자동 클릭 실패 ({e.__class__.__name__}).")
        input(
            "\n[수동 진행 필요] 브라우저에서 직접 Export > Details Only 또는 Formatted Report(.xls) 로 "
            "다운로드를 실행한 뒤, 여기서 Enter를 눌러주세요...\n"
        )

    return wait_for_new_file(before)


def wait_for_new_file(before_names, timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        current = list(config.DOWNLOAD_DIR.glob("*"))
        new_files = [p for p in current if p.name not in before_names and not p.name.endswith(".crdownload")]
        if new_files:
            newest = max(new_files, key=lambda p: p.stat().st_mtime)
            return newest
        time.sleep(1)
    raise TimeoutError(f"{config.DOWNLOAD_DIR} 에서 새 다운로드 파일을 찾지 못했습니다 ({timeout}초 대기).")


def run_export(from_date, to_date):
    driver = build_driver()
    try:
        print("1) 로그인 중...")
        login(driver)
        print("2) 리포트 페이지 여는 중...")
        open_report(driver)
        print("3) Time Frame 필터 설정 중...")
        set_time_frame(driver, from_date, to_date)
        print("4) Export 실행 중...")
        path = export_xls(driver)
        print(f"5) 다운로드 완료: {path}")
        return path
    finally:
        driver.quit()
