"""Script to capture Phase W6a screenshots in an isolated database:
1. 01_recommendations.png: "Describe your event" box with extracted parameters and recommended documents checklist.
2. 02_grouped_missing_panel.png: Grouped missing-info panel with needed_by badges and defer_ok flags.
3. 03_generation_progress_and_complete.png: Batch generation completion card with ZIP download and document reference numbers.
4. 04_documents_list_page.png: Documents library page with search, filters, sorting, status badges, and pagination.
"""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
import zipfile
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# CRITICAL: Isolate from data/clubdocs.db
TEMP_DB = Path("data/temp_screenshot_w6a.db")
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
    screenshots_dir = Path("docs/screenshots/w6a")
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    evidence_dir = Path("docs/evidence")
    evidence_dir.mkdir(parents=True, exist_ok=True)

    print("Step 1: Seeding isolated temporary database for W6a screenshots...")
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
    chrome_options.add_argument("--window-size=1600,1100")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")

    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 25)

    try:
        print("Step 2: Logging in as demo club owner...")
        driver.get(base_url)
        email_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email']")))
        email_input.clear()
        email_input.send_keys("demo.owner@svnit.ac.in")

        pass_input = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
        pass_input.clear()
        pass_input.send_keys("DemoOwnerPass123!")

        submit_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        submit_btn.click()

        # Wait for dashboard
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'ACM Student Chapter')]")))
        time.sleep(1)

        print("Step 3: Navigating to Events Tab...")
        events_tab_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Events')]")))
        events_tab_btn.click()
        time.sleep(1.5)

        print("Step 4: Submitting event description...")
        desc_input = wait.until(EC.presence_of_element_located((By.TAG_NAME, "textarea")))
        desc_input.clear()
        desc_input.send_keys("We are conducting a two-day Web Development Workshop on 14-15 October in Seminar Hall for around 120 students.")
        time.sleep(0.5)

        analyze_btn = driver.find_element(By.XPATH, "//button[contains(., 'Analyze & Recommend Documents')]")
        analyze_btn.click()

        # Wait for recommendations to render
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Recommended Documents for this Event')]")))
        time.sleep(1.5)

        # Screenshot 1: Recommendations
        shot1 = screenshots_dir / "01_recommendations.png"
        driver.save_screenshot(str(shot1))
        print(f"-> Saved {shot1}")

        # Screenshot 2: Grouped Missing-Info Panel
        # Scroll down slightly to center the grouped missing info panel
        driver.execute_script("window.scrollBy(0, 350);")
        time.sleep(1)
        shot2 = screenshots_dir / "02_grouped_missing_panel.png"
        driver.save_screenshot(str(shot2))
        print(f"-> Saved {shot2}")

        print("Step 5: Reviewing and confirming required parameters...")
        # Scroll to grouped missing info
        driver.execute_script("window.scrollBy(0, 300);")
        time.sleep(1)

        # 1. Accept any AI-drafted fields
        for btn in driver.find_elements(By.XPATH, "//button[contains(., 'Accept')]"):
            try:
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(0.3)
            except Exception as e:
                print("Accept btn click exc:", e)

        # 2. Confirm inferred dates
        for lbl in driver.find_elements(By.XPATH, "//label[contains(., 'Confirm inferred event year')]"):
            try:
                driver.execute_script("arguments[0].click();", lbl)
                time.sleep(0.3)
            except Exception as e:
                print("Inferred dates label click exc:", e)

        # 3. Confirm reference numbers to be reserved
        for lbl in driver.find_elements(By.XPATH, "//label[contains(., 'Confirm reference numbers')]"):
            try:
                driver.execute_script("arguments[0].click();", lbl)
                time.sleep(0.3)
            except Exception as e:
                print("Ref numbers label click exc:", e)

        # 4. Fill required missing text inputs if empty
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

        for el in driver.find_elements(By.XPATH, "//*[contains(text(), 'Generate disabled')]"):
            print("DISABLED NOTICE FOUND:", el.text)

        print("Triggering Batch Document Generation...")
        gen_btn = driver.find_element(By.XPATH, "//button[contains(., 'Generate Selected Documents')]")
        print("gen_btn disabled state:", gen_btn.get_attribute("disabled"))
        if gen_btn.get_attribute("disabled"):
            # If still disabled, click labels again or force click
            for lbl in driver.find_elements(By.XPATH, "//label[contains(., 'Confirm')]"):
                driver.execute_script("arguments[0].click();", lbl)
                time.sleep(0.3)
            print("gen_btn disabled state after re-click:", gen_btn.get_attribute("disabled"))

        driver.execute_script("arguments[0].click();", gen_btn)

        # Wait for completion card
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Batch Generation Complete')]")))
        time.sleep(1.5)

        # Scroll down to completion card
        driver.execute_script("window.scrollBy(0, 300);")
        time.sleep(1)
        shot3 = screenshots_dir / "03_generation_progress_and_complete.png"
        driver.save_screenshot(str(shot3))
        print(f"-> Saved {shot3}")

        print("Step 6: Navigating to Documents Library Tab...")
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(0.5)
        docs_tab_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Documents')]")))
        docs_tab_btn.click()

        # Wait for document table
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Documents Library')]")))
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))
        time.sleep(1.5)

        shot4 = screenshots_dir / "04_documents_list_page.png"
        driver.save_screenshot(str(shot4))
        print(f"-> Saved {shot4}")

        print("Step 7: Creating ZIP file listing evidence for workshop and 3-winner prize batches...")
        # 1. Capture the Workshop batch ZIP
        batches_dir = Path("storage/batches")
        workshop_zip = None
        if batches_dir.exists():
            zip_files = list(batches_dir.glob("*/*.zip"))
            if zip_files:
                workshop_zip = max(zip_files, key=lambda f: f.stat().st_mtime)

        # 2. Generate a 3-winner prize batch via API in the same isolated DB
        import requests
        login_res = requests.post(
            f"{base_url}/api/v1/auth/login",
            json={"email": "demo.owner@svnit.ac.in", "password": "DemoOwnerPass123!"},
        )
        token = login_res.json()["access_token"]
        api_headers = {"Authorization": f"Bearer {token}"}
        clubs_res = requests.get(f"{base_url}/api/v1/clubs", headers=api_headers)
        acm_id = next(c["id"] for c in clubs_res.json() if "ACM" in c["name"])

        prize_payload = {
            "selected_template_ids": ["prize_money_receipt"],
            "event_data": {
                "event_name": "Web Development Workshop Hackathon",
                "dates": "15 October 2026",
                "date_start": "2026-10-15",
                "date_end": "2026-10-15",
                "dates_confirmed": True,
                "venue": "Seminar Hall",
                "winners": [
                    {"position": "1st Place", "name": "Aarav Gupta", "roll_no": "U22CS001", "amount": 5000},
                    {"position": "2nd Place", "name": "Diya Shah", "roll_no": "U22CS002", "amount": 3000},
                    {"position": "3rd Place", "name": "Kavya Patel", "roll_no": "U22CS003", "amount": 2000},
                ],
            },
            "event_title": "Web Development Workshop Hackathon",
        }
        res_prize = requests.post(
            f"{base_url}/api/v1/clubs/{acm_id}/events/generate-batch",
            json=prize_payload,
            headers=api_headers,
        )
        prize_data = res_prize.json()
        prize_zip = Path(prize_data["zip_path"])

        # Write combined listing text
        listing_text = "================================================================================\n"
        listing_text += "PHASE W6a REAL BATCH RUN EVIDENCE: ZIP ARCHIVES AND SIZES\n"
        listing_text += "================================================================================\n\n"

        if workshop_zip and workshop_zip.exists():
            with zipfile.ZipFile(str(workshop_zip), "r") as zf:
                listing_text += f"1. Web Development Workshop Batch (Permission Letter)\n"
                listing_text += f"   Prompt: \"We are conducting a two-day Web Development Workshop on 14-15 October in Seminar Hall for around 120 students.\"\n"
                listing_text += f"   ZIP File: {workshop_zip.name}\n"
                listing_text += f"   Total Size: {workshop_zip.stat().st_size} bytes\n"
                listing_text += f"   Archive Contents ({len(zf.infolist())} files):\n"
                for info in sorted(zf.infolist(), key=lambda x: x.filename):
                    listing_text += f"     - {info.filename:45s}  Size: {info.file_size:8d} bytes  (Compressed: {info.compress_size:8d} bytes)\n"
                listing_text += "\n"

        if prize_zip and prize_zip.exists():
            with zipfile.ZipFile(str(prize_zip), "r") as zf:
                listing_text += f"2. 3-Winner Prize Batch (Prize Money Receipts)\n"
                listing_text += f"   Event: Web Development Workshop Hackathon (3 Winners: Aarav Gupta, Diya Shah, Kavya Patel)\n"
                listing_text += f"   ZIP File: {prize_zip.name}\n"
                listing_text += f"   Total Size: {prize_zip.stat().st_size} bytes\n"
                listing_text += f"   Archive Contents ({len(zf.infolist())} files):\n"
                for info in sorted(zf.infolist(), key=lambda x: x.filename):
                    listing_text += f"     - {info.filename:45s}  Size: {info.file_size:8d} bytes  (Compressed: {info.compress_size:8d} bytes)\n"
                listing_text += "\n"

        listing_path = evidence_dir / "w6a_zip_listing.txt"
        listing_path.write_text(listing_text, encoding="utf-8")
        print(f"-> Saved {listing_path}")

        print("All screenshots and evidence captured successfully!")
    finally:
        driver.quit()
        if TEMP_DB.exists():
            try:
                TEMP_DB.unlink()
                print(f"Cleaned up {TEMP_DB}")
            except Exception:
                pass


if __name__ == "__main__":
    main()
