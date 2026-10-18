"""Phase W7 Frontend Onboarding, Simplified Home, and Document Result E2E Tests.

Tests:
1. New user registration -> "Which club are you in?" -> join request with position -> shows "Waiting for approval from <admin>".
2. Admin approves request -> user now has active access.
3. Home page "What do you need?" -> understood chips, native pickers, reference number accepted, generates batch -> Result page renders with PDF preview and download buttons -> "Edit details" returns to Home.
4. Mobile layout test at 390px width asserting no horizontal scroll and all buttons reachable.
All screenshots saved to docs/screenshots/w7/.
"""

from __future__ import annotations

import io
import os
from pathlib import Path
import socket
import threading
import time
import pytest

pytestmark = pytest.mark.skip(
    reason="Legacy browser test for pre-Phase 3 tab UI; verified by scripts/verify_phase2_editor_selenium.py and scripts/verify_phase4_home_selenium.py"
)
from fastapi.testclient import TestClient
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from server.app.core.rate_limit import clear_rate_limits
from server.app.main import app
from server.app.models import Club, JoinRequest, User


def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def e2e_server():
    """Start an ephemeral background uvicorn server for the browser test."""
    clear_rate_limits()
    port = get_free_port()
    import uvicorn
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{port}"
    for _ in range(60):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                break
        except OSError:
            time.sleep(0.1)

    yield base_url


@pytest.fixture(scope="module")
def browser():
    """Headless Chrome browser with desktop viewport."""
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--window-size=1600,1100")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--hide-scrollbars")

    driver = webdriver.Chrome(options=chrome_options)
    driver.set_window_size(1600, 1100)
    yield driver
    driver.quit()


@pytest.fixture(scope="module")
def screenshots_dir() -> Path:
    p = Path("docs/screenshots/w7")
    p.mkdir(parents=True, exist_ok=True)
    return p


class SharedContext:
    user_email: str = ""
    user_password: str = "SecureStudentPass123!"
    club_id: str = ""
    join_request_id: str = ""


context = SharedContext()


def test_w7_01_new_user_onboarding_and_pending_approval(e2e_server, browser, screenshots_dir, db_session):
    """Test 1: New user registers -> 'Which club are you in?' -> join request -> 'Waiting for approval'."""
    driver = browser
    wait = WebDriverWait(driver, 25)
    base_url = e2e_server

    driver.get(base_url)
    time.sleep(1.5)

    # Click Register tab
    register_tab = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Register')]")))
    register_tab.click()
    time.sleep(0.5)

    unique_email = f"student.applicant.{int(time.time())}@svnit.ac.in"
    context.user_email = unique_email

    # Fill registration fields
    name_input = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Student Lead']")))
    name_input.clear()
    name_input.send_keys("Priya Sharma")

    email_input = driver.find_element(By.XPATH, "//input[@placeholder='lead@example.com']")
    email_input.clear()
    email_input.send_keys(unique_email)

    pass_input = driver.find_element(By.XPATH, "//input[@placeholder='Min 10 characters']")
    pass_input.clear()
    pass_input.send_keys(context.user_password)

    driver.save_screenshot(str(screenshots_dir / "01_register_form.png"))

    reg_btn = driver.find_element(By.XPATH, "//button[contains(., 'Create Account')]")
    reg_btn.click()

    # Step: User lands on onboarding page: "Which club are you in?"
    wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Which club are you in?')]")))
    driver.save_screenshot(str(screenshots_dir / "02_which_club_are_you_in.png"))

    # Open the club finder modal if not already open
    find_club_btns = driver.find_elements(By.XPATH, "//button[contains(., 'Find or Add Club') or contains(., 'Choose Club')]")
    if find_club_btns:
        find_club_btns[0].click()
        time.sleep(1)

    # In ClubSelectionModal, search for ACM
    search_input = wait.until(EC.presence_of_element_located((By.XPATH, "//input[contains(@placeholder, 'Search by club name')]")))
    search_input.clear()
    search_input.send_keys("ACM")
    time.sleep(1)

    driver.save_screenshot(str(screenshots_dir / "03_search_club_acm.png"))

    # Click "Join Club" on ACM Student Chapter
    join_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Join Club')]")))
    join_btn.click()
    time.sleep(0.5)

    # Position Selector Modal: choose "Member"
    wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), \"What's your position?\")]")))
    driver.save_screenshot(str(screenshots_dir / "04_select_position_modal.png"))

    # Submit request
    submit_join_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Submit Join Request')]")))
    submit_join_btn.click()
    time.sleep(1.5)

    # Verify user sees: "Waiting for approval"
    wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Waiting for approval')]")))
    driver.save_screenshot(str(screenshots_dir / "05_waiting_for_approval_screen.png"))

    page_text = driver.page_source
    assert "Waiting for approval" in page_text
    assert "Private club documents and drafting actions will be unlocked once approved." in page_text


def test_w7_02_admin_approves_request_unlocks_access(e2e_server, browser, screenshots_dir, db_session):
    """Test 2: Admin approves the pending join request -> user now has full access to Home."""
    driver = browser
    wait = WebDriverWait(driver, 25)

    # 1. Admin approves via API
    client = TestClient(app)
    admin_login = client.post(
        "/api/v1/auth/login",
        json={"email": "demo.owner@svnit.ac.in", "password": "DemoOwnerPass123!"},
    )
    assert admin_login.status_code == 200
    token = admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {token}"}

    # Find ACM club id
    clubs = client.get("/api/v1/clubs/", headers=admin_headers).json()
    acm = next(c for c in clubs if c["short_name"] == "ACM")
    club_id = acm["id"]
    context.club_id = str(club_id)

    # Find pending join request for user
    jrs = client.get(f"/api/v1/clubs/{club_id}/join-requests", headers=admin_headers).json()
    my_jr = next(jr for jr in jrs if jr["user_email"] == context.user_email and jr["status"] == "pending")
    context.join_request_id = my_jr["id"]

    # Approve the join request with role 'editor'
    approve_res = client.post(
        f"/api/v1/clubs/{club_id}/join-requests/{my_jr['id']}/approve",
        json={"role": "editor", "is_signatory": False},
        headers=admin_headers,
    )
    assert approve_res.status_code == 200

    # 2. In browser, refresh the page to reload memberships
    driver.refresh()
    time.sleep(2)

    # User now lands on simplified Home interface: "What do you need?"
    wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'What do you need?')]")))
    driver.save_screenshot(str(screenshots_dir / "06_approved_home_unlocked.png"))

    page_text = driver.page_source
    assert "What do you need?" in page_text
    assert "Permission letter for an event" in page_text
    # Verify no engineering jargon
    assert "reservation" not in page_text.lower()
    assert "series" not in page_text.lower()
    assert "canonical" not in page_text.lower()


def test_w7_03_home_understand_and_generate_flow(e2e_server, browser, screenshots_dir, db_session):
    """Test 3: Home text prompt -> understand -> widgets -> reference number accept -> generate -> ResultPage."""
    driver = browser
    wait = WebDriverWait(driver, 30)

    # Input workshop prompt
    textarea = wait.until(EC.presence_of_element_located((By.XPATH, "//textarea[@placeholder[contains(., 'We are conducting')]]")))
    textarea.clear()
    workshop_prompt = "We are conducting a two-day Web Development Workshop on 14-15 October in Seminar Hall for around 120 students."
    textarea.send_keys(workshop_prompt)

    understand_btn = wait.until(EC.presence_of_element_located((By.XPATH, "//button[contains(., 'Understand & Recommend')]")))
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'}); arguments[0].click();", understand_btn)

    # Wait for "What we understood"
    try:
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'What we understood')]")))
    except Exception as exc:
        driver.save_screenshot(str(screenshots_dir / "debug_understand_failure.png"))
        errors = driver.find_elements(By.XPATH, "//div[contains(@class, 'bg-red-50')]")
        err_text = [e.text for e in errors]
        print(f"\n[DEBUG UNDERSTAND ERROR ON SCREEN]: {err_text}\nURL: {driver.current_url}")
        raise exc
    time.sleep(1)
    driver.save_screenshot(str(screenshots_dir / "07_what_we_understood.png"))

    # Verify understood fields
    title_input = driver.find_element(By.XPATH, "//input[@placeholder='e.g. Web Development Workshop']")
    assert "Web Development Workshop" in title_input.get_attribute("value")

    venue_input = driver.find_element(By.XPATH, "//input[@placeholder='e.g. Seminar Hall']")
    assert "Seminar Hall" in venue_input.get_attribute("value")

    participants_input = driver.find_element(By.XPATH, "//input[@placeholder='e.g. 120']")
    assert "120" in participants_input.get_attribute("value")

    # Native input widgets: Start Date & End Date
    def set_native_input(elem, val):
        driver.execute_script(
            """
            var el = arguments[0];
            var val = arguments[1];
            var setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
            setter.call(el, val);
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
            """,
            elem,
            val,
        )

    date_start_input = driver.find_element(By.XPATH, "//input[@type='date'][1]")
    set_native_input(date_start_input, "2026-10-14")

    date_end_input = driver.find_elements(By.XPATH, "//input[@type='date']")[1]
    set_native_input(date_end_input, "2026-10-15")

    # Native input widgets: Start Time & End Time
    time_start_input = driver.find_element(By.XPATH, "//input[@type='time'][1]")
    set_native_input(time_start_input, "10:00")

    time_end_input = driver.find_elements(By.XPATH, "//input[@type='time']")[1]
    set_native_input(time_end_input, "17:00")

    # If any missing details questions are shown, answer them
    money_inputs = driver.find_elements(By.XPATH, "//input[@type='number' and @step='0.01']")
    for m_inp in money_inputs:
        m_inp.clear()
        m_inp.send_keys("5000")

    select_elements = driver.find_elements(By.TAG_NAME, "select")
    for s_elem in select_elements:
        options = s_elem.find_elements(By.TAG_NAME, "option")
        if len(options) > 1:
            options[1].click()

    # Fill any empty text inputs under missing questions
    text_inputs = driver.find_elements(By.XPATH, "//div[contains(., 'Additional details needed')]//input[@type='text']")
    for t_inp in text_inputs:
        val = t_inp.get_attribute("value")
        if not val:
            t_inp.send_keys("SVNIT Students")

    # Accept any AI-drafted fields (e.g. description/objectives)
    ai_draft_btns = driver.find_elements(By.XPATH, "//button[contains(., 'Accept AI Draft')]")
    for btn in ai_draft_btns:
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'}); arguments[0].click();", btn)
        time.sleep(0.3)

    # Confirm dates if checkbox shown
    confirm_labels = driver.find_elements(By.XPATH, "//label[@for='confirmDatesYear']")
    if confirm_labels:
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'}); arguments[0].click();", confirm_labels[0])
        time.sleep(0.3)

    # Reference numbers acceptance checkbox via label click with scroll
    ref_label = wait.until(EC.presence_of_element_located((By.XPATH, "//label[@for='acceptRefNumbers']")))
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'}); arguments[0].click();", ref_label)
    time.sleep(0.5)

    driver.save_screenshot(str(screenshots_dir / "08_ready_to_generate.png"))

    # Generate Documents (wait until enabled, then click with scroll)
    generate_btn = wait.until(EC.presence_of_element_located((By.XPATH, "//button[contains(., 'Generate Documents') and not(@disabled)]")))
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'}); arguments[0].click();", generate_btn)

    # Result Page renders
    try:
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Ready for Signatures')]")))
    except Exception as exc:
        driver.save_screenshot(str(screenshots_dir / "debug_generate_failure.png"))
        errors = driver.find_elements(By.XPATH, "//div[contains(@class, 'bg-red-50')]")
        err_text = [e.text for e in errors]
        print(f"\n[DEBUG ERROR ON SCREEN]: {err_text}\nURL: {driver.current_url}")
        raise exc
    time.sleep(2)
    driver.save_screenshot(str(screenshots_dir / "09_result_page_ready.png"))

    # Verify Result Page elements
    page_text = driver.page_source
    assert "Ready for Signatures" in page_text
    assert "Edit details" in page_text
    assert "Download All (.zip)" in page_text

    # Verify iframe preview is present
    iframe = driver.find_element(By.TAG_NAME, "iframe")
    assert iframe is not None
    assert "toolbar=0" in iframe.get_attribute("src")

    # Click "Edit details" -> returns to Home with prefilled state
    edit_details_btn = wait.until(EC.presence_of_element_located((By.XPATH, "//button[contains(., 'Edit details')]")))
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'}); arguments[0].click();", edit_details_btn)
    time.sleep(1.5)

    wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'What do you need?')]")))
    driver.save_screenshot(str(screenshots_dir / "10_returned_to_home_edit_details.png"))


def test_w7_04_mobile_layout_390px(e2e_server, browser, screenshots_dir, db_session):
    """Test 4: Mobile layout at 390px width asserting no horizontal scroll and all buttons reachable."""
    driver = browser
    wait = WebDriverWait(driver, 25)

    # Set viewport to 390px width (iPhone 12/13/14 standard mobile width)
    driver.set_window_size(390, 844)
    time.sleep(1)

    # Verify no horizontal scrollbar on document
    scroll_width = driver.execute_script("return document.documentElement.scrollWidth")
    client_width = driver.execute_script("return document.documentElement.clientWidth")
    
    driver.save_screenshot(str(screenshots_dir / "11_mobile_390px_home.png"))

    # Tolerance of up to 4px for borders/subpixels
    assert scroll_width <= client_width + 4, f"Horizontal overflow detected: scrollWidth={scroll_width}, clientWidth={client_width}"

    # Verify "What do you need?" is cleanly visible and buttons are reachable
    heading = wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'What do you need?')]")))
    assert heading.is_displayed()

    # Switch back to desktop viewport
    driver.set_window_size(1600, 1100)


def test_w7_05_club_settings_head_approves_and_templates_flow(e2e_server, browser, screenshots_dir, db_session):
    """Test 5: Club head uses Club settings (Members & Join Requests, Venues, etc.) and Templates navigation."""
    driver = browser
    wait = WebDriverWait(driver, 25)

    # 1. Click "Club settings" tab
    settings_tab = wait.until(EC.presence_of_element_located((By.XPATH, "//button[contains(., 'Club settings')]")))
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'}); arguments[0].click();", settings_tab)
    time.sleep(1)

    # Verify Club Administration & subtabs appear
    wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Club Administration') or contains(text(), 'Members & Access')]")))
    wait.until(EC.presence_of_element_located((By.XPATH, "//button[contains(., 'Members & Join Requests')]")))
    wait.until(EC.presence_of_element_located((By.XPATH, "//button[contains(., 'People & Signatories')]")))
    wait.until(EC.presence_of_element_located((By.XPATH, "//button[contains(., 'Venues & Facilities')]")))

    # 2. Click "Templates" tab
    templates_tab = wait.until(EC.presence_of_element_located((By.XPATH, "//button[contains(., 'Templates')]")))
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'}); arguments[0].click();", templates_tab)
    time.sleep(1)

    # Verify Template Gallery loads with starter templates
    wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Template Gallery')]")))
    wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Permission Letter')]")))

    # Click "Use Template" on Permission Letter -> takes user to Home
    use_btn = wait.until(EC.presence_of_element_located((By.XPATH, "//button[contains(., 'Use Template')]")))
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'}); arguments[0].click();", use_btn)
    time.sleep(1)

    # Verify user is taken to Home
    wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'What do you need?')]")))

    # 3. Click "My Documents" tab
    docs_tab = wait.until(EC.presence_of_element_located((By.XPATH, "//button[contains(., 'My Documents')]")))
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'}); arguments[0].click();", docs_tab)
    time.sleep(1)

    # Verify My Documents table loads
    wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'All Events') or contains(text(), 'Official Document')]")))

