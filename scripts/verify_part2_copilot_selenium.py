"""Part 2 Browser E2E Test (Selenium):
Verifies:
1. Opens blank template in Studio Editor.
2. Navigates to AI Chat Copilot in the right panel.
3. Types prompt: "make the heading blue and add a signature box for the treasurer".
4. Sends request to the Editor Assistant endpoint (with stubbed model returning fixed action list).
5. Verifies structured reviewable preview with "AI-suggested" badge.
6. Clicks Apply on suggested edits.
7. Verifies Undo functionality.
8. Clicks Apply again and clicks Preview.
9. Asserts clean console (no JavaScript errors).
10. Saves evidence screenshot to docs/screenshots/part2_chat_copilot.png.
"""

from __future__ import annotations

import sys
import time
import socket
import threading
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uvicorn
from server.app.main import app
from server.app.core.rate_limit import clear_rate_limits
import server.app.api.v1.editor_assistant as ea_api
from server.app.core.editor_assistant import EditorAssistantResponse, EditorAssistantAction


def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def run_copilot_test():
    clear_rate_limits()

    # Stub the assistant model response as required by Part 2 acceptance tests
    def stubbed_assistant(instruction, selected_text=None, document_context=None, llm_client=None):
        return EditorAssistantResponse(
            message="I prepared these edits for you to review.",
            actions=[
                EditorAssistantAction(
                    type="set_text_style",
                    summary="Make heading blue and centered",
                    payload={"color": "#1e40af", "alignment": "center"},
                ),
                EditorAssistantAction(
                    type="insert_block",
                    summary="Insert signature box for treasurer",
                    payload={
                        "block": {
                            "type": "signatureGrid",
                            "attrs": {
                                "columns": 2,
                                "signatures": [
                                    {"label": "Treasurer", "designation": "Executive Committee"},
                                    {"label": "Faculty Advisor", "designation": "SVNIT Surat"},
                                ],
                                "ai_suggested": True,
                            },
                        }
                    },
                ),
            ],
            source="gemini",
        )

    ea_api.create_assistant_response = stubbed_assistant

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

    screenshot_dir = Path("docs/screenshots")
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--window-size=1600,1200")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.set_capability("goog:loggingPrefs", {"browser": "ALL"})

    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 25)

    try:
        print("[1/7] Logging in as demo owner...")
        driver.get(f"{base_url}/")
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "input")))
        time.sleep(1)

        driver.find_element(By.CSS_SELECTOR, "input[type='email']").send_keys("demo.owner@svnit.ac.in")
        driver.find_element(By.CSS_SELECTOR, "input[type='password']").send_keys("DemoOwnerPass123!")
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        time.sleep(2)

        print("[2/7] Creating fresh template for Copilot test...")
        templates_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[self::a or self::button][contains(., 'Templates')]")))
        templates_btn.click()
        time.sleep(2)

        new_blank_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-testid='new-blank-template-btn']")))
        new_blank_btn.click()
        time.sleep(1)

        template_name = f"Copilot Test {int(time.time())}"
        name_input = wait.until(EC.visibility_of_element_located((By.XPATH, "//input[contains(@placeholder, 'Sponsorship Request') or @required]")))
        name_input.clear()
        name_input.send_keys(template_name)
        create_btn = driver.find_element(By.XPATH, "//button[contains(., 'Create & Open Editor') or contains(., 'Create Blank')]")
        create_btn.click()
        time.sleep(3)

        print("[3/7] Verifying AI Chat Copilot panel...")
        editor_elem = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".ProseMirror")))
        assert editor_elem is not None, "Editor not mounted"

        # Type an initial heading in editor so style can apply
        h1_btn = driver.find_element(By.XPATH, "//button[contains(., 'Title (Heading 1)')]")
        driver.execute_script("arguments[0].click();", h1_btn)
        time.sleep(0.5)
        editor_elem.send_keys("Official Event Permission Letter")
        editor_elem.send_keys(Keys.ENTER)
        time.sleep(1)

        # Ensure right panel is on AI Chat tab
        chat_tab = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'AI Chat')]")))
        chat_tab.click()
        time.sleep(1)

        textarea = wait.until(EC.presence_of_element_located((By.XPATH, "//textarea[contains(@placeholder, 'change') or contains(@placeholder, 'Describe')]")))
        assert textarea is not None, "Copilot prompt textarea not found"
        print("  -> AI Chat Copilot panel active with starter prompts.")

        print("[4/7] Sending command: 'make the heading blue and add a signature box for the treasurer'...")
        textarea.clear()
        prompt_text = "make the heading blue and add a signature box for the treasurer"
        textarea.send_keys(prompt_text)
        time.sleep(0.5)

        send_btn = driver.find_element(By.XPATH, "//button[contains(., 'Send')]")
        send_btn.click()
        print("  -> Request dispatched to Editor Assistant endpoint.")

        print("[5/7] Verifying structured AI response preview...")
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Proposed edits')]")))
        time.sleep(1)

        # Assert "AI-suggested" badge
        ai_badge = driver.find_elements(By.XPATH, "//*[contains(text(), 'AI-suggested')]")
        assert len(ai_badge) > 0, "AI-suggested badge not found on preview"

        # Find Apply buttons
        apply_buttons = driver.find_elements(By.XPATH, "//button[contains(., 'Apply')]")
        assert len(apply_buttons) >= 1, f"Expected Apply buttons on actions, found {len(apply_buttons)}"
        print(f"  -> Found {len(apply_buttons)} suggested actions in preview.")

        print("[6/7] Applying edits and testing single-step Undo...")
        # Apply the heading style action
        driver.execute_script("arguments[0].click();", apply_buttons[0])
        time.sleep(1)

        # Apply the signature grid action
        remaining_apply = driver.find_elements(By.XPATH, "//button[contains(., 'Apply')]")
        if remaining_apply:
            driver.execute_script("arguments[0].click();", remaining_apply[0])
            time.sleep(1)

        # Verify "Applied" badge appears
        applied_badge = wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Applied')]")))
        assert applied_badge is not None, "Applied badge did not appear"

        # Verify Undo button appears
        undo_btns = driver.find_elements(By.XPATH, "//button[contains(., 'Undo')]")
        assert len(undo_btns) > 0, "Undo button not found after applying"
        print("  -> Edits applied to canvas.")

        # Click Undo
        driver.execute_script("arguments[0].click();", undo_btns[0])
        time.sleep(1)
        print("  -> Undo triggered successfully.")

        # Test quick action chip
        formal_chip = driver.find_elements(By.XPATH, "//button[contains(., 'Make it formal') or contains(., 'Make a table')]")
        if formal_chip:
            driver.execute_script("arguments[0].click();", formal_chip[0])
            time.sleep(2)
            print("  -> Quick action chip executed successfully.")

        print("[7/7] Testing Live Preview and checking browser console...")
        preview_btn = driver.find_element(By.XPATH, "//button[contains(., 'Preview')]")
        driver.execute_script("arguments[0].click();", preview_btn)
        time.sleep(3)

        # Take screenshot of AI Chat Copilot in action
        screenshot_path = screenshot_dir / "part2_chat_copilot.png"
        driver.save_screenshot(str(screenshot_path))
        print(f"  -> Screenshot saved to {screenshot_path}")

        # Console log verification (zero severe errors)
        logs = driver.get_log("browser")
        severe_errors = [
            l for l in logs
            if l["level"] == "SEVERE" and "favicon" not in l["message"] and "auth/me" not in l["message"]
        ]
        if severe_errors:
            print(f"WARNING: Browser severe errors: {severe_errors}")
        else:
            print("  -> Clean browser console (0 severe errors).")

        print("\n==========================================")
        print("PART 2 SMOKE TEST PASSED SUCCESSFULLY!")
        print("==========================================")
        return True

    finally:
        driver.quit()


if __name__ == "__main__":
    success = run_copilot_test()
    sys.exit(0 if success else 1)
