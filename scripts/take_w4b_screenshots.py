"""Script to capture W4(b) screenshots:
1. 01_editor_all_blocks.png: TipTap editor showing toolbar, letterhead picker with locked SVNIT emblem,
   heading, formatted paragraph, field chips, info table, repeating table with computed total,
   page break, signature grid, and the right fields panel.
2. 02_editor_live_preview.png: Live preview modal with rendered dummy-data PDF pages.
"""

from __future__ import annotations

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
TEMP_DB = Path("data/temp_screenshot_w4b.db")
os.environ["DATABASE_URL"] = f"sqlite:///{TEMP_DB.as_posix()}"

from server.app.core.database import SessionLocal
from server.app.core.dummy_thumbnail import render_template_thumbnail
from server.app.main import app
from server.app.models import Template, TemplateVersion
from server.app.core.template_compiler import TemplateCompiler
from server.scripts.seed import seed


def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main():
    screenshots_dir = Path("docs/screenshots/w4b")
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    print("Step 1: Seeding isolated temporary database...")
    if TEMP_DB.exists():
        try:
            TEMP_DB.unlink()
        except Exception as e:
            print(f"Warning: could not delete {TEMP_DB}: {e}")
    seed(clean=True)

    # Create pre-built "Sponsorship Request Letter" draft in ACM club with all block types
    db = SessionLocal()
    acm_club_id = ""
    draft_template_id = ""
    try:
        from server.app.models import Club, User
        acm_club = db.query(Club).filter(Club.slug == "acm").first()
        acm_club_id = acm_club.id
        owner_user = db.query(User).filter(User.email == "demo.owner@svnit.ac.in").first()

        import uuid
        draft_template_id = str(uuid.uuid4())
        tmpl_slug = f"custom-sponsorship-{uuid.uuid4().hex[:6]}"

        editor_json = {
            "type": "doc",
            "content": [
                {"type": "heading", "attrs": {"level": 1, "textAlign": "center"}, "content": [{"type": "text", "text": "SPONSORSHIP & PARTNERSHIP PROPOSAL"}]},
                {"type": "paragraph", "content": [
                    {"type": "text", "text": "To,\nThe Executive Director & Corporate Relations Office,\nSVNIT Campus."}
                ]},
                {"type": "paragraph", "content": [
                    {"type": "text", "text": "Subject: Request for Official Sponsorship for "},
                    {"type": "fieldChip", "attrs": {"fieldName": "event_name", "label": "Event Name", "fieldType": "text"}},
                    {"type": "text", "text": " scheduled on "},
                    {"type": "fieldChip", "attrs": {"fieldName": "event_date", "label": "Event Date", "fieldType": "date"}},
                    {"type": "text", "text": " at "},
                    {"type": "fieldChip", "attrs": {"fieldName": "venue", "label": "Venue", "fieldType": "text"}},
                    {"type": "text", "text": "."}
                ]},
                {"type": "infoTable", "attrs": {
                    "title": "Event Overview",
                    "rows": [
                        {"label": "Organizing Club", "value": "ACM Student Chapter, SVNIT"},
                        {"label": "Flagship Event", "field": "event_name"},
                        {"label": "Proposed Date", "field": "event_date"},
                        {"label": "Confirmed Venue", "field": "venue"}
                    ]
                }},
                {"type": "paragraph", "content": [
                    {"type": "text", "text": "The sponsorship deliverables, tiers & contribution breakdown are summarized below:"}
                ]},
                {"type": "repeatingTable", "attrs": {
                    "listVariable": "sponsorship_tiers",
                    "itemAlias": "tier",
                    "columns": [
                        {"key": "tier_name", "label": "Tier & Deliverables", "align": "left"},
                        {"key": "slots_available", "label": "Slots Available", "align": "center", "type": "int"},
                        {"key": "amount", "label": "Contribution (INR)", "align": "right", "type": "money"}
                    ],
                    "hasTotal": True,
                    "totalLabel": "Total Expected Sponsorship",
                    "totalField": "amount",
                    "totalVarName": "total_sponsorship_amount"
                }},
                {"type": "pageBreak"},
                {"type": "paragraph", "content": [
                    {"type": "text", "text": "We look forward to an impactful collaboration. Official signatures and approval endorsements:"}
                ]},
                {"type": "signatureGrid", "attrs": {
                    "columns": 2,
                    "signatures": [
                        {"label": "Student Coordinator", "designation": "ACM Student Chapter"},
                        {"label": "Faculty Advisor", "designation": "Department of CSE, SVNIT"}
                    ]
                }}
            ]
        }

        fields = [
            {"key": "event_name", "label": "Event Name", "type": "text", "required": True, "ask": "What is the event name?"},
            {"key": "event_date", "label": "Event Date", "type": "date", "required": True, "ask": "What is the event date?"},
            {"key": "venue", "label": "Venue", "type": "text", "required": True, "ask": "What is the venue?"},
            {"key": "sponsorship_tiers", "label": "Sponsorship Tiers", "type": "table", "required": True, "columns": [
                {"key": "tier_name", "type": "text"},
                {"key": "slots_available", "type": "int"},
                {"key": "amount", "type": "money"}
            ]},
        ]

        docx_bytes, schema_yaml, report = TemplateCompiler.compile(
            editor_json=editor_json,
            fields=fields,
            template_meta={
                "id": draft_template_id,
                "name": "Sponsorship Request Letter",
                "category": "Official Event Documents",
                "numbering_series": "DOC",
            },
            club_slug=acm_club.slug,
        )

        storage_templates_dir = Path("storage/templates")
        storage_templates_dir.mkdir(parents=True, exist_ok=True)
        docx_dest = storage_templates_dir / f"{draft_template_id}_v1.docx"
        docx_dest.write_bytes(docx_bytes)

        tmpl = Template(
            id=draft_template_id,
            club_id=acm_club.id,
            slug=tmpl_slug,
            name="Sponsorship Request Letter",
            description="Official sponsorship proposal letter with tiered packages and computed total",
            category="Official Event Documents",
            stage="custom",
            is_system=False,
            status="draft",
        )
        db.add(tmpl)
        db.flush()

        ver = TemplateVersion(
            id=str(uuid.uuid4()),
            template_id=tmpl.id,
            version_no=1,
            editor_json=editor_json,
            schema_yaml=schema_yaml,
            docx_storage_key=str(docx_dest),
            validation_report=report,
            created_by=owner_user.id,
            change_note="Initial draft with all block types",
        )
        db.add(ver)
        db.flush()
        tmpl.current_version_id = ver.id
        db.commit()

        # Render dummy thumbnail
        render_template_thumbnail(db, tmpl, ver, "acm")
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
    chrome_options.add_argument("--window-size=1600,1050")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")

    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 25)

    try:
        from server.app.core.rate_limit import clear_rate_limits
        clear_rate_limits()

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

        # Click Edit Draft on Sponsorship Request Letter
        print("Step 4: Opening Template Editor for draft...")
        edit_draft_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Edit Draft')]")))
        edit_draft_btn.click()
        time.sleep(2)

        # Wait for Editor and toolbar to appear
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Fields Panel')]")))
        time.sleep(2)

        # Capture Screenshot 1: 01_editor_all_blocks.png
        screenshot_1 = screenshots_dir / "01_editor_all_blocks.png"
        driver.save_screenshot(str(screenshot_1))
        print(f"Captured: {screenshot_1}")

        # Click "Live Preview" button
        print("Step 5: Opening Live Preview modal...")
        preview_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Live Preview')]")))
        preview_btn.click()

        # Wait for preview modal to render
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Document Live Preview')]")))
        time.sleep(6)  # wait for LibreOffice render and base64 images

        # Capture Screenshot 2: 02_editor_live_preview.png
        screenshot_2 = screenshots_dir / "02_editor_live_preview.png"
        driver.save_screenshot(str(screenshot_2))
        print(f"Captured: {screenshot_2}")

    finally:
        driver.quit()
        print("Finished screenshot generation.")


if __name__ == "__main__":
    main()
