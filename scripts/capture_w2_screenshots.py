"""Capture automated browser screenshots of Phase W2.5 React UI with dummy data for gate verification."""

from __future__ import annotations

import os
import sys
import subprocess
import time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from server.app.core.database import SessionLocal, engine, Base
from server.app.core.security import get_password_hash
from server.app.models import Club, Membership, User

SCREENSHOTS_DIR = Path("docs/screenshots/phase_w2")
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

def setup_demo_user():
    """Ensure a demo leader user exists with active membership in the demo club."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    club = db.query(Club).first()
    if not club:
        print("Warning: No club found to attach demo user to.")
        db.close()
        return

    email = "demo.lead@example.com"
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            email=email,
            name="Demo Student Head",
            password_hash=get_password_hash("DemoSecurePass123!"),
            is_platform_admin=True,
        )
        db.add(user)
        db.flush()
    else:
        user.password_hash = get_password_hash("DemoSecurePass123!")
        user.is_platform_admin = True
        user.failed_login_attempts = 0
        user.locked_until = None
        db.flush()

    membership = db.query(Membership).filter(Membership.user_id == user.id, Membership.club_id == club.id).first()
    if not membership:
        membership = Membership(
            user_id=user.id,
            club_id=club.id,
            role="owner",
            status="active",
        )
        db.add(membership)

    db.commit()
    db.close()
    print("Demo user configured with active club access.", flush=True)

def run():
    setup_demo_user()

    import threading
    import uvicorn
    from server.app.main import app

    port = 8008
    print(f"Starting in-process uvicorn server on port {port}...", flush=True)
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()

    driver = None
    try:
        # Wait for server to start
        time.sleep(2)

        print("Initializing headless Chrome WebDriver...", flush=True)
        opts = Options()
        opts.add_argument("--headless=new")
        opts.add_argument("--window-size=1280,900")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--no-sandbox")
        driver = webdriver.Chrome(options=opts)
        print("Headless Chrome WebDriver initialized successfully.", flush=True)

        # ---------------- 1. AUTH / SIGN IN SCREEN ----------------
        print("1. Navigating to root / (Sign In Shell with Permanent SVNIT Logo)...")
        driver.get(f"http://127.0.0.1:{port}/")
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//img[@alt='SVNIT Crest']")))
        time.sleep(1)
        p1 = SCREENSHOTS_DIR / "w2_01_login_shell_svnit_logo.png"
        driver.save_screenshot(str(p1))
        print(f"  [OK] Saved screenshot: {p1}")

        # ---------------- 2. LOG IN VIA WEB UI ----------------
        print("2. Logging in with dummy leader credentials...")
        email_input = driver.find_element(By.XPATH, "//input[@placeholder='student@example.com']")
        email_input.clear()
        email_input.send_keys("demo.lead@example.com")

        pass_input = driver.find_element(By.XPATH, "//input[@type='password']")
        pass_input.clear()
        pass_input.send_keys("DemoSecurePass123!")

        driver.find_element(By.XPATH, "//button[@type='submit']").click()
        time.sleep(2)

        # ---------------- 3. DASHBOARD WITH CLUB SWITCHER ----------------
        print("3. Capturing Club Dashboard with Switcher, Counters, and Permanent SVNIT Logo...")
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//button[@title='Sign Out']"))
        )
        time.sleep(1)
        p2 = SCREENSHOTS_DIR / "w2_02_club_dashboard_switcher.png"
        driver.save_screenshot(str(p2))
        print(f"  [OK] Saved screenshot: {p2}")

        # ---------------- 4. MEMBERS TAB & ROLES (Accurate Count) ----------------
        print("4. Capturing Members tab...")
        members_tab = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Members')]"))
        )
        members_tab.click()
        time.sleep(1.5)
        p3 = SCREENSHOTS_DIR / "w2_03_members_and_roles_permissions.png"
        driver.save_screenshot(str(p3))
        print(f"  [OK] Saved screenshot: {p3}")

        # ---------------- 5. FACULTY & CONTACTS (Field Encryption) ----------------
        print("5. Capturing Faculty & Office directory showing encrypted contact fields...")
        faculty_tab = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Faculty')]"))
        )
        faculty_tab.click()
        time.sleep(1.5)
        p5 = SCREENSHOTS_DIR / "w2_05_faculty_directory_field_encryption.png"
        driver.save_screenshot(str(p5))
        print(f"  [OK] Saved screenshot: {p5}")

        # ---------------- 6. SECURITY & AUDIT TRAIL TAB ----------------
        print("6. Capturing Security & Audit Trail tab...")
        audit_tab = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Audit')]"))
        )
        audit_tab.click()
        time.sleep(1.5)
        p4 = SCREENSHOTS_DIR / "w2_04_club_security_audit_trail.png"
        driver.save_screenshot(str(p4))
        print(f"  [OK] Saved screenshot: {p4}")

        print("All Phase W2.5 screenshots successfully captured with dummy data!")
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
        server.should_exit = True

if __name__ == "__main__":
    run()
