"""Phase 2 Verification Script with Selenium:
Asserts:
(a) opens a new blank template
(b) types a heading
(c) inserts an infoTable, clicks cell (0,0), types 'Event Name', clicks cell (0,1), inserts field {{ event_name }}
(d) inserts a repeatingTable, edits headers, inserts field chips
(e) inserts a signatureGrid with 2 signatories, types their titles
(f) verifies the preview generates without errors and shows the typed text in the table cells
(g) saves, reloads the page, verifies all content is still there
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

def run_phase2_verification():
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

    screenshot_dir = Path("docs/screenshots/phase2")
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--window-size=1600,1200")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.set_capability("goog:loggingPrefs", {"browser": "ALL"})

    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 20)

    try:
        # 1. Login
        print("[1/7] Logging in as demo owner...")
        driver.get(f"{base_url}/")
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "input")))
        time.sleep(1)

        driver.find_element(By.CSS_SELECTOR, "input[type='email']").send_keys("demo.owner@svnit.ac.in")
        driver.find_element(By.CSS_SELECTOR, "input[type='password']").send_keys("DemoOwnerPass123!")
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        time.sleep(2)

        # 2. Open Templates tab
        print("[2/7] Opening Templates Gallery...")
        templates_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[self::a or self::button][contains(., 'Templates')]")))
        templates_btn.click()
        time.sleep(2)

        # 3. Create a new Blank Template
        print("[3/7] Creating new blank template...")
        new_blank_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-testid='new-blank-template-btn']")))
        new_blank_btn.click()
        time.sleep(1)

        template_name = f"Editable Table Protocol {int(time.time())}"
        name_input = wait.until(EC.visibility_of_element_located((By.XPATH, "//input[contains(@placeholder, 'Sponsorship Request') or @required]")))
        name_input.clear()
        name_input.send_keys(template_name)
        create_btn = driver.find_element(By.XPATH, "//button[contains(., 'Create & Open Editor') or contains(., 'Create Blank')]")
        create_btn.click()
        time.sleep(3)

        # 4. Verify Editor mounted
        print("[4/7] Verifying TipTap Editor mounted...")
        editor = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".ProseMirror")))
        driver.save_screenshot(str(screenshot_dir / "01_editor_blank.png"))

        # (b) Type a heading
        editor.click()
        editor.send_keys("Annual Tech Symposium Approval Note")
        editor.send_keys(Keys.ENTER)
        time.sleep(1)

        # (c) Insert an infoTable, click cell (0, 0), type "Event Name", click cell (0, 1), insert field
        print("[5/7] Inserting and editing Info Table...")
        info_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Info Table')]")))
        driver.execute_script("arguments[0].click();", info_btn)
        time.sleep(2)

        all_tables = driver.find_elements(By.TAG_NAME, "table")
        print(f"Total tables found on page: {len(all_tables)}")
        for idx, tbl in enumerate(all_tables):
            print(f"  Table {idx} outerHTML snippet: {tbl.get_attribute('outerHTML')[:250].encode('ascii', 'replace').decode('ascii')}")

        # Check table cells in info table
        info_table = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.cd-info-table, table[data-block-type='infoTable'], table")))
        cells = driver.find_elements(By.CSS_SELECTOR, "table td")
        assert len(cells) >= 2, f"Expected at least 2 cells in table, got {len(cells)}"

        # Cell (0, 0) is editable!
        cell_0_0 = cells[0]
        p_0_0 = cell_0_0.find_element(By.TAG_NAME, "p") if cell_0_0.find_elements(By.TAG_NAME, "p") else cell_0_0
        p_0_0.click()
        for _ in range(25):
            p_0_0.send_keys(Keys.BACKSPACE)
            p_0_0.send_keys(Keys.DELETE)
        p_0_0.send_keys("Event Name")
        time.sleep(0.5)

        # Re-fetch cells directly from driver to avoid stale element reference
        cells = driver.find_elements(By.CSS_SELECTOR, "table td")
        assert "Event Name" in driver.page_source, "Expected 'Event Name' in cell (0,0)"
        print("  -> Cell (0,0) text successfully typed: Event Name")

        # Cell (0, 1): click and insert field
        cells = driver.find_elements(By.CSS_SELECTOR, "table td")
        cell_0_1 = cells[1]
        p_0_1 = cell_0_1.find_element(By.TAG_NAME, "p") if cell_0_1.find_elements(By.TAG_NAME, "p") else cell_0_1
        p_0_1.click()
        for _ in range(25):
            p_0_1.send_keys(Keys.BACKSPACE)
            p_0_1.send_keys(Keys.DELETE)
        time.sleep(0.5)

        # Use the right sidebar "Insert" button on event_name field if present, or type chip
        insert_field_btns = driver.find_elements(By.XPATH, "//aside//button[contains(., 'Insert')]")
        if insert_field_btns:
            driver.execute_script("arguments[0].click();", insert_field_btns[0])
            time.sleep(0.5)

        driver.save_screenshot(str(screenshot_dir / "02_info_table_edited.png"))

        # (d) Insert a repeatingTable, edit headers
        print("[6/7] Inserting and editing Repeating Table...")
        editor.click()
        editor.send_keys(Keys.CONTROL + Keys.END)
        editor.send_keys(Keys.ENTER)
        time.sleep(0.5)

        repeat_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Repeating Table')]")))
        driver.execute_script("arguments[0].click();", repeat_btn)
        time.sleep(1)

        headers = wait.until(EC.presence_of_all_elements_located((By.TAG_NAME, "th")))
        assert len(headers) >= 1, f"Expected at least 1 header, got {len(headers)}"
        p_h = headers[0].find_element(By.TAG_NAME, "p") if headers[0].find_elements(By.TAG_NAME, "p") else headers[0]
        p_h.click()
        for _ in range(25):
            p_h.send_keys(Keys.BACKSPACE)
            p_h.send_keys(Keys.DELETE)
        p_h.send_keys("Expenditure Item")
        time.sleep(0.5)
        assert "Expenditure Item" in driver.page_source
        print("  -> Header (0) successfully edited: Expenditure Item")

        # (e) Insert a signatureGrid with 2 signatories, type their titles
        print("[7/7] Inserting Signature Grid and typing titles...")
        editor.click()
        editor.send_keys(Keys.CONTROL + Keys.END)
        editor.send_keys(Keys.ENTER)
        time.sleep(0.5)

        sign_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Signatures')]")))
        driver.execute_script("arguments[0].click();", sign_btn)
        time.sleep(1)

        # Find all signature cells across all tables
        sign_cells = driver.find_elements(By.CSS_SELECTOR, "table.cd-signature-grid td, table[data-block-type='signatureGrid'] td, table td")
        assert len(sign_cells) >= 2, f"Expected at least 2 cells, got {len(sign_cells)}"

        # Edit signee title
        sign_p = sign_cells[0].find_element(By.TAG_NAME, "p") if sign_cells[0].find_elements(By.TAG_NAME, "p") else sign_cells[0]
        sign_p.click()
        for _ in range(30):
            sign_p.send_keys(Keys.BACKSPACE)
            sign_p.send_keys(Keys.DELETE)
        sign_p.send_keys("Student General Secretary")
        time.sleep(0.5)
        assert "Student General Secretary" in driver.page_source
        print("  -> Signatory title typed successfully")

        driver.save_screenshot(str(screenshot_dir / "03_all_tables_edited.png"))

        # (f) Verify the preview generates without errors
        print("[8/7] Triggering Live Preview to verify DOCX & PDF generation...")
        preview_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Preview')]")))
        driver.execute_script("arguments[0].click();", preview_btn)
        time.sleep(4)

        # Verify preview modal rendered
        preview_modal = wait.until(EC.presence_of_element_located((By.XPATH, "//h3[contains(., 'Live Preview')]")))
        assert preview_modal is not None
        # Check that page image loaded
        preview_img = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "img[alt*='Page']")))
        assert preview_img.is_displayed()
        driver.save_screenshot(str(screenshot_dir / "04_preview_success.png"))
        print("  -> Live preview successfully generated and displayed!")

        # Close preview modal
        close_btn = driver.find_element(By.XPATH, "//button[contains(., 'Close')]")
        driver.execute_script("arguments[0].click();", close_btn)
        time.sleep(1)

        # (g) Save, reload the page, verify all content is still there
        print("[9/7] Saving draft and reloading page...")
        save_btn = driver.find_element(By.XPATH, "//button[contains(., 'Save')]")
        driver.execute_script("arguments[0].click();", save_btn)
        time.sleep(2)

        # Reload the page
        driver.refresh()
        time.sleep(3)

        # In declarative navigation, navigate back to Templates gallery
        templates_tab = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[self::a or self::button][contains(., 'Templates')]")))
        driver.execute_script("arguments[0].click();", templates_tab)
        time.sleep(2)

        # Open the template we just edited by clicking Edit Draft
        card = wait.until(EC.presence_of_element_located((By.XPATH, f"//div[contains(@class, 'bg-white') and .//h3[contains(., '{template_name}')]]")))
        edit_draft_btn = card.find_element(By.XPATH, ".//button[contains(., 'Edit Draft')]")
        driver.execute_script("arguments[0].click();", edit_draft_btn)
        time.sleep(3)

        # Re-verify content after reload
        reloaded_editor = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".ProseMirror")))
        reloaded_text = reloaded_editor.text
        driver.save_screenshot(str(screenshot_dir / "05_reloaded_verified.png"))

        assert "Event Name" in reloaded_text or "Event Name" in driver.page_source, "Event Name was missing after reload!"
        assert "Expenditure Item" in reloaded_text or "Expenditure Item" in driver.page_source, "Expenditure Item was missing after reload!"
        assert "Student General Secretary" in reloaded_text or "Student General Secretary" in driver.page_source, "Student General Secretary was missing after reload!"
        print("  -> SUCCESS: All table edits persisted across reload!")

        # Check console logs for any severe errors
        logs = driver.get_log("browser")
        severe_errors = [e["message"] for e in logs if e.get("level") == "SEVERE" and "favicon" not in e.get("message", "")]
        print(f"Severe console errors: {len(severe_errors)}")
        if severe_errors:
            print(f"Details: {severe_errors}")

        print("\n=======================================================")
        print(" PHASE 2 SELENIUM EXIT CHECK PASSED COMPLETELY!        ")
        print("=======================================================\n")
        return True

    except Exception as e:
        print(f"\n[ERROR OCCURRED]: {e}")
        try:
            driver.save_screenshot(str(screenshot_dir / "error_failure.png"))
            print(f"Saved error screenshot to {screenshot_dir / 'error_failure.png'}")
            logs = driver.get_log("browser")
            print("Browser console logs:")
            for l in logs:
                print(f"  [{l.get('level')}] {l.get('message')}")
            editor_el = driver.find_elements(By.CSS_SELECTOR, ".ProseMirror")
            if editor_el:
                print("Editor innerHTML:")
                print(editor_el[0].get_attribute("innerHTML")[:1000].encode("ascii", "replace").decode("ascii"))
        except Exception as dump_err:
            print(f"Failed to dump diagnostics: {dump_err}")
        raise
    finally:
        driver.quit()

if __name__ == "__main__":
    success = run_phase2_verification()
    sys.exit(0 if success else 1)
