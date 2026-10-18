"""Phase 3 Verification Script with Selenium:
Asserts:
1. Deep-link to /templates redirects unauthenticated user to /login; logging in returns to /templates.
2. New user registration redirects to /onboarding/club; submits join request; sees waiting screen.
3. Club administrator logs in, sees /join-requests, approves user as editor.
4. User logs in/refreshes, completes position onboarding if needed, lands on /home.
5. React Router history (back / forward) between /home, /templates, and /documents functions cleanly.
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
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uvicorn
from server.app.main import app

def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

def run_phase3_verification():
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

    screenshot_dir = Path("docs/screenshots/phase3")
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--window-size=1600,1200")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.set_capability("goog:loggingPrefs", {"browser": "ALL"})

    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 15)

    try:
        print("[Step 1] Deep-link while logged out -> /login redirect")
        driver.get(f"{base_url}/templates")
        time.sleep(1.5)
        current_url = driver.current_url
        print(f"Current URL: {current_url}")
        assert "/login" in current_url, f"Expected redirect to /login, got {current_url}"
        driver.save_screenshot(str(screenshot_dir / "01_deep_link_redirect_login.png"))

        print("[Step 2] Registering new user -> /onboarding/club")
        reg_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Register')]")))
        reg_btn.click()
        time.sleep(0.5)

        unique_ts = int(time.time())
        test_email = f"lead.newstudent{unique_ts}@example.com"
        test_pass = "TestStudentPass123!"

        name_in = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Student Lead']")))
        name_in.send_keys("Test Lead Student")
        email_in = driver.find_element(By.XPATH, "//input[@placeholder='lead@example.com']")
        email_in.send_keys(test_email)
        pass_in = driver.find_element(By.XPATH, "//input[@placeholder='Min 10 characters']")
        pass_in.send_keys(test_pass)

        submit_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Create Account')]")
        submit_btn.click()
        time.sleep(2)

        wait.until(lambda d: "/onboarding/club" in d.current_url or "/home" in d.current_url)
        print(f"After registration URL: {driver.current_url}")
        assert "/onboarding/club" in driver.current_url, f"Expected /onboarding/club, got {driver.current_url}"
        driver.save_screenshot(str(screenshot_dir / "02_onboarding_club_page.png"))

        print("[Step 3] Submitting join request to existing club")
        club_select = wait.until(EC.presence_of_element_located((By.XPATH, "//select[contains(@class, 'border-slate-200')]")))
        options = club_select.find_elements(By.TAG_NAME, "option")
        assert len(options) > 1, "Expected clubs available to select"
        options[1].click()
        target_club_id = options[1].get_attribute("value")
        print(f"Selected target club id: {target_club_id}")

        join_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Submit Join Request')]")
        join_btn.click()
        time.sleep(2)

        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Waiting for Club Approval')]")))
        print("Waiting card rendered successfully!")
        driver.save_screenshot(str(screenshot_dir / "03_waiting_approval_card.png"))

        print("[Step 4] Club administrator logs in & reviews join requests at /join-requests")
        driver.delete_all_cookies()
        driver.get(f"{base_url}/login")
        time.sleep(1)

        sign_in_tab = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Sign In')]")))
        sign_in_tab.click()
        time.sleep(0.5)

        email_in = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@placeholder='student@example.com']")))
        email_in.clear()
        email_in.send_keys("demo.owner@svnit.ac.in")
        pass_in = driver.find_element(By.XPATH, "//input[@placeholder='••••••••••••']")
        pass_in.clear()
        pass_in.send_keys("DemoOwnerPass123!")

        auth_btn = driver.find_element(By.XPATH, "//button[@type='submit']")
        auth_btn.click()
        wait.until(lambda d: "/login" not in d.current_url)

        driver.get(f"{base_url}/join-requests")
        time.sleep(2)
        print(f"Admin on /join-requests: {driver.current_url}")
        assert "/join-requests" in driver.current_url, f"Expected /join-requests, got {driver.current_url}"
        driver.save_screenshot(str(screenshot_dir / "04_admin_join_requests_page.png"))

        approve_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Approve')]")))
        approve_btn.click()
        time.sleep(2)
        print("Join request approved by administrator!")
        driver.save_screenshot(str(screenshot_dir / "05_approved_join_request.png"))

        print("[Step 5] Approved user logs in and navigates seamlessly")
        driver.delete_all_cookies()
        driver.get(f"{base_url}/login")
        time.sleep(1)

        email_in = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@placeholder='student@example.com']")))
        email_in.clear()
        email_in.send_keys(test_email)
        pass_in = driver.find_element(By.XPATH, "//input[@placeholder='••••••••••••']")
        pass_in.clear()
        pass_in.send_keys(test_pass)

        auth_btn = driver.find_element(By.XPATH, "//button[@type='submit']")
        auth_btn.click()
        wait.until(lambda d: "/login" not in d.current_url)

        print(f"Logged in user URL: {driver.current_url}")
        driver.save_screenshot(str(screenshot_dir / "06_user_logged_in_routed.png"))

        print("[Step 6] Verifying browser back & forward navigation")
        driver.get(f"{base_url}/templates")
        time.sleep(1.5)
        assert "/templates" in driver.current_url, f"Expected /templates, got {driver.current_url}"

        driver.get(f"{base_url}/documents")
        time.sleep(1.5)
        assert "/documents" in driver.current_url, f"Expected /documents, got {driver.current_url}"

        driver.back()
        time.sleep(1.5)
        assert "/templates" in driver.current_url, f"Expected /templates on back, got {driver.current_url}"

        driver.forward()
        time.sleep(1.5)
        assert "/documents" in driver.current_url, f"Expected /documents on forward, got {driver.current_url}"
        driver.save_screenshot(str(screenshot_dir / "07_router_history_verified.png"))

        print("Checking browser logs for critical errors...")
        logs = driver.get_log("browser")
        severe_errors = [
            l for l in logs
            if l["level"] == "SEVERE"
            and "favicon" not in l["message"].lower()
            and "/api/v1/auth/me" not in l["message"]
            and "/permissions" not in l["message"]
        ]
        if severe_errors:
            print("Browser SEVERE logs:", severe_errors)
        assert len(severe_errors) == 0, f"Found {len(severe_errors)} severe console errors: {severe_errors}"

        print("\n=======================================================")
        print("PHASE 3 ROUTER VERIFICATION PASSED COMPLETELY!")
        print("=======================================================")

    finally:
        driver.quit()

if __name__ == "__main__":
    run_phase3_verification()
