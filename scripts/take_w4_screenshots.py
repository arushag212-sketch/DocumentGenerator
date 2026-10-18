"""Script to take high-resolution screenshots for W4a.1:
1. 01_template_gallery.png on clean seed (6 system templates with rendered dummy-data thumbnails).
2. 02_forked_template.png showing forked custom draft with unique name and action buttons.
"""

import socket
import threading
import time
from pathlib import Path

import uvicorn
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

import os
TEMP_DB = Path("data/temp_screenshot_w4.db")
os.environ["DATABASE_URL"] = f"sqlite:///{TEMP_DB.as_posix()}"

from server.app.core.database import SessionLocal
from server.app.core.dummy_thumbnail import render_template_thumbnail
from server.app.main import app
from server.app.models import Template, TemplateVersion
from server.scripts.seed import seed


def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main():
    screenshots_dir = Path("docs/screenshots/w4")
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    (screenshots_dir / "debug_error.png").unlink(missing_ok=True)

    print("Step 1: Seeding isolated temporary database...")
    if TEMP_DB.exists():
        try:
            TEMP_DB.unlink()
        except Exception as e:
            print(f"Warning: could not delete {TEMP_DB}: {e}")
    seed(clean=True)

    print("Step 2: Pre-rendering thumbnails with dummy data for system templates...")
    db = SessionLocal()
    try:
        sys_tmpls = db.query(Template).filter(Template.is_system == True).all()
        for t in sys_tmpls:
            ver = db.query(TemplateVersion).filter(TemplateVersion.template_id == t.id).order_by(TemplateVersion.version_no.desc()).first()
            if ver:
                p = render_template_thumbnail(db, t, ver, "acm")
                print(f"  Pre-rendered {t.slug} -> {p}")
    finally:
        db.close()

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
    chrome_options.add_argument("--window-size=1440,960")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")

    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 25)

    try:
        from server.app.core.rate_limit import clear_rate_limits
        clear_rate_limits()

        print("Step 3: Logging in as demo owner...")
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

        print("Step 4: Navigating to Template Gallery...")
        gallery_tab = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Template Gallery')]")))
        gallery_tab.click()

        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Template Gallery')]")))
        # Wait for 6 template cards
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Permission Letter')]")))
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Approval Note')]")))
        time.sleep(2)

        # Retake screenshot 1 on clean DB (6 system templates)
        s1_path = screenshots_dir / "01_template_gallery.png"
        driver.save_screenshot(str(s1_path))
        print(f"Captured: {s1_path}")

        print("Step 5: Forking Permission Letter...")
        fork_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@data-testid='fork-btn-permission_letter']")))
        fork_btn.click()

        # Modal opens
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Customize Template (Fork)')]")))
        time.sleep(0.5)

        submit_fork_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Create Club Fork')]")))
        submit_fork_btn.click()

        # Wait for success message
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Successfully forked')]")))
        time.sleep(1)

        print("Step 6: Filtering to Custom Drafts...")
        custom_filter_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Custom Drafts')]")))
        custom_filter_btn.click()
        time.sleep(1.5)

        # Retake screenshot 2 showing forked custom draft
        s2_path = screenshots_dir / "02_forked_template.png"
        driver.save_screenshot(str(s2_path))
        print(f"Captured: {s2_path}")

    finally:
        driver.quit()
        server.should_exit = True
        print("Screenshots completed successfully.")


if __name__ == "__main__":
    main()
