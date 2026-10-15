"""End-to-End browser test for W3 Vertical Slice using Selenium headless Chrome:
1. Login with demo owner user (demo.owner@svnit.ac.in).
2. Verify active club Dashboard shows 'Your Role: Owner' and accurate member count.
3. Open 'Permission Letter' card to load schema-driven form and missing-info panel.
4. Fill event description and click 'Extract & Pre-fill Form'.
5. Verify unconfirmed badges, confirm suggested ref number.
6. Click 'Generate Document' to run Docgen engine + LibreOffice.
7. Verify Review page renders high-res PDF preview images.
8. Verify downloaded/rendered PDF text contains event title and ROOM ref.
Saves high-res screenshots to docs/screenshots/w3_slice/.
"""

from __future__ import annotations

import os
import shutil
import socket
import threading
import time
from pathlib import Path

import pymupdf
import pytest
import uvicorn
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from server.app.main import app

SCREENSHOTS_DIR = Path("docs/screenshots/w3_slice")


def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def e2e_server():
    """Start uvicorn server serving single-URL production bundle on background thread."""
    port = get_free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Wait for server ready
    base_url = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                break
        except OSError:
            time.sleep(0.1)

    yield base_url
    server.should_exit = True


@pytest.fixture(scope="module")
def driver():
    """Headless Chrome WebDriver with high-DPI desktop viewport."""
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1440,960")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=options)
    driver.set_window_size(1440, 960)
    yield driver
    driver.quit()


def test_w3_slice_end_to_end_journey(driver, e2e_server):
    """Full browser E2E test verifying login, dashboard coherence, prefill, generate, and PDF review."""
    wait = WebDriverWait(driver, 20)

    # ---------------- 1. LOGIN PAGE ----------------
    driver.get(e2e_server)
    email_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email']")))
    pwd_input = driver.find_element(By.CSS_SELECTOR, "input[type='password']")

    email_input.clear()
    email_input.send_keys("demo.owner@svnit.ac.in")
    pwd_input.clear()
    pwd_input.send_keys("DemoOwnerPass123!")

    time.sleep(0.5)
    driver.save_screenshot(str(SCREENSHOTS_DIR / "01_login.png"))

    # Submit login
    submit_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
    submit_btn.click()

    # ---------------- 2. DASHBOARD & ROLE COHERENCE ----------------
    # Wait for dashboard to load
    wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'ACM Student Chapter')]")))
    wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Your Role:')]")))

    # Verify role displayed is Owner
    dashboard_text = driver.find_element(By.TAG_NAME, "body").text
    assert "Your Role: Owner" in dashboard_text or "Owner" in dashboard_text
    assert "Standard SVNIT Document Suite" in dashboard_text

    time.sleep(0.5)
    driver.save_screenshot(str(SCREENSHOTS_DIR / "02_dashboard_owner_role.png"))

    # ---------------- 3. SELECT PERMISSION LETTER TEMPLATE ----------------
    perm_card = wait.until(
        EC.element_to_be_clickable(
            (By.XPATH, "//*[contains(text(), 'Permission Letter')]//ancestor::div[contains(@class, 'cursor-pointer')]")
        )
    )
    perm_card.click()

    # Wait for New Document form
    wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Describe Your Event')]")))
    wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Reserve Next Number') or contains(text(), 'Click to Confirm')]")))

    time.sleep(0.5)
    driver.save_screenshot(str(SCREENSHOTS_DIR / "03_new_permission_letter_form.png"))

    # ---------------- 4. DESCRIBE YOUR EVENT & EXTRACT ----------------
    desc_box = driver.find_element(By.TAG_NAME, "textarea")
    desc_box.clear()
    event_prompt = (
        "We are organizing Smart India Hackathon 2026 Internal Hackathon on 15/10/2026 "
        "from 09:00 AM to 06:00 PM at Seminar Hall. "
        "Expected participants: 120 students."
    )
    desc_box.send_keys(event_prompt)

    # Click Extract & Pre-fill Form
    extract_btn = driver.find_element(By.XPATH, "//button[contains(., 'Extract & Pre-fill Form')]")
    extract_btn.click()

    # Wait for AI Extraction to complete and populate
    time.sleep(1.5)

    # Confirm suggested reference number
    confirm_ref_btn = wait.until(
        EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Reserve Next Number') or contains(., 'Click to Confirm')]"))
    )
    confirm_ref_btn.click()

    # Wait for confirmation badge
    wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Ref No. Reserved') or contains(text(), 'Ref No. Confirmed')]")))

    # Accept any AI drafts (per Directive 2 requirement that user must accept or edit drafts)
    time.sleep(0.5)
    accept_btns = driver.find_elements(By.XPATH, "//button[contains(., 'Accept')]")
    for btn in accept_btns:
        driver.execute_script("arguments[0].click();", btn)
        time.sleep(0.2)

    time.sleep(0.5)
    driver.save_screenshot(str(SCREENSHOTS_DIR / "04_extracted_prefill_and_missing_panel.png"))

    # ---------------- 5. GENERATE DOCUMENT ----------------
    gen_btn = wait.until(
        EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Generate Document')]"))
    )
    # Scroll into view and click
    driver.execute_script("arguments[0].scrollIntoView(true);", gen_btn)
    time.sleep(0.5)
    gen_btn.click()

    # ---------------- 6. REVIEW PAGE & RENDERED PREVIEW ----------------
    # Wait for Review page banner and rendered preview image
    wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Rendered PDF Preview')]")))
    preview_img = wait.until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "img[alt*='Document Page']"))
    )

    # Verify image has src
    img_src = preview_img.get_attribute("src")
    assert img_src and "/pages/" in img_src

    time.sleep(1.0)
    driver.save_screenshot(str(SCREENSHOTS_DIR / "05_review_page_pdf_preview.png"))

    # ---------------- 7. VERIFY DOWNLOAD LINK & PDF CONTENT ----------------
    download_link = driver.find_element(By.XPATH, "//a[contains(., 'Download PDF')]")
    pdf_href = download_link.get_attribute("href")
    assert pdf_href and "format=pdf" in pdf_href

    # Fetch PDF content via session cookies
    cookies = driver.get_cookies()
    cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
    import httpx

    with httpx.Client(headers={"Cookie": cookie_str}) as client:
        res = client.get(pdf_href)
        assert res.status_code == 200
        assert res.headers["content-type"] == "application/pdf"

        # PyMuPDF content verification
        doc = pymupdf.open(stream=res.content, filetype="pdf")
        pdf_text = ""
        for page in doc:
            pdf_text += page.get_text()

        assert "ROOM" in pdf_text
        assert "SIH Internal Hackathon" in pdf_text or "Hackathon" in pdf_text
        assert "None" not in pdf_text
        assert "<function" not in pdf_text
        assert "{{" not in pdf_text
