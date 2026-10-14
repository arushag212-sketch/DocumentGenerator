"""Capture automated browser screenshots of the Phase W2 web UI for gate verification."""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

SCREENSHOTS_DIR = Path("docs/screenshots/phase_w2")
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

def run():
    print("Starting background uvicorn server on port 8000...")
    env = os.environ.copy()
    server_proc = subprocess.Popen(
        ["python", "-m", "uvicorn", "server.app.main:app", "--port", "8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )

    try:
        # Wait for server to become responsive
        time.sleep(3)

        opts = Options()
        opts.add_argument("--headless=new")
        opts.add_argument("--window-size=1280,900")
        opts.add_argument("--disable-gpu")
        driver = webdriver.Chrome(options=opts)

        print("1. Navigating to root / (Sign In Shell with Permanent SVNIT Logo)...")
        driver.get("http://127.0.0.1:8000/")
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "top-shell-svnit-logo")))
        time.sleep(1)
        p1 = SCREENSHOTS_DIR / "w2_01_login_shell_svnit_logo.png"
        driver.save_screenshot(str(p1))
        print(f"  [OK] Saved screenshot: {p1}")

        print("2. Registering / logging in via web UI...")
        import random
        rand_id = random.randint(100, 999)
        test_email = f"ansh.gupta.{rand_id}@svnit.ac.in"
        club_slug = f"acm-chapter-{rand_id}"

        # Click Create Account tab
        tabs = driver.find_elements(By.CLASS_NAME, "auth-tab")
        if len(tabs) > 1:
            tabs[1].click()
            time.sleep(0.5)

        # Fill registration form
        driver.find_element(By.ID, "reg-name").send_keys("Ansh Gupta")
        driver.find_element(By.ID, "reg-email").send_keys(test_email)
        driver.find_element(By.ID, "reg-password").send_keys("ACMLeader2026!")
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        time.sleep(2)

        # Create club
        try:
            btn_create = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Create New Club') or contains(text(), '+ New Club')]"))
            )
            btn_create.click()
            time.sleep(0.5)
            driver.find_element(By.ID, "club-new-name").send_keys("ACM Student Chapter")
            driver.find_element(By.ID, "club-new-short").send_keys("ACM")
            driver.find_element(By.ID, "club-new-slug").send_keys(club_slug)
            driver.find_element(By.ID, "club-new-chapter").send_keys("6/52")
            driver.find_element(By.XPATH, "//button[contains(text(), 'Create Club') and @type='submit']").click()
            time.sleep(2)
        except Exception as e:
            print("Note on club creation:", e)

        print("3. Capturing Club Dashboard with Club Switcher and Permanent SVNIT Logo...")
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "club-switcher-select")))
        time.sleep(1)
        p2 = SCREENSHOTS_DIR / "w2_02_club_dashboard_switcher.png"
        driver.save_screenshot(str(p2))
        print(f"  [OK] Saved screenshot: {p2}")

        print("4. Adding member and capturing Members & Roles tab...")
        tabs = driver.find_elements(By.CLASS_NAME, "dash-tab")
        for tab in tabs:
            if "Members" in tab.text:
                tab.click()
                break
        time.sleep(1.5)

        # Add member Arshad Khatib
        try:
            add_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Add Member')]")
            # register target member in background first so they exist in DB
            import requests
            requests.post("http://127.0.0.1:8000/api/v1/auth/register", json={
                "name": "Arshad Khatib",
                "email": "arshad@svnit.ac.in",
                "password": "Password123!"
            })
            add_btn.click()
            time.sleep(0.5)
            driver.find_element(By.ID, "member-new-email").send_keys("arshad@svnit.ac.in")
            driver.find_element(By.XPATH, "//button[contains(text(), 'Add Member') and @type='submit']").click()
            time.sleep(1.5)
        except Exception as e:
            print("Note on member add:", e)

        p3 = SCREENSHOTS_DIR / "w2_03_members_and_roles_permissions.png"
        driver.save_screenshot(str(p3))
        print(f"  [OK] Saved screenshot: {p3}")

        print("5. Capturing Audit Trail tab...")
        tabs = driver.find_elements(By.CLASS_NAME, "dash-tab")
        for tab in tabs:
            if "Audit" in tab.text:
                tab.click()
                break
        time.sleep(1.5)
        p4 = SCREENSHOTS_DIR / "w2_04_club_security_audit_trail.png"
        driver.save_screenshot(str(p4))
        print(f"  [OK] Saved screenshot: {p4}")

        driver.quit()
        print("All Phase W2 screenshots successfully captured!")

    finally:
        server_proc.terminate()
        server_proc.wait()

if __name__ == "__main__":
    run()
