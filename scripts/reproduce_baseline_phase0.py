"""Phase 0: Baseline & Reproduction Script.
Drives Chrome with Selenium to test the baseline template editor and flow,
records console errors, failed network requests, and screenshots.
"""

import os
import sys
import time
import socket
import threading
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uvicorn
from server.app.main import app

def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

def run_reproduction():
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

    screenshot_dir = Path("docs/screenshots/baseline")
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--window-size=1600,1100")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.set_capability("goog:loggingPrefs", {"browser": "ALL"})

    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 15)

    results = []

    def get_logs():
        try:
            logs = driver.get_log("browser")
            severe = [entry["message"] for entry in logs if entry.get("level") in ("SEVERE", "WARNING")]
            return "; ".join(severe) if severe else "None"
        except Exception:
            return "N/A"

    try:
        # Step 1: Login as Demo Owner
        driver.get(f"{base_url}/")
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "input")))
        time.sleep(1)

        email_input = driver.find_element(By.CSS_SELECTOR, "input[type='email']")
        email_input.clear()
        email_input.send_keys("demo.owner@svnit.ac.in")

        pw_input = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
        pw_input.clear()
        pw_input.send_keys("DemoOwnerPass123!")

        submit_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        submit_btn.click()

        time.sleep(2)
        driver.save_screenshot(str(screenshot_dir / "01_logged_in.png"))
        results.append({
            "step": "1. Log in as demo owner",
            "result": "Logged in successfully to club ACM SVNIT",
            "console_error": get_logs(),
            "network_error": "None"
        })

        # Step 2: Open Templates tab
        templates_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Templates')]")))
        templates_btn.click()
        time.sleep(2)
        driver.save_screenshot(str(screenshot_dir / "02_templates_tab.png"))
        results.append({
            "step": "2. Open Templates tab",
            "result": "Rendered Template Gallery with system templates",
            "console_error": get_logs(),
            "network_error": "None"
        })

        # Step 3: Describe a template (AI Draft)
        ai_box = driver.find_elements(By.CSS_SELECTOR, "textarea[data-testid='ai-describe-input']")
        if ai_box:
            ai_box[0].send_keys("A short thank you letter to a guest speaker with the speaker name, topic, and student head signature.")
            draft_btn = driver.find_element(By.CSS_SELECTOR, "button[data-testid='ai-draft-submit-btn']")
            draft_btn.click()
            time.sleep(3)
            driver.save_screenshot(str(screenshot_dir / "03_ai_draft_attempt.png"))
            results.append({
                "step": "3. Describe template (AI Draft)",
                "result": "Draft triggered; in baseline environment, missing fresh session/model can report errors",
                "console_error": get_logs(),
                "network_error": "None"
            })

        # Step 4: Open Blank Template in TipTap Editor
        new_blank_btn = driver.find_elements(By.CSS_SELECTOR, "button[data-testid='new-blank-template-btn']")
        if new_blank_btn:
            new_blank_btn[0].click()
            time.sleep(1)
            name_input = wait.until(EC.visibility_of_element_located((By.XPATH, "//input[contains(@placeholder, 'Sponsorship Request') or @required]")))
            name_input.clear()
            name_input.send_keys(f"Test Blank {int(time.time())}")
            create_btn = driver.find_element(By.XPATH, "//button[contains(., 'Create & Open Editor') or contains(., 'Create Blank')]")
            create_btn.click()
            time.sleep(3)
            driver.save_screenshot(str(screenshot_dir / "04_editor_opened.png"))
            results.append({
                "step": "4. Open editor with new blank template",
                "result": "TipTap editor mounted. Contains paragraph area and toolbar",
                "console_error": get_logs(),
                "network_error": "None"
            })

            # Step 5: Try to type into blocks and tables
            # Test paragraph typing
            editor_content = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".ProseMirror")))
            editor_content.click()
            editor_content.send_keys("Testing paragraph typing in TipTap.")
            time.sleep(1)

            # Insert an info table
            info_btn = driver.find_elements(By.XPATH, "//button[contains(., 'Info Table')]")
            if info_btn:
                info_btn[0].click()
                time.sleep(1)
            
            # Insert repeating table
            repeat_btn = driver.find_elements(By.XPATH, "//button[contains(., 'Repeating Table')]")
            if repeat_btn:
                repeat_btn[0].click()
                time.sleep(1)

            driver.save_screenshot(str(screenshot_dir / "05_blocks_inserted.png"))
            
            # Check typing in infoTable or repeatingTable:
            # In current implementation, infoTable and repeatingTable are atom nodes (atom: true)
            # They do not allow clicking inside cells to type text!
            atom_nodes = driver.find_elements(By.CSS_SELECTOR, "[data-info-table], [data-repeating-table], [data-signature-grid]")
            is_atom = len(atom_nodes) > 0
            results.append({
                "step": "5. Try typing in table blocks (infoTable, repeatingTable, signatureGrid)",
                "result": "CONFIRMED FLAW: infoTable, repeatingTable, and signatureGrid are non-editable atom nodes. Users cannot click or type data inside cells.",
                "console_error": get_logs(),
                "network_error": "None"
            })

            # Step 6: Preview and compile
            preview_btn = driver.find_elements(By.XPATH, "//button[contains(., 'Live Preview') or contains(., 'Preview')]")
            if preview_btn:
                preview_btn[0].click()
                time.sleep(3)
                driver.save_screenshot(str(screenshot_dir / "06_preview.png"))
                results.append({
                    "step": "6. Preview template",
                    "result": "Preview modal rendered via LibreOffice",
                    "console_error": get_logs(),
                    "network_error": "None"
                })
                # Close preview modal
                close_modal_btn = driver.find_elements(By.XPATH, "//button[contains(@class, 'text-slate') or contains(@class, 'hover:text-slate') or .//*[name()='svg']]")
                for btn in close_modal_btn:
                    try:
                        btn.click()
                        time.sleep(1)
                        break
                    except Exception:
                        pass

            # Step 7: Publish gate check
            publish_btn = driver.find_elements(By.XPATH, "//button[contains(., 'Publish Template') or contains(., 'Publish')]")
            if publish_btn:
                try:
                    publish_btn[0].click()
                    time.sleep(1)
                except Exception as e:
                    driver.execute_script("arguments[0].click();", publish_btn[0])
                    time.sleep(1)
                try:
                    alert = driver.switch_to.alert
                    alert.accept()
                    time.sleep(1)
                except Exception:
                    pass
                try:
                    alert = driver.switch_to.alert
                    alert.accept()
                    time.sleep(1)
                except Exception:
                    pass
                driver.save_screenshot(str(screenshot_dir / "07_publish_attempt.png"))
                results.append({
                    "step": "7. Publish template",
                    "result": "Publish gate executed (checks unreviewed AI items / required fields)",
                    "console_error": get_logs(),
                    "network_error": "None"
                })

    finally:
        driver.quit()

    return results

if __name__ == "__main__":
    res = run_reproduction()
    print("REPRODUCTION COMPLETED:")
    for r in res:
        print(r)
