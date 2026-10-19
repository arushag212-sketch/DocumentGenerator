"""Part 5 Browser E2E Stopwatch Verification (Selenium):
Verifies:
1. Starts stopwatch timer.
2. Logs in as demo owner.
3. Opens Template Gallery.
4. Opens Template Creation Wizard.
5. Submits prompt for a new official document.
6. Reviews & selects clarifying question chips.
7. Clicks 'Build My Template' to generate designed template.
8. Opens newly generated template in Studio Editor.
9. Triggers live Preview dry-run and asserts rendered page.
10. Stops timer: asserts entire workflow completes in < 3 minutes (< 180 seconds).
11. Asserts 0 severe console errors.
12. Saves screenshot evidence to docs/screenshots/part5_ai_everywhere.png.
"""

from __future__ import annotations

import sys
import time
import socket
import threading
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import uvicorn
from server.app.main import app
from server.app.core.rate_limit import clear_rate_limits


def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def run_ai_everywhere_stopwatch_test():
    clear_rate_limits()
    start_time = time.time()

    port = get_free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="info")
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
    wait = WebDriverWait(driver, 30)

    try:
        print("[1/6] Logging in as demo owner...")
        driver.get(f"{base_url}/")
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "input")))
        time.sleep(1)

        driver.find_element(By.CSS_SELECTOR, "input[type='email']").send_keys("demo.owner@svnit.ac.in")
        driver.find_element(By.CSS_SELECTOR, "input[type='password']").send_keys("DemoOwnerPass123!")
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        time.sleep(2)

        print("[2/6] Navigating to Template Gallery...")
        templates_btn = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//*[self::a or self::button][contains(., 'Templates')]"))
        )
        templates_btn.click()
        time.sleep(2)

        print("[3/6] Opening Template Wizard...")
        wizard_btn = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-testid='wizard-template-btn']"))
        )
        wizard_btn.click()
        time.sleep(1)

        # Step 1: Prompt input
        prompt_input = wait.until(EC.visibility_of_element_located((By.XPATH, "//textarea[@required]")))
        prompt_input.clear()
        prompt_input.send_keys("Permission letter for organizing AI & Robotics Hackathon in Computer Center")
        time.sleep(0.5)

        continue_btn = driver.find_element(By.XPATH, "//button[contains(., 'Continue to Customization')]")
        driver.execute_script("arguments[0].click();", continue_btn)
        time.sleep(2)

        print("[4/6] Answering clarifying question chips...")
        wait.until(EC.visibility_of_element_located((By.XPATH, "//h3[contains(., 'Template Creation Wizard')]")))
        # Click an option chip if present
        modal = driver.find_element(By.XPATH, "//div[contains(@class, 'fixed inset-0')]")
        option_chips = modal.find_elements(By.XPATH, ".//div[contains(@class, 'grid')]//button")
        if option_chips:
            driver.execute_script("arguments[0].click();", option_chips[0])
            time.sleep(0.5)

        build_btn = wait.until(
            EC.presence_of_element_located((By.XPATH, "//button[contains(., 'Build My Template')]"))
        )
        driver.execute_script("arguments[0].click();", build_btn)
        print("[5/6] Verifying editor opened with generated template...")
        for _ in range(30):
            if "/templates/" in driver.current_url:
                break
            time.sleep(1)
        print("Current URL:", driver.current_url)

        try:
            editor_elem = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.CLASS_NAME, "tiptap"))
            )
            print("  [OK] Editor canvas loaded")
        except Exception as e:
            driver.save_screenshot(str(screenshot_dir / "part5_ai_debug.png"))
            print("Page title:", driver.title)
            print("Current URL:", driver.current_url)
            print("Console logs:", driver.get_log("browser"))
            raise e

        time.sleep(2)

        # Assert document has content
        assert len(editor_elem.text) > 10, f"Expected editor text to be non-empty, got: {editor_elem.text}"

        print("[6/6] Verifying live preview generation...")
        preview_btn = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Preview')]"))
        )
        # Click via JS in case header intercepts
        driver.execute_script("arguments[0].click();", preview_btn)
        time.sleep(3)

        # Wait for preview modal
        wait.until(EC.visibility_of_element_located((By.XPATH, "//*[contains(text(), 'Template Live Preview')]")))
        time.sleep(3)

        try:
            alert = driver.switch_to.alert
            print(f"  [ALERT] Detected browser alert: {alert.text}")
            alert.accept()
            time.sleep(1)
        except Exception:
            pass

        # Screenshot capture
        screenshot_path = screenshot_dir / "part5_ai_everywhere.png"
        driver.save_screenshot(str(screenshot_path))
        print(f"[OK] Saved screenshot to {screenshot_path}")

        # Console inspection
        logs = driver.get_log("browser")
        severe_errors = [
            l for l in logs
            if l.get("level") == "SEVERE"
            and not any(ignored in l.get("message", "") for ignored in [
                "favicon.ico",
                "chrome-extension",
                "/api/v1/auth/me",
            ])
        ]
        print(f"Browser console errors (SEVERE, non-ignored): {len(severe_errors)}")
        for err in severe_errors:
            print(f"  Console SEVERE: {err.get('message')}")
        assert len(severe_errors) == 0, f"Found {len(severe_errors)} severe console errors!"

        elapsed_time = time.time() - start_time
        print(f"[OK] Total Stopwatch Time: {elapsed_time:.2f} seconds (< 180s limit)")
        assert elapsed_time < 180, f"Workflow took {elapsed_time:.2f}s, exceeding 180s limit!"

        print("[SUCCESS] Part 5 AI Everywhere Stopwatch E2E test passed!")

    finally:
        driver.quit()


if __name__ == "__main__":
    run_ai_everywhere_stopwatch_test()
