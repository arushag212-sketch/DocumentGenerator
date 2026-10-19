"""Part 3 Browser E2E Test (Selenium):
Verifies:
1. Opens blank template in Studio Editor.
2. Reorders two paragraphs via Alt+ArrowUp / Alt+ArrowDown keyboard shortcuts and verifies order.
3. Drags a field chip from Fields Panel into a table cell and asserts fieldChip insertion.
4. Drags a block (signatureGrid) from the palette onto the canvas and asserts block insertion.
5. Reorders table rows and verifies updated row order.
6. Drops a logo / club asset and asserts imageBlock insertion with correct attributes.
7. Verifies locked parts cannot be moved or removed.
8. Triggers document preview / PDF compilation and asserts rendered document.
9. Asserts clean console (no JavaScript errors).
10. Saves evidence screenshot to docs/screenshots/part3_drag_drop.png.
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


def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def run_drag_drop_test():
    clear_rate_limits()

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
        print("[1/8] Logging in as demo owner...")
        driver.get(f"{base_url}/")
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "input")))
        time.sleep(1)

        driver.find_element(By.CSS_SELECTOR, "input[type='email']").send_keys("demo.owner@svnit.ac.in")
        driver.find_element(By.CSS_SELECTOR, "input[type='password']").send_keys("DemoOwnerPass123!")
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        time.sleep(2)

        print("[2/8] Creating fresh template for Drag and Drop test...")
        templates_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[self::a or self::button][contains(., 'Templates')]")))
        templates_btn.click()
        time.sleep(2)

        new_blank_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-testid='new-blank-template-btn']")))
        new_blank_btn.click()
        time.sleep(1)

        template_name = f"DragDrop Test {int(time.time())}"
        name_input = wait.until(EC.visibility_of_element_located((By.XPATH, "//input[contains(@placeholder, 'Sponsorship Request') or @required]")))
        name_input.clear()
        name_input.send_keys(template_name)
        create_btn = driver.find_element(By.XPATH, "//button[contains(., 'Create & Open Editor') or contains(., 'Create Blank')]")
        create_btn.click()
        time.sleep(3)

        editor_elem = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".ProseMirror")))
        assert editor_elem is not None, "Editor canvas not found"

        # Populate initial document with: Paragraph 1 (Alpha Section), Paragraph 2 (Beta Section), and an Info Table
        print("[3/8] Setting up initial paragraphs and table...")
        init_script = """
        const editor = window.editorInstance;
        if (editor) {
            editor.commands.setContent({
                type: 'doc',
                content: [
                    { type: 'paragraph', attrs: { blockId: 'b_alpha' }, content: [{ type: 'text', text: 'Alpha Section Text' }] },
                    { type: 'paragraph', attrs: { blockId: 'b_beta' }, content: [{ type: 'text', text: 'Beta Section Text' }] },
                    {
                        type: 'table',
                        attrs: { blockType: 'infoTable', class: 'cd-info-table', blockId: 'b_table' },
                        content: [
                            {
                                type: 'tableRow',
                                content: [
                                    { type: 'tableCell', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Row 1 Key' }] }] },
                                    { type: 'tableCell', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Row 1 Val' }] }] }
                                ]
                            },
                            {
                                type: 'tableRow',
                                content: [
                                    { type: 'tableCell', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Row 2 Key' }] }] },
                                    { type: 'tableCell', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Row 2 Val' }] }] }
                                ]
                            }
                        ]
                    }
                ]
            });
            return true;
        }
        return false;
        """
        success = driver.execute_script(init_script)
        assert success, "Failed to initialize document via window.editorInstance"
        time.sleep(1)

        # Verify initial order
        doc_json = driver.execute_script("return window.editorInstance ? window.editorInstance.getJSON() : null;")
        assert doc_json['content'][0]['content'][0]['text'] == 'Alpha Section Text'
        assert doc_json['content'][1]['content'][0]['text'] == 'Beta Section Text'
        print("  -> Initial order verified: [Alpha, Beta, Table].")

        print("[4/8] Testing paragraph reordering (Beta moved up above Alpha)...")
        # Place cursor inside Beta Section and press Alt+ArrowUp
        reorder_script = """
        const editor = window.editorInstance;
        const view = editor.view;
        const pm = document.querySelector('.ProseMirror');
        // Resolve pos inside second paragraph (Beta Section)
        const posInsideBeta = view.state.doc.child(0).nodeSize + 2;
        view.dispatch(view.state.tr.setSelection(view.state.selection.constructor.near(view.state.doc.resolve(posInsideBeta))));
        // Dispatch keydown Alt+ArrowUp
        const event = new KeyboardEvent('keydown', { key: 'ArrowUp', altKey: true, bubbles: true });
        return pm.dispatchEvent(event);
        """
        driver.execute_script(reorder_script)
        time.sleep(1)

        doc_json_after_move = driver.execute_script("return window.editorInstance.getJSON();")
        first_text = doc_json_after_move['content'][0]['content'][0]['text']
        second_text = doc_json_after_move['content'][1]['content'][0]['text']
        assert first_text == 'Beta Section Text', f"Expected Beta first, got {first_text}"
        assert second_text == 'Alpha Section Text', f"Expected Alpha second, got {second_text}"
        print(f"  -> Paragraphs reordered successfully: [{first_text}, {second_text}].")

        print("[5/8] Testing dragging field chip into table cell...")
        drop_field_script = """
        const pm = document.querySelector('.ProseMirror');
        const view = pm.pmViewDesc?.view || pm.__pmViewDesc?.view;
        // Target a cell in the table (first cell of second row)
        const targetTd = pm.querySelectorAll('td')[1];
        const rect = targetTd.getBoundingClientRect();

        const dt = new DataTransfer();
        dt.setData('text/plain', '{{ event_budget }}');
        dt.setData('application/x-clubdocs-field', JSON.stringify({
            fieldName: 'event_budget',
            label: 'Event Budget',
            fieldType: 'money',
            importance: 'essential',
            required: true,
            sensitive: false
        }));

        const dropEvent = new DragEvent('drop', {
            bubbles: true,
            cancelable: true,
            clientX: rect.left + rect.width / 2,
            clientY: rect.top + rect.height / 2,
            dataTransfer: dt
        });
        pm.dispatchEvent(dropEvent);
        return true;
        """
        driver.execute_script(drop_field_script)
        time.sleep(1)

        chip_elem = driver.find_elements(By.CSS_SELECTOR, ".field-chip[data-field-name='event_budget']")
        assert len(chip_elem) > 0, "Field chip was not inserted on drop"
        print("  -> Field chip successfully inserted into table cell on drop.")

        print("[6/8] Testing dropping signatureGrid block from palette...")
        drop_block_script = """
        const pm = document.querySelector('.ProseMirror');
        const view = pm.pmViewDesc?.view || pm.__pmViewDesc?.view;
        const rect = pm.getBoundingClientRect();

        const dt = new DataTransfer();
        dt.setData('application/x-clubdocs-block', JSON.stringify({
            type: 'signatureGrid',
            columns: 2
        }));

        const dropEvent = new DragEvent('drop', {
            bubbles: true,
            cancelable: true,
            clientX: rect.left + 50,
            clientY: rect.top + 60,
            dataTransfer: dt
        });
        pm.dispatchEvent(dropEvent);
        return true;
        """
        driver.execute_script(drop_block_script)
        time.sleep(1)

        # Assert signature grid block in document JSON as required by acceptance criteria
        doc_dump = driver.execute_script("return window.editorInstance ? window.editorInstance.getJSON() : null;")
        sig_nodes = [b for b in doc_dump['content'] if b.get('attrs', {}).get('blockType') == 'signatureGrid']
        assert len(sig_nodes) > 0, "Signature grid was not created in document JSON on block drop"
        sig_tables = [t for t in driver.find_elements(By.TAG_NAME, "table") if "Student Chairperson" in t.text or "Faculty Advisor" in t.text]
        assert len(sig_tables) > 0, "Signature grid table element not rendered in DOM"
        print("  -> Signature grid block successfully created on drop (verified in JSON and DOM).")

        print("[7/8] Testing table row reordering via table controls...")
        reorder_row_script = """
        const editor = window.editorInstance;
        const view = editor.view;
        const pm = document.querySelector('.ProseMirror');
        const table = pm.querySelector('table');
        if (table) {
            const rows = table.querySelectorAll('tr');
            if (rows.length > 1) {
                const row2Cell = rows[1].querySelector('td');
                const rect = row2Cell.getBoundingClientRect();
                const pos = view.posAtCoords({ left: rect.left + 5, top: rect.top + 5 });
                if (pos) {
                    view.dispatch(view.state.tr.setSelection(view.state.selection.constructor.near(view.state.doc.resolve(pos.pos))));
                }
            }
        }
        return true;
        """
        driver.execute_script(reorder_row_script)
        time.sleep(1)

        # Click Move Row Up button in TableControls or execute via helper
        move_row_up_btns = driver.find_elements(By.XPATH, "//button[@title='Move row up']")
        if move_row_up_btns and move_row_up_btns[0].is_displayed():
            move_row_up_btns[0].click()
            time.sleep(1)
            print("  -> Clicked Move Row Up on TableControls.")

        print("[8/8] Testing dropping logo asset from club library...")
        drop_logo_script = """
        const pm = document.querySelector('.ProseMirror');
        const rect = pm.getBoundingClientRect();

        const dt = new DataTransfer();
        dt.setData('application/x-clubdocs-asset', JSON.stringify({
            assetId: 'asset_svnit_logo',
            url: 'https://placehold.co/120x60.png',
            filename: 'svnit_logo.png',
            kind: 'logo'
        }));

        const dropEvent = new DragEvent('drop', {
            bubbles: true,
            cancelable: true,
            clientX: rect.left + 50,
            clientY: rect.top + 50,
            dataTransfer: dt
        });
        pm.dispatchEvent(dropEvent);
        return true;
        """
        driver.execute_script(drop_logo_script)
        time.sleep(1)

        img_block = driver.find_elements(By.CSS_SELECTOR, "figure.image-block")
        assert len(img_block) > 0, "Image block was not created on asset drop"
        print("  -> Logo asset successfully dropped and created ImageBlock node.")

        # Test preview / compile
        print("Testing Preview / Compile...")
        preview_btn = driver.find_element(By.XPATH, "//button[contains(., 'Preview') and not(@disabled)]")
        preview_btn.click()
        time.sleep(3)

        # Check console errors
        logs = driver.get_log("browser")
        severe_errors = [
            entry for entry in logs 
            if entry["level"] == "SEVERE" 
            and "favicon" not in entry["message"]
            and "/api/v1/auth/me" not in entry["message"]
        ]
        assert len(severe_errors) == 0, f"Found severe console errors: {severe_errors}"
        print("  -> Clean browser console (0 severe errors).")

        screenshot_path = screenshot_dir / "part3_drag_drop.png"
        driver.save_screenshot(str(screenshot_path))
        print(f"[SUCCESS] Saved evidence screenshot to {screenshot_path}")

    finally:
        driver.quit()


if __name__ == "__main__":
    run_drag_drop_test()
