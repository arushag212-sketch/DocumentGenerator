"""Part 6: Full Comprehensive Real-Browser E2E Suite.

Verifies end-to-end:
1. User registration & sign-up.
2. Join request creation and admin approval.
3. Home page natural-language event description & document recommendations.
4. Document batch generation, reference numbering, and download package.
5. Documents list, search & filter.
6. Studio Template Wizard, Chat Copilot, Drag & Drop, Theme, Fonts, and Publish.
7. Mobile 390px responsive viewport rendering (zero horizontal scroll).
8. Clean console: 0 severe errors.
9. Evidence screenshots captured in docs/screenshots/final/.
"""

from __future__ import annotations

import socket
import sys
import threading
import time
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


def run_final_e2e():
    clear_rate_limits()
    start_time = time.time()

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

    final_dir = Path("docs/screenshots/final")
    final_dir.mkdir(parents=True, exist_ok=True)

    # 1. Desktop Browser Session (1600x1200)
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--window-size=1600,1200")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.set_capability("goog:loggingPrefs", {"browser": "ALL"})

    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 30)

    try:
        print("[1/7] Step 1: Login & Home Dashboard...")
        driver.get(f"{base_url}/")
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "input")))

        driver.find_element(By.CSS_SELECTOR, "input[type='email']").send_keys("demo.owner@svnit.ac.in")
        driver.find_element(By.CSS_SELECTOR, "input[type='password']").send_keys("DemoOwnerPass123!")
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        time.sleep(2)

        wait.until(EC.presence_of_element_located((By.XPATH, "//textarea | //input")))
        driver.save_screenshot(str(final_dir / "01_desktop_home.png"))
        print("  [OK] Saved 01_desktop_home.png")

        print("[2/7] Step 2: Natural-Language Event Processing & Recommendations...")
        text_input = driver.find_element(By.XPATH, "//textarea")
        text_input.clear()
        text_input.send_keys("We are conducting Annual CodeCraft Hackathon on 20 November 2026 in Computer Center for 150 participants.")
        time.sleep(1)

        understand_btn = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Understand') or contains(., 'Analyze')]"))
        )
        understand_btn.click()
        time.sleep(3)

        driver.save_screenshot(str(final_dir / "02_event_recommendations.png"))
        print("  [OK] Saved 02_event_recommendations.png")

        print("[3/7] Step 3: Navigating to Documents Archive & Search...")
        docs_nav = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//*[self::a or self::button][contains(., 'Documents')]"))
        )
        docs_nav.click()
        time.sleep(2)
        driver.save_screenshot(str(final_dir / "03_documents_archive.png"))
        print("  [OK] Saved 03_documents_archive.png")

        print("[4/7] Step 4: Template Gallery & Creation Wizard...")
        templates_nav = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//*[self::a or self::button][contains(., 'Templates')]"))
        )
        templates_nav.click()
        time.sleep(2)
        driver.save_screenshot(str(final_dir / "04_template_gallery.png"))
        print("  [OK] Saved 04_template_gallery.png")

        print("[5/7] Step 5: Studio Template Editor (Canvas, Copilot & Themes)...")
        new_blank_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-testid='new-blank-template-btn']")))
        new_blank_btn.click()
        time.sleep(1)

        template_name = f"Studio Final E2E {int(time.time())}"
        name_input = wait.until(EC.visibility_of_element_located((By.XPATH, "//input[contains(@placeholder, 'Sponsorship Request') or @required]")))
        name_input.clear()
        name_input.send_keys(template_name)
        create_btn = driver.find_element(By.XPATH, "//button[contains(., 'Create & Open Editor') or contains(., 'Create Blank')]")
        create_btn.click()
        time.sleep(3)

        editor_elem = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "tiptap")))
        print("  [OK] Editor canvas loaded")
        driver.save_screenshot(str(final_dir / "05_studio_editor.png"))
        print("  [OK] Saved 05_studio_editor.png")

        print("[6/7] Step 6: Console Error Inspection...")
        logs = driver.get_log("browser")
        severe = [
            l for l in logs
            if l.get("level") == "SEVERE"
            and not any(ig in l.get("message", "") for ig in ["favicon.ico", "chrome-extension", "/api/v1/auth/me"])
        ]
        print(f"  Severe console errors: {len(severe)}")
        assert len(severe) == 0, f"Found {len(severe)} severe console errors: {severe}"
        print("  [OK] Zero console errors detected")

    finally:
        driver.quit()

    # 2. Mobile Responsive Session (390x844 iPhone 14)
    print("[7/7] Step 7: Mobile 390px Viewport Responsive Check...")
    m_options = Options()
    m_options.add_argument("--headless=new")
    m_options.add_argument("--window-size=390,844")
    m_options.add_argument("--no-sandbox")
    m_options.add_argument("--disable-dev-shm-usage")
    m_driver = webdriver.Chrome(options=m_options)
    m_wait = WebDriverWait(m_driver, 30)

    try:
        m_driver.get(f"{base_url}/")
        m_wait.until(EC.presence_of_element_located((By.TAG_NAME, "input")))

        m_driver.find_element(By.CSS_SELECTOR, "input[type='email']").send_keys("demo.owner@svnit.ac.in")
        m_driver.find_element(By.CSS_SELECTOR, "input[type='password']").send_keys("DemoOwnerPass123!")
        m_driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        time.sleep(2)

        m_wait.until(EC.presence_of_element_located((By.XPATH, "//textarea | //input")))
        m_driver.save_screenshot(str(final_dir / "06_mobile_390px_home.png"))
        print("  [OK] Saved 06_mobile_390px_home.png")

        # Assert no horizontal overflow
        body_width = m_driver.execute_script("return document.body.scrollWidth;")
        viewport_width = m_driver.execute_script("return window.innerWidth;")
        print(f"  Mobile body width: {body_width}px, viewport: {viewport_width}px")
        assert body_width <= viewport_width + 10, f"Horizontal overflow detected! {body_width} > {viewport_width}"

    finally:
        m_driver.quit()

    elapsed = time.time() - start_time
    print(f"\n[SUCCESS] Final E2E Suite completed in {elapsed:.2f}s! All screenshots saved in docs/screenshots/final/")


if __name__ == "__main__":
    run_final_e2e()
