"""Capture high-resolution screenshots for Phase W3.3 verification:
1. w3_3_number_reservation.png: Shows New Document form with Reference Number reservation button & reserved badge.
2. w3_3_event_diff_preview.png: Shows Event edit dialog with "venue: Old -> New, affects N documents" diff BEFORE saving.
3. w3_3_event_rerender_toast.png: Shows success toast with new version numbers for re-rendered documents.
"""

import os
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

SCREENSHOTS_DIR = Path("docs/screenshots/w3_3")
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def run_capture():
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

    driver = webdriver.Chrome(options=options)
    driver.set_window_size(1440, 960)
    wait = WebDriverWait(driver, 15)

    try:
        # 1. Login
        driver.get(base_url)
        email_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email']")))
        pwd_input = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
        email_input.send_keys("demo.owner@svnit.ac.in")
        pwd_input.send_keys("DemoOwnerPass123!")
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()

        # Wait for dashboard
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'ACM Student Chapter')]")))

        # 2. Click Permission Letter card
        perm_card = wait.until(
            EC.element_to_be_clickable(
                (By.XPATH, "//*[contains(text(), 'Permission Letter')]//ancestor::div[contains(@class, 'cursor-pointer')]")
            )
        )
        perm_card.click()

        # Wait for form
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Describe Your Event')]")))

        # Extract details to pre-fill
        desc_box = driver.find_element(By.TAG_NAME, "textarea")
        desc_box.send_keys(
            "We are organizing Smart India Hackathon 2026 Internal Hackathon on 15/10/2026 "
            "from 09:00 AM to 06:00 PM at Seminar Hall. Expected participants: 120 students."
        )
        driver.find_element(By.XPATH, "//button[contains(., 'Extract & Pre-fill Form')]").click()
        time.sleep(1.5)

        # Click Reserve Next Number
        reserve_btn = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Reserve Next Number')]"))
        )
        reserve_btn.click()
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Ref No. Reserved')]")))

        time.sleep(0.5)
        driver.save_screenshot(str(SCREENSHOTS_DIR / "w3_3_number_reservation.png"))
        print("Captured w3_3_number_reservation.png")

        # Accept drafts & generate document
        accept_btns = driver.find_elements(By.XPATH, "//button[contains(., 'Accept')]")
        for btn in accept_btns:
            driver.execute_script("arguments[0].click();", btn)
            time.sleep(0.2)

        gen_btn = driver.find_element(By.XPATH, "//button[contains(., 'Generate Document')]")
        driver.execute_script("arguments[0].scrollIntoView(true);", gen_btn)
        time.sleep(0.5)
        gen_btn.click()

        # Wait for review page
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Download PDF')]")))
        time.sleep(1.5)

        # 3. Navigate to Events Tab
        back_btn = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Back to Dashboard')]"))
        )
        back_btn.click()

        events_tab = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Events')]"))
        )
        events_tab.click()

        # Wait for events to load and find the Edit Event button
        edit_btn = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Edit Event')]"))
        )
        edit_btn.click()

        # In Edit modal, change venue to trigger diff preview
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Edit Event Context')]")))
        venue_inputs = driver.find_elements(By.XPATH, "//input[@type='text']")
        # venue is the 3rd input in the modal (0: title, 1: code, 2: venue)
        venue_input = venue_inputs[-1]
        venue_input.clear()
        venue_input.send_keys("Computer Center Lab 1")

        # Verify Diff Preview is visible before saving
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Propagation Diff Preview')]")))
        time.sleep(0.5)
        driver.save_screenshot(str(SCREENSHOTS_DIR / "w3_3_event_diff_preview.png"))
        print("Captured w3_3_event_diff_preview.png")

        # Save and verify Toast with document version number
        submit_btn = driver.find_element(By.XPATH, "//button[@type='submit' and contains(., 'Update')]")
        submit_btn.click()

        # Wait for toast
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Re-rendered')]")))
        time.sleep(0.5)
        driver.save_screenshot(str(SCREENSHOTS_DIR / "w3_3_event_rerender_toast.png"))
        print("Captured w3_3_event_rerender_toast.png")

    finally:
        driver.quit()
        server.should_exit = True


if __name__ == "__main__":
    run_capture()
