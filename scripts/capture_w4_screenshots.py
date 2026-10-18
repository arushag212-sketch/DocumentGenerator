"""Script to capture W4 Part (a) screenshots:
1. Template Gallery listing system templates.
2. Forked template card showing independent club draft.
"""

from __future__ import annotations

import os
from pathlib import Path
import socket
import threading
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uvicorn
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

TEMP_DB = Path("data/temp_screenshot_w4_cap.db")
os.environ["DATABASE_URL"] = f"sqlite:///{TEMP_DB.as_posix()}"

from server.app.main import app
from server.scripts.seed import seed

SCREENSHOTS_DIR = Path("docs/screenshots/w4")
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def run():
    if TEMP_DB.exists():
        try:
            TEMP_DB.unlink()
        except Exception:
            pass
    seed(clean=True)

    port = get_free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    t = threading.Thread(target=server.run, daemon=True)
    t.start()

    base_url = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                break
        except OSError:
            time.sleep(0.1)

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1440,960")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=options)
    driver.set_window_size(1440, 960)
    wait = WebDriverWait(driver, 15)

    try:
        # 1. Login
        driver.get(base_url)
        email_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email']")))
        pwd_input = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
        email_input.clear()
        email_input.send_keys("demo.owner@svnit.ac.in")
        pwd_input.clear()
        pwd_input.send_keys("DemoOwnerPass123!")
        time.sleep(0.5)
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()

        # Wait for dashboard
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'ACM Student Chapter')]")))
        time.sleep(1)

        # 2. Click "Template Gallery" tab
        gallery_tab_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Template Gallery')]")))
        gallery_tab_btn.click()

        # Wait for template cards to render
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Official Event Documents')]")))
        time.sleep(1.5)

        # Capture 1: Template Gallery listing
        gallery_shot = SCREENSHOTS_DIR / "01_template_gallery.png"
        driver.save_screenshot(str(gallery_shot))
        print(f"Captured: {gallery_shot}")

        # 3. Click "Customize (fork)" on permission_letter
        fork_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-testid='fork-btn-permission_letter']")))
        driver.execute_script("arguments[0].scrollIntoView(true);", fork_btn)
        time.sleep(0.5)
        fork_btn.click()

        # Wait for success notification
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Successfully forked')]")))
        time.sleep(1)

        # Click "Custom Drafts" filter tab to showcase the newly created club custom draft
        custom_drafts_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Custom Drafts')]")))
        custom_drafts_btn.click()
        time.sleep(1.5)

        # Capture 2: Forked Template Card in gallery
        fork_shot = SCREENSHOTS_DIR / "02_forked_template.png"
        driver.save_screenshot(str(fork_shot))
        print(f"Captured: {fork_shot}")

    except Exception as e:
        print(f"Error during capture: {e}")
        driver.save_screenshot(str(SCREENSHOTS_DIR / "debug_error.png"))
        raise
    finally:
        driver.quit()
        server.should_exit = True


if __name__ == "__main__":
    run()
