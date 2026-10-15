"""Generate evidence screenshots for Phase W3.2:

1. w3_2_amber_missing_ref_no.png: Missing-info panel with Amber status for unconfirmed reference number.
2. w3_2_standing_defaults_badge.png: Bill Certificate form showing 'from club settings' badge and NiL / Student Council standing defaults.
3. w3_2_event_diff_preview.png: Events tab showing dynamic UI diff preview ('venue: ... -> ..., affects N documents') and 'Update N documents' button.
4. w3_2_bill_certificate_page1.png: Rendered PDF page image of Bill Certificate showing 'for Rs. 944.00' matching Supplier Amount.
"""

from __future__ import annotations

import os
import shutil
import socket
import threading
import time
import uuid
from pathlib import Path

import pymupdf
import uvicorn
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from server.app.core.database import SessionLocal
from server.app.main import app
from server.app.models import Club, Document, Event, Template, User

SCREENSHOTS_DIR = Path("docs/screenshots/w3_2")


def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def ensure_demo_event():
    """Ensure at least one event with linked documents exists for the Events Tab preview."""
    db = SessionLocal()
    try:
        acm = db.query(Club).filter(Club.slug == "acm").first()
        owner = db.query(User).filter(User.email == "demo.owner@svnit.ac.in").first()
        tmpl = db.query(Template).filter(Template.slug == "permission_letter").first()
        if not acm or not owner or not tmpl:
            return

        ev = db.query(Event).filter(Event.club_id == acm.id, Event.title == "SIH Hackathon Cascade Demo").first()
        if not ev:
            ev = Event(
                id=str(uuid.uuid4()),
                club_id=acm.id,
                title="SIH Hackathon Cascade Demo",
                event_code="SIH",
                record={
                    "venue": "Old Seminar Hall",
                    "dates": "15/10/2026",
                    "time_start": "09:00 AM",
                    "time_end": "06:00 PM",
                },
                status="active",
                created_by=owner.id,
            )
            db.add(ev)
            db.commit()

            doc = Document(
                id=str(uuid.uuid4()),
                club_id=acm.id,
                template_id=tmpl.id,
                template_version_id=tmpl.current_version_id,
                event_id=ev.id,
                title="Permission Letter - SIH Hackathon",
                ref_no="ACM/2026-27/ROOM/099",
                status="generated",
                created_by=owner.id,
            )
            db.add(doc)
            db.commit()
    finally:
        db.close()


def main():
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    ensure_demo_event()

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
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1440,960")

    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 15)

    try:
        # 1. Login
        driver.get(base_url)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email']")))
        driver.find_element(By.CSS_SELECTOR, "input[type='email']").send_keys("demo.owner@svnit.ac.in")
        driver.find_element(By.CSS_SELECTOR, "input[type='password']").send_keys("DemoOwnerPass123!")
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'ACM Student Chapter')]")))
        time.sleep(1)

        # 2. Open Permission Letter to capture Amber Missing Ref No
        perm_card = wait.until(
            EC.element_to_be_clickable(
                (By.XPATH, "//*[contains(text(), 'Permission Letter')]//ancestor::div[contains(@class, 'cursor-pointer')]")
            )
        )
        perm_card.click()
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Required Field Status')]")))
        time.sleep(1)
        driver.save_screenshot(str(SCREENSHOTS_DIR / "w3_2_amber_missing_ref_no.png"))
        print("Captured w3_2_amber_missing_ref_no.png")

        # Cancel back to dashboard
        cancel_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Cancel')]")
        cancel_btn.click()
        time.sleep(0.5)

        # 3. Open Bill Certificate to capture 'from club settings' badge and defaults
        bc_card = wait.until(
            EC.element_to_be_clickable(
                (By.XPATH, "//*[contains(text(), 'Bill Certificate')]//ancestor::div[contains(@class, 'cursor-pointer')]")
            )
        )
        bc_card.click()
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'from club settings')]")))
        badge_el = driver.find_element(By.XPATH, "//*[contains(text(), 'from club settings')]")
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", badge_el)
        time.sleep(0.5)
        driver.save_screenshot(str(SCREENSHOTS_DIR / "w3_2_standing_defaults_badge.png"))
        print("Captured w3_2_standing_defaults_badge.png")

        # Cancel back to dashboard
        cancel_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Cancel')]")
        cancel_btn.click()
        time.sleep(0.5)

        # 4. Open Events Tab and trigger Diff Preview
        events_tab = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Events')]"))
        )
        events_tab.click()
        time.sleep(1)

        # Look for Edit Event button
        wait.until(EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'Edit Event')]")))
        edit_buttons = driver.find_elements(By.XPATH, "//button[contains(text(), 'Edit Event')]")
        if edit_buttons:
            edit_buttons[0].click()
            time.sleep(0.5)
            # Find venue input and change it
            venue_inputs = driver.find_elements(By.XPATH, "//input[@placeholder='e.g. Seminar Hall, CC Lab 1']")
            if venue_inputs:
                venue_inputs[0].clear()
                venue_inputs[0].send_keys("New Central Computing Facility")
                time.sleep(0.5)
            driver.save_screenshot(str(SCREENSHOTS_DIR / "w3_2_event_diff_preview.png"))
            print("Captured w3_2_event_diff_preview.png")

        # 5. Extract Bill Certificate Page 1 preview
        candidates = list(Path("outputs").glob("**/bill_certificate_v1.pdf"))
        if candidates:
            pdf_path = candidates[0]
            doc = pymupdf.open(str(pdf_path))
            pix = doc[0].get_pixmap(dpi=150)
            pix.save(str(SCREENSHOTS_DIR / "w3_2_bill_certificate_page1.png"))
            doc.close()
            print(f"Captured w3_2_bill_certificate_page1.png from {pdf_path}")

    finally:
        driver.quit()
        server.should_exit = True


if __name__ == "__main__":
    main()
