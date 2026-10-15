"""Capture UI screenshots for W3.1 evidence using headless Chrome."""

from __future__ import annotations

import socket
import threading
import time
from pathlib import Path

import uvicorn
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from server.app.main import app

SCREENSHOTS_DIR = Path("docs/screenshots/w3_1")
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def capture_screenshots():
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

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1440,960")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=options)
    driver.set_window_size(1440, 960)
    wait = WebDriverWait(driver, 20)

    try:
        # 1. Login
        driver.get(base_url)
        email_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email']")))
        pwd_input = driver.find_element(By.CSS_SELECTOR, "input[type='password']")

        email_input.clear()
        email_input.send_keys("demo.owner@svnit.ac.in")
        pwd_input.clear()
        pwd_input.send_keys("DemoOwnerPass123!")

        submit_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        submit_btn.click()

        # Wait for dashboard to load
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'ACM Student Chapter')]")))
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Your Role:')]")))
        time.sleep(1)

        # 2. Click Permission Letter card to open New Document form
        perm_card = wait.until(
            EC.element_to_be_clickable(
                (By.XPATH, "//*[contains(text(), 'Permission Letter')]//ancestor::div[contains(@class, 'cursor-pointer')]")
            )
        )
        perm_card.click()

        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Describe Your Event')]")))
        time.sleep(1)

        # Capture New Document with Missing Info Panel
        driver.save_screenshot(str(SCREENSHOTS_DIR / "ui_new_document_missing_panel.png"))
        print("Saved ui_new_document_missing_panel.png")

        # 3. Navigate to Events tab
        events_tab = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[normalize-space()='Events']")))
        events_tab.click()
        time.sleep(1)

        # Capture Events Tab
        driver.save_screenshot(str(SCREENSHOTS_DIR / "ui_events_tab.png"))
        print("Saved ui_events_tab.png")

    finally:
        driver.quit()
        server.should_exit = True


if __name__ == "__main__":
    capture_screenshots()
