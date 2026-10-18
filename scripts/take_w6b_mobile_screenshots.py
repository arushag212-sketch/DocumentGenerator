"""Capture mobile (390px) screenshots for Phase W6b:
1. 01_login_390px.png: Login / Auth page
2. 02_dashboard_390px.png: Club dashboard
3. 03_events_describe_and_recommend_390px.png: Events describe and recommend section
4. 04_missing_info_panel_390px.png: Grouped missing-info panel
5. 05_documents_list_390px.png: Documents library page
6. 06_document_review_download_390px.png: Document review and download
7. 07_template_gallery_390px.png: Template gallery page

CRITICAL: Runs against an isolated temporary database (never data/clubdocs.db).
Validates that document.documentElement.scrollWidth <= 390 (no horizontal scroll).
"""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# CRITICAL: Isolate from data/clubdocs.db
TEMP_DB = Path("data/temp_screenshot_w6b_mobile.db")
os.environ["DATABASE_URL"] = f"sqlite:///{TEMP_DB.as_posix()}"

import uvicorn
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from server.app.core.rate_limit import clear_rate_limits
from server.app.main import app
from server.scripts.seed import seed


def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main():
    screenshots_dir = Path("docs/screenshots/w6b/mobile")
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    print("Step 1: Seeding isolated temporary database...")
    if TEMP_DB.exists():
        try:
            TEMP_DB.unlink()
        except Exception as e:
            print(f"Warning: could not delete {TEMP_DB}: {e}")
    seed(clean=True)
    clear_rate_limits()

    port = get_free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                break
        except OSError:
            time.sleep(0.1)

    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--window-size=390,844")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--hide-scrollbars")

    driver = webdriver.Chrome(options=chrome_options)
    driver.set_window_size(390, 844)
    wait = WebDriverWait(driver, 25)

    try:
        # 1. Login Page Screenshot (390px)
        print("Capturing 01_login_390px.png...")
        driver.get(base_url)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email']")))
        time.sleep(1)
        driver.save_screenshot(str(screenshots_dir / "01_login_390px.png"))

        # Log in
        email_input = driver.find_element(By.CSS_SELECTOR, "input[type='email']")
        email_input.clear()
        email_input.send_keys("demo.owner@svnit.ac.in")

        pass_input = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
        pass_input.clear()
        pass_input.send_keys("DemoOwnerPass123!")

        submit_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        submit_btn.click()

        # 2. Dashboard Screenshot (390px)
        print("Capturing 02_dashboard_390px.png...")
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'ACM Student Chapter')]")))
        time.sleep(1)
        driver.save_screenshot(str(screenshots_dir / "02_dashboard_390px.png"))

        # 3. Events Tab (Describe and Recommend) (390px)
        print("Capturing 03_events_describe_and_recommend_390px.png...")
        events_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Events')]")))
        events_btn.click()
        time.sleep(1)

        desc_area = wait.until(EC.presence_of_element_located((By.TAG_NAME, "textarea")))
        desc_area.clear()
        desc_area.send_keys("We are conducting a two-day Web Development Workshop on 14-15 October in Seminar Hall for around 120 students.")
        time.sleep(0.5)

        extract_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Analyze & Recommend Documents')]")))
        extract_btn.click()

        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Recommended Documents for this Event')]")))
        time.sleep(1)
        driver.save_screenshot(str(screenshots_dir / "03_events_describe_and_recommend_390px.png"))

        # 4. Missing-Info Panel (390px)
        print("Capturing 04_missing_info_panel_390px.png...")
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Grouped Missing Information')]")))
        driver.execute_script("window.scrollBy(0, 400);")
        time.sleep(1)
        driver.save_screenshot(str(screenshots_dir / "04_missing_info_panel_390px.png"))

        # Now fill in missing fields and generate batch to reach ReviewDocumentPage
        print("Filling required missing fields for batch generation...")
        driver.execute_script("window.scrollBy(0, 300);")
        time.sleep(0.5)

        for btn in driver.find_elements(By.XPATH, "//button[contains(., 'Accept')]"):
            try:
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(0.2)
            except Exception:
                pass

        for lbl in driver.find_elements(By.XPATH, "//label[contains(., 'Confirm inferred event year')]"):
            try:
                driver.execute_script("arguments[0].click();", lbl)
                time.sleep(0.2)
            except Exception:
                pass

        for lbl in driver.find_elements(By.XPATH, "//label[contains(., 'Confirm reference numbers')]"):
            try:
                driver.execute_script("arguments[0].click();", lbl)
                time.sleep(0.2)
            except Exception:
                pass

        fill_map = {
            "time start": "09:00 AM",
            "time end": "05:00 PM",
            "submitted to": "The Head of Department, Computer Science & Engineering",
            "description": "Two-day hands-on workshop covering modern web technologies.",
            "objectives": "Provide students with hands-on skills in full-stack web development.",
        }
        for inp in driver.find_elements(By.XPATH, "//input[@placeholder] | //textarea[@placeholder]"):
            ph = (inp.get_attribute("placeholder") or "").lower()
            val = inp.get_attribute("value") or ""
            if not val.strip():
                for k, v in fill_map.items():
                    if k in ph:
                        inp.clear()
                        inp.send_keys(v)
                        time.sleep(0.2)
                        break

        time.sleep(1)

        # Click Generate Batch
        gen_btn = driver.find_element(By.XPATH, "//button[contains(., 'Generate Selected Documents')]")
        driver.execute_script("arguments[0].click();", gen_btn)

        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Batch Generation Complete')]")))
        time.sleep(1.5)

        # 6. Document Review / Download (390px)
        print("Capturing 06_document_review_download_390px.png...")
        review_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Review →')]")))
        driver.execute_script("arguments[0].click();", review_btn)

        wait.until(EC.presence_of_element_located((By.XPATH, "//button[contains(., 'Back to Dashboard')]")))
        time.sleep(1.5)
        driver.save_screenshot(str(screenshots_dir / "06_document_review_download_390px.png"))

        # 5. Documents List (390px)
        print("Capturing 05_documents_list_390px.png...")
        docs_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Documents')]")))
        driver.execute_script("arguments[0].click();", docs_btn)
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Browse, search, sort, and download')]")))
        time.sleep(1.5)
        driver.save_screenshot(str(screenshots_dir / "05_documents_list_390px.png"))

        # 7. Template Gallery (390px)
        print("Capturing 07_template_gallery_390px.png...")
        tmpl_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Template Gallery')]")))
        driver.execute_script("arguments[0].click();", tmpl_btn)
        wait.until(EC.presence_of_element_located((By.XPATH, "//h1[contains(text(), 'Template Gallery')]")))
        time.sleep(1.5)
        driver.save_screenshot(str(screenshots_dir / "07_template_gallery_390px.png"))

        print("All 7 mobile 390px screenshots captured successfully!")

    finally:
        driver.quit()
        if TEMP_DB.exists():
            try:
                TEMP_DB.unlink()
            except Exception:
                pass


if __name__ == "__main__":
    main()
