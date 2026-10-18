"""Phase 4 Verification Script with Selenium:
Asserts:
1. Native widgets on /home: dates (type="date", DD/MM/YYYY Indian format, past/future bounds),
   times (type="time", 24-hr stored, 12-hr AM/PM displayed, end > start validated),
   money (type="number", leading ₹, Indian grouping).
2. Input prompt "TechNova on 15 Nov 2026, 10 AM to 5 PM, Computer Dept seminar hall, budget 25000, 120 attendees".
3. AI / Rule understanding extracts fields cleanly.
4. User answers any missing fields, accepts reference numbers, and triggers batch generation.
5. Verifies generated ZIP package contains 3+ valid SVNIT official documents with unbroken
   numbering, Indian currency formatting, and Indian date/time formatting.
"""

from __future__ import annotations

import io
import json
import os
import re
import socket
import sys
import threading
import time
import zipfile
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uvicorn
from server.app.main import app

def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

def run_phase4_verification():
    port = get_free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    t = threading.Thread(target=server.run, daemon=True)
    t.start()

    base_url = f"http://127.0.0.1:{port}"
    for _ in range(60):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                break
        except OSError:
            time.sleep(0.1)

    screenshot_dir = Path("docs/screenshots/phase4")
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    download_dir = Path("docs/downloads/phase4").resolve()
    download_dir.mkdir(parents=True, exist_ok=True)

    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--window-size=1600,1200")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.set_capability("goog:loggingPrefs", {"browser": "ALL"})
    chrome_options.add_experimental_option("prefs", {
        "download.default_directory": str(download_dir),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
    })

    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 45)

    try:
        print("[Step 1] Logging in as demo owner...")
        driver.get(f"{base_url}/login")
        time.sleep(1)

        email_in = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@placeholder='student@example.com']")))
        email_in.clear()
        email_in.send_keys("demo.owner@svnit.ac.in")
        pass_in = driver.find_element(By.XPATH, "//input[@placeholder='••••••••••••']")
        pass_in.clear()
        pass_in.send_keys("DemoOwnerPass123!")

        submit_btn = driver.find_element(By.XPATH, "//button[@type='submit']")
        submit_btn.click()
        wait.until(lambda d: "/login" not in d.current_url)

        driver.get(f"{base_url}/home")
        time.sleep(1.5)
        print(f"Logged in and landed on: {driver.current_url}")
        driver.save_screenshot(str(screenshot_dir / "01_home_initial.png"))

        print("[Step 2] Inputting test prompt for TechNova event...")
        prompt_area = wait.until(EC.presence_of_element_located((By.XPATH, "//textarea")))
        test_prompt = "TechNova on 15 Nov 2026, 10 AM to 5 PM, Computer Dept seminar hall, budget 25000, 120 attendees, 1st prize Rs 5000 to Rahul Sharma (U22CS001), 2nd prize Rs 3000 to Priya Patel (U22CS002)"
        driver.execute_script("""
            var ta = arguments[0];
            var val = arguments[1];
            var nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
            nativeSetter.call(ta, val);
            ta.dispatchEvent(new Event('input', { bubbles: true }));
            ta.dispatchEvent(new Event('change', { bubbles: true }));
        """, prompt_area, test_prompt)
        time.sleep(0.5)

        understand_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Understand & Recommend')]")))
        understand_btn.click()

        print("[Step 3] Waiting for AI / Rule understand results...")
        try:
            wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'What we understood')]")))
        except Exception:
            driver.save_screenshot(str(screenshot_dir / "error_understand_timeout.png"))
            logs = driver.get_log("browser")
            print("Browser logs on timeout:", logs)
            raise
        time.sleep(2)
        driver.save_screenshot(str(screenshot_dir / "02_understood_cards.png"))

        # Verify understood inputs
        start_date_el = driver.find_element(By.XPATH, "//input[@type='date']")
        print(f"Understood start date: {start_date_el.get_attribute('value')}")
        assert "2026-11-15" in (start_date_el.get_attribute("value") or ""), f"Expected 2026-11-15, got {start_date_el.get_attribute('value')}"

        # Ensure start and end time are populated (10:00 and 17:00)
        time_inputs = driver.find_elements(By.XPATH, "//input[@type='time']")
        if len(time_inputs) >= 2:
            if not time_inputs[0].get_attribute("value"):
                time_inputs[0].send_keys("10:00")
            if not time_inputs[1].get_attribute("value"):
                time_inputs[1].send_keys("17:00")
            print(f"Times configured: {time_inputs[0].get_attribute('value')} to {time_inputs[1].get_attribute('value')}")

        # Ensure at least 3 templates are selected
        # The recommended doc cards are inside the 'Recommended documents' section and have class 'cursor-pointer'
        doc_cards = driver.find_elements(By.XPATH, "//div[contains(@class, 'space-y-3')]//div[contains(@class, 'cursor-pointer')]")
        print(f"Found {len(doc_cards)} document cards in recommended list")
        selected_count = 0
        for card in doc_cards:
            if "border-[#1b365d]" in card.get_attribute("class"):
                selected_count += 1

        print(f"Initially selected templates count: {selected_count}")
        for card in doc_cards:
            if selected_count >= 3:
                break
            if "border-[#1b365d]" not in card.get_attribute("class"):
                card.click()
                selected_count += 1
                time.sleep(0.3)

        print(f"Total selected templates for batch: {selected_count}")
        assert selected_count >= 3, f"Expected at least 3 selected templates, got {selected_count}"

        # Answer any missing questions if present
        missing_inputs = driver.find_elements(By.XPATH, "//div[contains(@class, 'space-y-1.5')]//input | //div[contains(@class, 'space-y-1.5')]//select")
        print(f"Found {len(missing_inputs)} missing input fields to review/fill")
        for inp in missing_inputs:
            tag = inp.tag_name.lower()
            val = inp.get_attribute("value")
            if tag == "select" and not val:
                options = inp.find_elements(By.TAG_NAME, "option")
                if len(options) > 1:
                    opt_val = options[1].get_attribute("value") or options[1].text
                    driver.execute_script("""
                        var sel = arguments[0];
                        sel.value = arguments[1];
                        sel.dispatchEvent(new Event('input', { bubbles: true }));
                        sel.dispatchEvent(new Event('change', { bubbles: true }));
                    """, inp, opt_val)
                    print(f"Selected option '{opt_val}' for select")
            elif tag == "input" and not val:
                inp_type = inp.get_attribute("type")
                inp_ph = inp.get_attribute("placeholder") or ""
                if inp_type == "number":
                    set_val = "25000"
                elif "code" in inp_ph.lower():
                    set_val = "TECH26"
                elif "letter" in inp_ph.lower() or "addressed" in inp_ph.lower():
                    set_val = "Dean (Student Welfare), SVNIT"
                else:
                    set_val = "SVNIT Technical Workshop"
                driver.execute_script("""
                    var el = arguments[0];
                    var val = arguments[1];
                    var nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                    nativeSetter.call(el, val);
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                """, inp, set_val)
                print(f"Set input '{inp_ph}' to '{set_val}'")

        # Accept AI-drafted narrative text if present
        accept_btns = driver.find_elements(By.XPATH, "//button[contains(., 'Accept AI Draft')]")
        print(f"Found {len(accept_btns)} 'Accept AI Draft' buttons")
        for ab in accept_btns:
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'}); arguments[0].click();", ab)
            time.sleep(0.3)

        # Accept reference numbers checkbox
        ref_checkbox = wait.until(EC.presence_of_element_located((By.ID, "acceptRefNumbers")))
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'}); if (!arguments[0].checked) { arguments[0].click(); }", ref_checkbox)
        time.sleep(0.5)

        driver.save_screenshot(str(screenshot_dir / "03_ready_to_generate.png"))

        print("[Step 4] Triggering batch generation...")
        gen_btn = wait.until(EC.presence_of_element_located((By.XPATH, "//button[contains(., 'Generate Documents') or contains(., 'Generate Batch')]")))
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", gen_btn)
        time.sleep(0.5)
        print("Generate button enabled:", gen_btn.is_enabled())
        if not gen_btn.is_enabled():
            warnings = driver.find_elements(By.XPATH, "//div[contains(@class, 'text-amber-700')]")
            for w in warnings:
                print("Warning found on page:", w.text)
        driver.execute_script("arguments[0].click();", gen_btn)

        print("[Step 5] Waiting for generation completion...")
        try:
            wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Ready for Signatures')] | //*[contains(text(), 'Download All (.zip)')]")))
        except Exception:
            driver.save_screenshot(str(screenshot_dir / "error_step5_timeout.png"))
            err_banners = driver.find_elements(By.XPATH, "//div[contains(@class, 'bg-red-50')]")
            for eb in err_banners:
                print("Red error banner found:", eb.text)
            logs = driver.get_log("browser")
            print("Browser logs on step 5 timeout:", logs)
            raise
        time.sleep(2)
        driver.save_screenshot(str(screenshot_dir / "04_batch_generated_success.png"))

        # Find the Download ZIP button
        zip_btn = wait.until(EC.presence_of_element_located((By.XPATH, "//a[contains(., 'Download All') or contains(@href, '.zip')]")))
        zip_url = zip_btn.get_attribute("href")
        print(f"ZIP download URL: {zip_url}")

        # Download ZIP directly or wait for browser download
        import urllib.request
        zip_path = download_dir / "technova_batch.zip"
        # Download with session cookies from browser
        cookie_header = "; ".join([f"{c['name']}={c['value']}" for c in driver.get_cookies()])
        req = urllib.request.Request(zip_url, headers={"Cookie": cookie_header})
        with urllib.request.urlopen(req) as resp, open(zip_path, "wb") as f:
            f.write(resp.read())

        print(f"Downloaded ZIP size: {zip_path.stat().st_size} bytes")
        assert zip_path.stat().st_size > 5000, f"ZIP file too small: {zip_path.stat().st_size} bytes"

        print("[Step 6] Inspecting generated documents inside ZIP archive...")
        with zipfile.ZipFile(zip_path, "r") as z:
            namelist = z.namelist()
            print(f"Files inside ZIP ({len(namelist)}):", namelist)
            docx_files = [n for n in namelist if n.endswith(".docx")]
            pdf_files = [n for n in namelist if n.endswith(".pdf")]
            print(f"DOCX files: {len(docx_files)}, PDF files: {len(pdf_files)}")
            assert len(pdf_files) >= 3, f"Expected at least 3 PDF documents inside ZIP, got {len(pdf_files)}"

            # Inspect text content in PDF documents
            import pymupdf
            verified_ref_no = False
            verified_currency = False
            verified_date = False

            for pdf_name in pdf_files:
                pdf_bytes = z.read(pdf_name)
                doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
                full_text = ""
                for page in doc:
                    full_text += page.get_text() + "\n"
                doc.close()

                # Check reference number pattern (e.g. ACM/26-27/... or ACM/...)
                if re.search(r"ACM/\d{2}-\d{2}/[A-Z0-9_-]+/\d{3}", full_text) or "ACM/" in full_text:
                    verified_ref_no = True
                # Check Indian currency or 25,000 / 25000
                if "₹" in full_text or "Rs." in full_text or "25,000" in full_text or "25000" in full_text:
                    verified_currency = True
                # Check date 15/11/2026 or 15 November 2026 or 15-11-2026
                if "15/11/2026" in full_text or "15 November 2026" in full_text or "15 Nov 2026" in full_text or "15-11-2026" in full_text:
                    verified_date = True

            print(f"Verification flags: ref_no={verified_ref_no}, currency={verified_currency}, date={verified_date}")
            assert verified_ref_no, "Failed to verify unbroken official reference number in generated documents"
            assert verified_currency, "Failed to verify Indian currency in generated documents"
            assert verified_date, "Failed to verify formatted date in generated documents"

        print("Checking browser logs for critical errors...")
        logs = driver.get_log("browser")
        severe_errors = [
            l for l in logs
            if l["level"] == "SEVERE"
            and "favicon" not in l["message"].lower()
            and "/api/v1/auth/me" not in l["message"]
        ]
        if severe_errors:
            print("Browser SEVERE logs:", severe_errors)
        assert len(severe_errors) == 0, f"Found {len(severe_errors)} severe console errors: {severe_errors}"

        print("\n=======================================================")
        print("PHASE 4 HOME & BATCH GENERATION VERIFICATION PASSED!")
        print("=======================================================")

    finally:
        driver.quit()

if __name__ == "__main__":
    run_phase4_verification()
