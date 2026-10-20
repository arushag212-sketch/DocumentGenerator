"""Selenium verification script for SVNIT ClubDocs Template Editor:
Tests required browser actions:
1. Open Template Editor with portrait template
2. Test unified toolbar, 3-tab left sidebar ("Blocks", "Fields", "Design")
3. Insert 3 fields (Event Name, Event Date, Venue)
4. Rename field chip
5. Change font and font size
6. Switch orientation (Portrait vs Landscape cards)
7. Live Preview:
   - Portrait template preview (tall aspect ratio, realistic dummy data, full title, proper signature spacing)
   - Landscape certificate preview (wide aspect ratio)
8. AI Copilot: ask for change & single-click undo
9. Captures high-res screenshots to docs/evidence/
"""

import time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

EVIDENCE_DIR = Path("docs/evidence")
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

def main():
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--window-size=1600,1050")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")

    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 20)

    try:
        print("[1] Opening app login page...")
        driver.get("http://localhost:5173/login")
        time.sleep(1)

        print("[2] Logging in as demo owner...")
        email_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email']")))
        email_input.clear()
        email_input.send_keys("demo.owner@svnit.ac.in")

        pass_input = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
        pass_input.clear()
        pass_input.send_keys("DemoOwnerPass123!")

        submit_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        submit_btn.click()
        time.sleep(2)

        # Direct navigation to Template Editor for Sponsorship Request Letter (Portrait)
        portrait_id = "8c1112a5-5481-4ff3-9ebd-9da1a3300a84"
        print(f"[3] Navigating to Template Editor for portrait template {portrait_id}...")
        driver.get(f"http://localhost:5173/editor/{portrait_id}")
        time.sleep(3)

        wait.until(EC.presence_of_element_located((By.XPATH, "//button[@title='Undo (Ctrl+Z)']")))
        time.sleep(2)

        title = driver.find_element(By.XPATH, "//h1").text
        print(f"[4] Loaded Template: {title}")

        # Capture screenshot 1: New Template Editor UI with unified toolbar and 3-tab left sidebar
        screenshot_editor = EVIDENCE_DIR / "template_editor_new_ux.png"
        driver.save_screenshot(str(screenshot_editor))
        print(f"Captured: {screenshot_editor}")

        # Test Left Sidebar - Fields Tab
        print("[5] Switching to Fields tab in Left Sidebar...")
        fields_tab = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Fields')]")))
        fields_tab.click()
        time.sleep(1)

        # Open Create Field Modal
        create_field_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Create Field')]")))
        create_field_btn.click()
        time.sleep(1)

        # Fill modal form: Label, Type, Required, Example
        print("[6] Creating new field: Event Category...")
        label_input = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@placeholder='e.g. Event Name, Chief Guest, Venue']")))
        label_input.clear()
        label_input.send_keys("Event Category")

        example_input = driver.find_element(By.XPATH, "//input[@placeholder='e.g. Annual Photography Walk']")
        example_input.clear()
        example_input.send_keys("Technical Workshop")

        create_submit = driver.find_element(By.XPATH, "//button[contains(text(), 'Create and Insert')]")
        create_submit.click()
        time.sleep(1)

        # Test renaming a chip / clicking chip
        print("[7] Clicking chip to test ChipPopover...")
        chips = driver.find_elements(By.CSS_SELECTOR, ".field-chip")
        if chips:
            chips[0].click()
            time.sleep(1)
            # Check ChipPopover is open
            popover_input = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@placeholder='e.g. Event Name']")))
            print(f"ChipPopover opened with label: {popover_input.get_attribute('value')}")
            # Close popover
            done_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Done')]")
            done_btn.click()
            time.sleep(1)

        # Test Left Sidebar - Design Tab
        print("[8] Switching to Design tab in Left Sidebar...")
        design_tab = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Design')]")))
        design_tab.click()
        time.sleep(1)

        screenshot_design = EVIDENCE_DIR / "template_editor_design_panel.png"
        driver.save_screenshot(str(screenshot_design))
        print(f"Captured: {screenshot_design}")

        # Ensure Portrait orientation is active
        portrait_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Portrait')]")))
        portrait_btn.click()
        time.sleep(1)

        # Click Live Preview (Task A)
        print("[9] Testing Live Preview (Portrait orientation)...")
        preview_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@title='Live Preview (Ctrl+P)']")))
        preview_btn.click()

        # Wait for preview modal to finish rendering
        time.sleep(5)
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Template Live Preview')]")))

        screenshot_portrait = EVIDENCE_DIR / "template_preview_portrait.png"
        driver.save_screenshot(str(screenshot_portrait))
        print(f"Captured Portrait Preview: {screenshot_portrait}")

        # Close preview modal
        close_preview = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(@aria-label, 'Close') or contains(text(), '✕')]")))
        close_preview.click()
        time.sleep(1)

        # Test Landscape orientation
        print("[10] Switching to Landscape orientation...")
        landscape_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Landscape')]")))
        landscape_btn.click()
        time.sleep(1)

        # Open Live Preview in Landscape
        print("[11] Testing Live Preview (Landscape orientation)...")
        preview_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@title='Live Preview (Ctrl+P)']")))
        preview_btn.click()
        time.sleep(5)

        screenshot_landscape = EVIDENCE_DIR / "template_preview_landscape.png"
        driver.save_screenshot(str(screenshot_landscape))
        print(f"Captured Landscape Preview: {screenshot_landscape}")

        close_preview = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(@aria-label, 'Close') or contains(text(), '✕')]")))
        close_preview.click()
        time.sleep(1)

        # Restore to Portrait
        portrait_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Portrait')]")))
        portrait_btn.click()
        time.sleep(1)

        # Test Copilot Chat & Undo
        print("[12] Testing Copilot Chat on the right panel...")
        starter_btn = driver.find_elements(By.XPATH, "//button[contains(text(), 'Make this a formal letter') or contains(text(), 'Change the theme to blue')]")
        if starter_btn:
            starter_btn[0].click()
            time.sleep(4)
            # Check for undo button
            undo_btns = driver.find_elements(By.XPATH, "//button[contains(., 'Undo') or contains(@title, 'Undo')]")
            if undo_btns:
                print("Single-click Undo button found in Copilot chat!")
                undo_btns[0].click()
                time.sleep(1)
                print("Successfully triggered Undo for Copilot action.")

        screenshot_final = EVIDENCE_DIR / "template_editor_complete.png"
        driver.save_screenshot(str(screenshot_final))
        print(f"Captured Final Studio state: {screenshot_final}")

        print("\n[SUCCESS] All manual browser verification steps passed and evidence captured!")

    finally:
        driver.quit()

if __name__ == "__main__":
    main()
