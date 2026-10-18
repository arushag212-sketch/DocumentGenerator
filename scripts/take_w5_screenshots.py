"""Script to capture Phase W5 screenshots:
1. 01_describe_box_gallery.png: "Describe your template" box on the gallery page with prompt and examples.
2. 02_ai_draft_editor.png: AI-generated draft template loaded into the editor with the AI banner and suggested fields.
"""

from __future__ import annotations

import json
import socket
import sys
import threading
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uvicorn
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

import os
TEMP_DB = Path("data/temp_screenshot_w5.db")
os.environ["DATABASE_URL"] = f"sqlite:///{TEMP_DB.as_posix()}"

from docgen.llm import StubLLMClient, set_llm_client
from server.app.core.rate_limit import clear_rate_limits
from server.app.main import app
from server.scripts.seed import seed
from tests.test_w5_ai_template import SAMPLE_SPONSORSHIP_SPEC


def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main():
    screenshots_dir = Path("docs/screenshots/w5")
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    print("Step 1: Seeding isolated temporary database...")
    if TEMP_DB.exists():
        try:
            TEMP_DB.unlink()
        except Exception as e:
            print(f"Warning: could not delete {TEMP_DB}: {e}")
    seed(clean=True)

    # Configure deterministic StubLLMClient
    set_llm_client(StubLLMClient(default_json=SAMPLE_SPONSORSHIP_SPEC))
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
    chrome_options.add_argument("--window-size=1600,1050")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")

    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 25)

    try:
        print("Step 2: Logging in as demo owner...")
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

        # Navigate to Templates Gallery tab
        print("Step 3: Navigating to Templates Gallery tab...")
        templates_nav = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Template Gallery')]")))
        templates_nav.click()
        time.sleep(2)

        # Locate the "Describe your template" box
        print("Step 4: Focusing Describe box...")
        textarea = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "textarea[placeholder*='sponsorship request letter']")))
        sample_prompt = (
            "A sponsorship request letter to a company with event name, date, venue, "
            "a tiers table with an amount per tier, and signatures for the coordinator and the faculty advisor"
        )
        textarea.clear()
        textarea.send_keys(sample_prompt)
        time.sleep(1)

        # Capture Screenshot 1: 01_describe_box_gallery.png
        screenshot_1 = screenshots_dir / "01_describe_box_gallery.png"
        driver.save_screenshot(str(screenshot_1))
        print(f"Captured: {screenshot_1}")

        # Click Generate Draft Template
        print("Step 5: Generating AI Draft...")
        gen_btn = driver.find_element(By.XPATH, "//button[contains(., 'Generate Draft Template')]")
        gen_btn.click()

        # Wait for Editor and AI banner
        print("Step 6: Waiting for Editor with AI Draft...")
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'AI-Suggested Template Draft')]")))
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Fields Panel')]")))
        time.sleep(3)

        # Capture Screenshot 2: 02_ai_draft_editor.png
        screenshot_2 = screenshots_dir / "02_ai_draft_editor.png"
        driver.save_screenshot(str(screenshot_2))
        print(f"Captured: {screenshot_2}")

    finally:
        driver.quit()
        print("Finished W5 screenshot generation.")


if __name__ == "__main__":
    main()
