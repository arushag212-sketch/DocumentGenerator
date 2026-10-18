"""Script to generate Phase W6a.1 evidence:
1. docs/screenshots/w6a/05_blocked_attempt.png (grouped missing list, nothing generated, disabled generate button with reasons)
2. docs/evidence/w6a1_permission_letter.txt (extracted text from workshop batch Permission Letter PDF)
3. docs/evidence/w6a1_permission_letter.png (rendered PNG of workshop batch Permission Letter PDF)
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
TEMP_DB = Path("data/temp_w6a1.db")
os.environ["DATABASE_URL"] = f"sqlite:///{TEMP_DB.as_posix()}"

import pymupdf as fitz
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

    print("Step 1: Initializing isolated temporary database...")
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
    chrome_options.add_argument("--window-size=1600,1200")
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

        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'ACM Student Chapter')]")))
        time.sleep(1)

        print("Step 3: Navigating to Events Tab...")
        events_tab_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Events')]")))
        events_tab_btn.click()
        time.sleep(1.5)

        print("Step 4: Submitting workshop description...")
        desc_input = wait.until(EC.presence_of_element_located((By.TAG_NAME, "textarea")))
        desc_input.clear()
        desc_input.send_keys("We are conducting a two-day Web Development Workshop on 14-15 October in Seminar Hall for around 120 students.")
        time.sleep(0.5)

        analyze_btn = driver.find_element(By.XPATH, "//button[contains(., 'Analyze & Recommend Documents')]")
        analyze_btn.click()

        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Recommended Documents for this Event')]")))
        time.sleep(1.5)

        print("Step 5: Capturing blocked attempt screenshot (grouped missing list, nothing generated)...")
        # Scroll down so grouped missing info and disabled generate button are clearly visible
        driver.execute_script("window.scrollBy(0, 450);")
        time.sleep(1)

        shot_blocked = screenshots_dir / "05_blocked_attempt.png"
        driver.save_screenshot(str(shot_blocked))
        print(f"-> Saved {shot_blocked}")

        print("Step 6: Reviewing, accepting, and confirming required fields to generate...")
        # 1. Accept AI-drafted fields
        for btn in driver.find_elements(By.XPATH, "//button[contains(., 'Accept')]"):
            try:
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(0.3)
            except Exception as e:
                print("Accept btn error:", e)

        # 2. Confirm inferred dates
        for lbl in driver.find_elements(By.XPATH, "//label[contains(., 'Confirm inferred event year')]"):
            try:
                driver.execute_script("arguments[0].click();", lbl)
                time.sleep(0.3)
            except Exception as e:
                print("Inferred dates label error:", e)

        # 3. Confirm reference numbers
        for lbl in driver.find_elements(By.XPATH, "//label[contains(., 'Confirm reference numbers')]"):
            try:
                driver.execute_script("arguments[0].click();", lbl)
                time.sleep(0.3)
            except Exception as e:
                print("Ref numbers label error:", e)

        # 4. Fill required missing text inputs
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

        print("Step 7: Generating batch...")
        gen_btn = driver.find_element(By.XPATH, "//button[contains(., 'Generate Selected Documents')]")
        driver.execute_script("arguments[0].click();", gen_btn)

        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Batch Generation Complete')]")))
        time.sleep(2)

        print("Step 8: Locating generated Permission Letter PDF and extracting evidence...")
        doc_pdfs = list(Path("storage/documents").glob("*/*/*permission_letter*.pdf"))
        if not doc_pdfs:
            # Check batches zip
            zip_files = list(Path("storage/batches").glob("*/*.zip"))
            if zip_files:
                import zipfile
                latest_zip = max(zip_files, key=lambda f: f.stat().st_mtime)
                with zipfile.ZipFile(latest_zip, "r") as zf:
                    for name in zf.namelist():
                        if "permission_letter" in name.lower() and name.endswith(".pdf"):
                            extracted_path = Path("storage/batches") / name
                            extracted_path.write_bytes(zf.read(name))
                            doc_pdfs.append(extracted_path)
        if not doc_pdfs:
            raise FileNotFoundError("No permission_letter PDF found in storage/documents or storage/batches")

        latest_pdf = max(doc_pdfs, key=lambda f: f.stat().st_mtime)
        print(f"Found permission letter PDF: {latest_pdf}")

        # Extract text using PyMuPDF
        doc = fitz.open(str(latest_pdf))
        full_text = ""
        for i, page in enumerate(doc):
            full_text += f"--- Page {i + 1} ---\n"
            full_text += page.get_text() + "\n"

        txt_evidence = evidence_dir / "w6a1_permission_letter.txt"
        txt_evidence.write_text(full_text, encoding="utf-8")
        print(f"-> Saved {txt_evidence} ({len(full_text)} characters)")

        # Render first page as PNG using PyMuPDF
        page0 = doc[0]
        pix = page0.get_pixmap(dpi=150)
        png_evidence = evidence_dir / "w6a1_permission_letter.png"
        pix.save(str(png_evidence))
        print(f"-> Saved {png_evidence} ({png_evidence.stat().st_size} bytes)")

        print("Part A completed successfully!")
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
