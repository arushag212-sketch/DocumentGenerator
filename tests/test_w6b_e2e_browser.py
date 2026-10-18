"""Phase W6b Full Browser E2E Test (Selenium, isolated DB, one test):
1. Register via invite link
2. Pick club / lands on active club dashboard
3. Describe the workshop event
4. See recommendations
5. Blocked attempt with missing list
6. Fill fields and confirm ref numbers and year
7. Generate batch
8. Download ZIP -> open the PDF text and check it
9. Open Documents list and search for it
10. Edit a field on the event and update documents -> new version v2
Save screenshots of every step to docs/screenshots/w6b/e2e/
"""

from __future__ import annotations

import io
import os
import socket
import threading
import time
import zipfile
from pathlib import Path
import pytest
import pymupdf as fitz
import uvicorn
from fastapi.testclient import TestClient
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from server.app.core.rate_limit import clear_rate_limits
from server.app.main import app
from server.app.models import Club, User


def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def e2e_server():
    """Start an ephemeral background uvicorn server for the browser test."""
    clear_rate_limits()
    port = get_free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{port}"
    for _ in range(60):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                break
        except OSError:
            time.sleep(0.1)

    yield base_url


@pytest.fixture(scope="module")
def browser():
    """Headless Chrome browser with desktop viewport."""
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--window-size=1600,1100")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--hide-scrollbars")

    driver = webdriver.Chrome(options=chrome_options)
    driver.set_window_size(1600, 1100)
    yield driver
    driver.quit()


def test_full_browser_e2e_flow(e2e_server, browser, db_session):
    base_url = e2e_server
    driver = browser
    wait = WebDriverWait(driver, 30)

    screenshots_dir = Path("docs/screenshots/w6b/e2e")
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    # --------------------------------------------------------------------------
    # Step 0: Admin creates an invite via API client
    # --------------------------------------------------------------------------
    client = TestClient(app)
    admin_login = client.post(
        "/api/v1/auth/login",
        json={"email": "demo.owner@svnit.ac.in", "password": "DemoOwnerPass123!"},
    )
    assert admin_login.status_code == 200
    token = admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {token}"}

    clubs = client.get("/api/v1/clubs/", headers=admin_headers).json()
    acm = next(c for c in clubs if c["short_name"] == "ACM")
    club_id = acm["id"]

    inv_res = client.post(
        f"/api/v1/clubs/{club_id}/invites",
        json={"role": "editor", "max_uses": 5, "expiry_days": 7},
        headers=admin_headers,
    )
    assert inv_res.status_code == 201
    invite_code = inv_res.json()["code"]

    # --------------------------------------------------------------------------
    # Step 1: Register via invite link
    # --------------------------------------------------------------------------
    invite_url = f"{base_url}/?invite={invite_code}"
    driver.get(invite_url)
    time.sleep(1.5)

    # Verify invite preview banner is visible
    wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), \"You've been invited!\")]")))

    # Fill register form
    name_input = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Student Lead']")))
    name_input.clear()
    name_input.send_keys("E2E Test Member")

    email_input = driver.find_element(By.XPATH, "//input[@placeholder='lead@example.com']")
    email_input.clear()
    unique_email = f"e2e.member.{int(time.time())}@svnit.ac.in"
    email_input.send_keys(unique_email)

    pass_input = driver.find_element(By.XPATH, "//input[@placeholder='Min 10 characters']")
    pass_input.clear()
    pass_input.send_keys("SecureE2EPass123!")

    # Screenshot 1: Register via invite
    driver.save_screenshot(str(screenshots_dir / "01_register_via_invite.png"))

    reg_btn = driver.find_element(By.XPATH, "//button[contains(., 'Create Account')]")
    reg_btn.click()

    # --------------------------------------------------------------------------
    # Step 2: Pick club / Active club dashboard
    # --------------------------------------------------------------------------
    wait.until(EC.presence_of_element_located((By.XPATH, "//button[contains(., 'Dashboard')]")))
    time.sleep(1.5)

    # Screenshot 2: Active club dashboard
    driver.save_screenshot(str(screenshots_dir / "02_active_club_dashboard.png"))

    # --------------------------------------------------------------------------
    # Step 3: Describe the workshop event
    # --------------------------------------------------------------------------
    events_tab_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Events')]")))
    events_tab_btn.click()
    time.sleep(1)

    desc_input = wait.until(EC.presence_of_element_located((By.TAG_NAME, "textarea")))
    desc_input.clear()
    event_sentence = "We are conducting a two-day Web Development Workshop on 14-15 October in Seminar Hall for around 120 students."
    desc_input.send_keys(event_sentence)
    time.sleep(0.5)

    # Screenshot 3: Describe event
    driver.save_screenshot(str(screenshots_dir / "03_describe_event.png"))

    # --------------------------------------------------------------------------
    # Step 4: See recommendations
    # --------------------------------------------------------------------------
    analyze_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Analyze & Recommend Documents')]")))
    analyze_btn.click()

    wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Recommended Documents for this Event')]")))
    time.sleep(1.5)

    # Screenshot 4: Recommendations
    driver.save_screenshot(str(screenshots_dir / "04_recommendations.png"))

    # --------------------------------------------------------------------------
    # Step 5: Blocked attempt with missing list
    # --------------------------------------------------------------------------
    wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Grouped Missing Information')]")))
    driver.execute_script("window.scrollBy(0, 450);")
    time.sleep(1)

    # Confirm Generate button is disabled
    gen_btn = driver.find_element(By.XPATH, "//button[contains(., 'Generate Selected Documents')]")
    assert not gen_btn.is_enabled(), "Generate button must be disabled when missing fields or unconfirmed items exist"

    # Screenshot 5: Blocked attempt
    driver.save_screenshot(str(screenshots_dir / "05_blocked_attempt.png"))

    # --------------------------------------------------------------------------
    # Step 6: Fill fields and confirm ref numbers and year
    # --------------------------------------------------------------------------
    # 1. Accept AI drafts
    for btn in driver.find_elements(By.XPATH, "//button[contains(., 'Accept')]"):
        try:
            driver.execute_script("arguments[0].click();", btn)
            time.sleep(0.2)
        except Exception:
            pass

    # 2. Confirm inferred event year
    for lbl in driver.find_elements(By.XPATH, "//label[contains(., 'Confirm inferred event year')]"):
        try:
            driver.execute_script("arguments[0].click();", lbl)
            time.sleep(0.2)
        except Exception:
            pass

    # 3. Confirm reference numbers
    for lbl in driver.find_elements(By.XPATH, "//label[contains(., 'Confirm reference numbers')]"):
        try:
            driver.execute_script("arguments[0].click();", lbl)
            time.sleep(0.2)
        except Exception:
            pass

    # 4. Fill required text inputs
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
                    time.sleep(0.1)
                    break

    time.sleep(1)

    # Screenshot 6: Filled and confirmed
    driver.save_screenshot(str(screenshots_dir / "06_filled_and_confirmed.png"))

    # --------------------------------------------------------------------------
    # Step 7: Generate batch
    # --------------------------------------------------------------------------
    gen_btn = driver.find_element(By.XPATH, "//button[contains(., 'Generate Selected Documents')]")
    assert gen_btn.is_enabled(), "Generate button must become enabled once all requirements are satisfied"
    driver.execute_script("arguments[0].click();", gen_btn)

    wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Batch Generation Complete')]")))
    time.sleep(1.5)

    # Screenshot 7: Batch generated
    driver.save_screenshot(str(screenshots_dir / "07_batch_generated.png"))

    # --------------------------------------------------------------------------
    # Step 8: Download ZIP -> open the PDF text and check it
    # --------------------------------------------------------------------------
    zip_link_elem = wait.until(EC.presence_of_element_located((By.XPATH, "//a[contains(., 'Download Complete ZIP')]")))
    zip_rel_url = zip_link_elem.get_attribute("href")
    assert zip_rel_url, "ZIP download URL must exist"

    # Fetch zip directly via backend client with auth headers
    browser_token = driver.execute_script("return localStorage.getItem('token');")
    token_to_use = browser_token or token
    zip_resp = client.get(zip_rel_url, headers={"Authorization": f"Bearer {token_to_use}"})
    assert zip_resp.status_code == 200
    zip_bytes = zip_resp.content

    # Inspect zip contents
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        file_names = zf.namelist()
        pdf_names = [f for f in file_names if f.endswith(".pdf")]
        assert len(pdf_names) >= 1, f"Expected at least 1 PDF in batch ZIP, found: {file_names}"

        # Find permission letter PDF
        perm_pdf_name = next((f for f in pdf_names if "permission" in f.lower() or "room" in f.lower()), pdf_names[0])
        perm_pdf_bytes = zf.read(perm_pdf_name)

        doc = fitz.open(stream=perm_pdf_bytes, filetype="pdf")
        pdf_text = "\n".join(page.get_text() for page in doc)

        # Check required contents in rendered PDF
        assert "Web Development Workshop" in pdf_text
        assert "Seminar Hall" in pdf_text
        assert "09:00 AM" in pdf_text
        assert "05:00 PM" in pdf_text

    # Screenshot 8: ZIP and PDF text verified
    driver.save_screenshot(str(screenshots_dir / "08_zip_download_and_pdf.png"))

    # --------------------------------------------------------------------------
    # Step 9: Open Documents list and search for it
    # --------------------------------------------------------------------------
    docs_tab_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Documents')]")))
    driver.execute_script("arguments[0].click();", docs_tab_btn)
    time.sleep(1.5)

    search_input = wait.until(EC.presence_of_element_located((By.XPATH, "//input[contains(@placeholder, 'Search by title')]")))
    search_input.clear()
    search_input.send_keys("Web Development Workshop")

    search_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Search')]")
    driver.execute_script("arguments[0].click();", search_btn)
    time.sleep(1.5)

    # Document should be listed in results
    wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Permission Letter')]")))

    # Screenshot 9: Documents list search
    driver.save_screenshot(str(screenshots_dir / "09_documents_list_search.png"))

    # --------------------------------------------------------------------------
    # Step 10: Edit a field on the event and update documents -> new version v2
    # --------------------------------------------------------------------------
    events_tab_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Events')]")))
    driver.execute_script("arguments[0].click();", events_tab_btn)
    time.sleep(1.5)

    # Scroll down to Active Campus Events
    driver.execute_script("window.scrollBy(0, 800);")
    time.sleep(1)

    edit_event_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Edit Event')]")))
    driver.execute_script("arguments[0].click();", edit_event_btn)
    time.sleep(1)

    # In modal: modify venue
    venue_input = wait.until(EC.presence_of_element_located((By.XPATH, "//label[contains(., 'Event Venue')]/following-sibling::input")))
    venue_input.clear()
    venue_input.send_keys("DoCSE Computer Center 1")

    # Save changes with cascade checkbox checked
    save_modal_btn = driver.find_element(By.XPATH, "//button[contains(., 'Save & Cascade')]")
    driver.execute_script("arguments[0].click();", save_modal_btn)

    # Wait for document version to update to v2
    wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'v2')]")))
    time.sleep(1.5)

    # Screenshot 10: Event updated v2
    driver.save_screenshot(str(screenshots_dir / "10_event_updated_v2.png"))

    print("Full browser E2E test completed successfully! All 10 screenshots captured.")
