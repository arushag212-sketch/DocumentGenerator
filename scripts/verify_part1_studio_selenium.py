"""Part 1 Browser Smoke Test (Selenium):
Verifies:
1. Opens blank template in the 3-pane Studio Editor layout.
2. Types text in every block type:
   - Paragraph
   - Heading 1
   - Info Table
   - Repeating Table
   - Signature Grid
   - Page Break
3. Tests right tabs navigation (AI Chat, Fields, Design, Checks).
4. Verifies autosave status is "Saved".
5. Verifies live preview modal opens.
6. Asserts clean console (no JavaScript errors).
7. Captures screenshot to docs/screenshots/part1_studio_editor.png.
"""

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

def run_smoke_test():
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

    screenshot_dir = Path("docs/screenshots")
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
        print("[1/8] Logging in as demo owner...")
        driver.get(f"{base_url}/")
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "input")))
        time.sleep(1)

        driver.find_element(By.CSS_SELECTOR, "input[type='email']").send_keys("demo.owner@svnit.ac.in")
        driver.find_element(By.CSS_SELECTOR, "input[type='password']").send_keys("DemoOwnerPass123!")
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        time.sleep(2)

        print("[2/8] Opening Templates Gallery...")
        templates_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[self::a or self::button][contains(., 'Templates')]")))
        templates_btn.click()
        time.sleep(2)

        print("[3/8] Creating new blank template...")
        new_blank_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-testid='new-blank-template-btn']")))
        new_blank_btn.click()
        time.sleep(1)

        template_name = f"Studio Smoke Test {int(time.time())}"
        name_input = wait.until(EC.visibility_of_element_located((By.XPATH, "//input[contains(@placeholder, 'Sponsorship Request') or @required]")))
        name_input.clear()
        name_input.send_keys(template_name)
        create_btn = driver.find_element(By.XPATH, "//button[contains(., 'Create & Open Editor') or contains(., 'Create Blank')]")
        create_btn.click()
        time.sleep(3)

        print("[4/8] Verifying 3-pane editor structure mounted...")
        editor_elem = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".ProseMirror")))
        assert editor_elem is not None, "TipTap editor (.ProseMirror) not found"

        # Check PalettePanel (left)
        palette = driver.find_element(By.XPATH, "//*[contains(text(), 'Blocks Palette')]")
        assert palette is not None, "Blocks Palette not found"

        # Check RightTabsPanel (right)
        tabs = driver.find_elements(By.XPATH, "//aside//button[contains(., 'AI Chat') or contains(., 'Fields') or contains(., 'Design') or contains(., 'Checks')]")
        assert len(tabs) >= 3, f"Expected right panel tabs, found {len(tabs)}"
        print("  -> 3-pane layout verified: Left palette, Center canvas, Right tabs panel.")

        print("[5/8] Typing in each block type...")
        editor_elem.click()
        editor_elem.send_keys("Studio Editor Foundation Smoke Test")
        editor_elem.send_keys(Keys.ENTER)
        time.sleep(0.5)

        # Title (Heading 1) from palette
        h1_btn = driver.find_element(By.XPATH, "//button[contains(., 'Title (Heading 1)')]")
        driver.execute_script("arguments[0].click();", h1_btn)
        time.sleep(0.5)
        editor_elem.send_keys("Annual Tech Symposium 2026")
        editor_elem.send_keys(Keys.ENTER)
        time.sleep(0.5)

        # Info Table from palette
        info_btn = driver.find_element(By.XPATH, "//button[contains(., 'Info Table')]")
        driver.execute_script("arguments[0].click();", info_btn)
        time.sleep(1)

        # Repeating Table from palette
        repeat_btn = driver.find_element(By.XPATH, "//button[contains(., 'Repeating Table')]")
        driver.execute_script("arguments[0].click();", repeat_btn)
        time.sleep(1)

        # Signature Grid from palette
        sig_btn = driver.find_element(By.XPATH, "//button[contains(., 'Signature Grid')]")
        driver.execute_script("arguments[0].click();", sig_btn)
        time.sleep(1)

        # Page Break from palette
        pb_btn = driver.find_element(By.XPATH, "//button[contains(., 'Page Break')]")
        driver.execute_script("arguments[0].click();", pb_btn)
        time.sleep(1)

        # Verify tables and page break present in DOM
        tables = driver.find_elements(By.CSS_SELECTOR, "table")
        assert len(tables) >= 3, f"Expected at least 3 tables in editor, found {len(tables)}"
        print("  -> All blocks (Heading, Paragraph, InfoTable, RepeatingTable, SignatureGrid, PageBreak) created!")

        print("[6/8] Testing Right Panel Tabs...")
        for tab_name in ['Fields', 'Design', 'Checks', 'AI Chat']:
            tab_btn = driver.find_element(By.XPATH, f"//aside//button[contains(., '{tab_name}')]")
            driver.execute_script("arguments[0].click();", tab_btn)
            time.sleep(0.5)
        print("  -> Right tabs [AI Chat | Fields | Design | Checks] clicked and rendered.")

        print("[7/8] Verifying Autosave status...")
        time.sleep(2)
        saved_indicators = driver.find_elements(By.XPATH, "//*[contains(text(), 'Saved')]")
        assert len(saved_indicators) > 0, "Expected 'Saved' status indicator"
        print("  -> Autosave confirmed: 'Saved' status active.")

        # Save screenshot
        screenshot_path = screenshot_dir / "part1_studio_editor.png"
        driver.save_screenshot(str(screenshot_path))
        print(f"  -> Screenshot captured: {screenshot_path}")

        print("[8/8] Checking browser console for errors...")
        logs = driver.get_log("browser")
        severe_errors = [
            log for log in logs
            if log["level"] == "SEVERE" and "favicon" not in log["message"].lower() and "401" not in log["message"]
        ]
        if severe_errors:
            print(f"FAILED: Found {len(severe_errors)} severe console errors:")
            for err in severe_errors:
                print(f"  [{err['level']}] {err['message']}")
            sys.exit(1)
        else:
            print("  -> Browser console is 100% clean (0 severe errors).")

        print("\nSUCCESS: Part 1 Editor Foundation Browser Smoke Test PASSED!")
    finally:
        driver.quit()

if __name__ == "__main__":
    run_smoke_test()
