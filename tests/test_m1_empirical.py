import os
import sys
import time
import subprocess
import urllib.request

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr.encoding != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8')

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.edge.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

VITE_PORT = 5199
BASE_URL = f"http://localhost:{VITE_PORT}/test-shell.html"

def start_vite():
    try:
        with urllib.request.urlopen(BASE_URL, timeout=1) as resp:
            if resp.status == 200:
                print(f"[+] Vite dev server is already running at {BASE_URL}")
                return None
    except Exception:
        pass

    print(f"[*] Starting Vite dev server on port {VITE_PORT}...")
    proc = subprocess.Popen(
        f"npx vite --port {VITE_PORT}",
        cwd=os.path.abspath("frontend"),
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    start_time = time.time()
    while time.time() - start_time < 20:
        try:
            with urllib.request.urlopen(BASE_URL, timeout=1) as resp:
                if resp.status == 200:
                    print(f"[+] Vite dev server is UP at {BASE_URL}")
                    return proc
        except Exception:
            time.sleep(0.5)
    raise RuntimeError(f"Vite server failed to start within 20s on port {VITE_PORT}")

def create_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Edge(options=opts)
    return driver

def run_tests():
    vite_proc = None
    driver = None
    results = {}
    try:
        vite_proc = start_vite()
        driver = create_driver()

        # -------------------------------------------------------------
        # TEST 1: Mobile Touch Envelope Dimensions (at 375x812)
        # -------------------------------------------------------------
        print("\n=== TEST 1: Touch Envelope Dimensions (Mobile 375px) ===")
        driver.set_window_size(375, 812)
        driver.get(BASE_URL)
        wait = WebDriverWait(driver, 10)

        # Header hamburger button
        hamburger = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "header button[aria-label='Open menu']")))
        h_box = hamburger.rect
        print(f"Hamburger button: {h_box['width']}px × {h_box['height']}px (expected >= 44x44)")

        # Header profile link
        profile_link = driver.find_element(By.CSS_SELECTOR, "header a[aria-label='Your profile']")
        p_box = profile_link.rect
        print(f"Header profile link: {p_box['width']}px × {p_box['height']}px (expected >= 44x44)")

        # Open drawer
        hamburger.click()
        time.sleep(0.3)

        # Drawer close button
        close_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "div[role='dialog'] button[aria-label='Close menu']")))
        c_box = close_btn.rect
        print(f"Drawer close button: {c_box['width']}px × {c_box['height']}px (expected >= 44x44)")

        # Drawer aside max width check
        aside = driver.find_element(By.CSS_SELECTOR, "div[role='dialog'] aside")
        aside_box = aside.rect
        print(f"Mobile drawer aside width: {aside_box['width']}px (window=375px, max-w=calc(100vw-3rem)={375-48}px)")

        # Drawer NavLinks (scoped to drawer dialog)
        nav_links = driver.find_elements(By.CSS_SELECTOR, "div[role='dialog'] nav[aria-label='Main'] a")
        nav_results = []
        for nl in nav_links:
            text = nl.text.strip().replace('\n', ' ')
            nl_box = nl.rect
            nav_results.append((text, nl_box['width'], nl_box['height']))
            print(f"Nav item '{text}': {nl_box['width']}px × {nl_box['height']}px (height expected >= 44px)")

        # New document CTA
        new_doc_btn = driver.find_element(By.XPATH, "//div[@role='dialog']//aside//a[contains(., 'New document')]")
        nd_box = new_doc_btn.rect
        print(f"New document CTA: {nd_box['width']}px × {nd_box['height']}px (height expected >= 44px)")

        # Sign out button
        signout_btn = driver.find_element(By.CSS_SELECTOR, "div[role='dialog'] button[aria-label='Sign out']")
        so_box = signout_btn.rect
        print(f"Sign out button: {so_box['width']}px × {so_box['height']}px (expected >= 44x44)")

        # User profile link in drawer footer
        footer_profile = driver.find_element(By.CSS_SELECTOR, "div[role='dialog'] aside div.border-t a[title='Your profile']")
        fp_box = footer_profile.rect
        print(f"Footer profile link: {fp_box['width']}px × {fp_box['height']}px (height expected >= 44px)")

        test1_pass = (
            h_box['width'] >= 44 and h_box['height'] >= 44 and
            p_box['width'] >= 44 and p_box['height'] >= 44 and
            c_box['width'] >= 44 and c_box['height'] >= 44 and
            so_box['width'] >= 44 and so_box['height'] >= 44 and
            nd_box['height'] >= 44 and
            fp_box['height'] >= 44 and
            all(h >= 44 for _, _, h in nav_results) and
            aside_box['width'] <= (375 - 48 + 2) # tolerance
        )
        results['test1_touch_envelopes'] = {
            'passed': test1_pass,
            'hamburger': h_box,
            'header_profile': p_box,
            'drawer_close': c_box,
            'drawer_aside': aside_box,
            'signout': so_box,
            'new_doc': nd_box,
            'nav_links': nav_results
        }

        # Close drawer for next test
        close_btn.click()
        time.sleep(0.3)

        # -------------------------------------------------------------
        # TEST 2: Rapid Opening/Closing & Scroll Style Restoration
        # -------------------------------------------------------------
        print("\n=== TEST 2: Rapid Opening/Closing & Scroll Restoration ===")
        initial_overflow = driver.execute_script("return document.body.style.overflow;")
        initial_touch = driver.execute_script("return document.body.style.touchAction;")
        print(f"Baseline: overflow='{initial_overflow}', touchAction='{initial_touch}'")

        rapid_success = True
        rapid_log = []
        for cycle in range(20):
            # Click hamburger to open
            h = driver.find_element(By.CSS_SELECTOR, "header button[aria-label='Open menu']")
            h.click()
            time.sleep(0.05)
            ov_open = driver.execute_script("return document.body.style.overflow;")
            ta_open = driver.execute_script("return document.body.style.touchAction;")

            # Click close button to close
            c = driver.find_element(By.CSS_SELECTOR, "div[role='dialog'] button[aria-label='Close menu']")
            c.click()
            time.sleep(0.05)
            ov_closed = driver.execute_script("return document.body.style.overflow;")
            ta_closed = driver.execute_script("return document.body.style.touchAction;")

            if ov_open != 'hidden' or ta_open != 'none' or ov_closed != initial_overflow or ta_closed != initial_touch:
                rapid_success = False
                rapid_log.append((cycle, ov_open, ta_open, ov_closed, ta_closed))

        # Test backdrop click closure (click on the exposed backdrop area on the right, x=330, y=200)
        h = driver.find_element(By.CSS_SELECTOR, "header button[aria-label='Open menu']")
        h.click()
        time.sleep(0.1)
        webdriver.ActionChains(driver).move_by_offset(330, 200).click().perform()
        time.sleep(0.1)
        # reset mouse
        webdriver.ActionChains(driver).move_by_offset(-330, -200).perform()
        ov_after_backdrop = driver.execute_script("return document.body.style.overflow;")
        ta_after_backdrop = driver.execute_script("return document.body.style.touchAction;")
        dialog_present = len(driver.find_elements(By.CSS_SELECTOR, "div[role='dialog']")) > 0

        test2_pass = rapid_success and ov_after_backdrop == initial_overflow and not dialog_present
        print(f"20 rapid cycles passed: {rapid_success} (failures={len(rapid_log)})")
        print(f"Backdrop click closes: {not dialog_present}, overflow restored: {ov_after_backdrop == initial_overflow}")
        results['test2_rapid_cycles'] = {
            'passed': test2_pass,
            'rapid_success': rapid_success,
            'failures': rapid_log,
            'backdrop_close': not dialog_present,
            'overflow_restored': ov_after_backdrop == initial_overflow
        }

        # -------------------------------------------------------------
        # TEST 3: Escape Key Dismissal & Scroll Restoration
        # -------------------------------------------------------------
        print("\n=== TEST 3: Escape Key Dismissal ===")
        h = driver.find_element(By.CSS_SELECTOR, "header button[aria-label='Open menu']")
        h.click()
        time.sleep(0.1)
        ov_pre_esc = driver.execute_script("return document.body.style.overflow;")
        assert ov_pre_esc == 'hidden', "Body overflow should be hidden while drawer is open"

        # Send Escape key
        webdriver.ActionChains(driver).send_keys(Keys.ESCAPE).perform()
        time.sleep(0.1)

        ov_post_esc = driver.execute_script("return document.body.style.overflow;")
        ta_post_esc = driver.execute_script("return document.body.style.touchAction;")
        drawer_exists = len(driver.find_elements(By.CSS_SELECTOR, "div[role='dialog']")) > 0

        test3_pass = (not drawer_exists) and (ov_post_esc == initial_overflow) and (ta_post_esc == initial_touch)
        print(f"Drawer dismissed by Escape: {not drawer_exists}")
        print(f"Overflow restored: '{ov_post_esc}' == '{initial_overflow}', touchAction: '{ta_post_esc}' == '{initial_touch}'")
        results['test3_escape_dismissal'] = {
            'passed': test3_pass,
            'drawer_dismissed': not drawer_exists,
            'overflow_restored': ov_post_esc == initial_overflow,
            'touch_restored': ta_post_esc == initial_touch
        }

        # -------------------------------------------------------------
        # TEST 4: Viewport Resizing Across Breakpoint (Stress Test)
        # -------------------------------------------------------------
        print("\n=== TEST 4: Viewport Resizing Across Breakpoint While Drawer Open ===")
        # 1. Open drawer at mobile 375x812
        driver.set_window_size(375, 812)
        time.sleep(0.1)
        h = driver.find_element(By.CSS_SELECTOR, "header button[aria-label='Open menu']")
        h.click()
        time.sleep(0.1)
        assert len(driver.find_elements(By.CSS_SELECTOR, "div[role='dialog']")) > 0
        ov_mobile_open = driver.execute_script("return document.body.style.overflow;")
        print(f"Mobile drawer open: body.style.overflow='{ov_mobile_open}'")

        # 2. Resize to desktop 1280x800 while mobile drawer is still open!
        driver.set_window_size(1280, 800)
        time.sleep(0.3)

        # Inspect desktop sidebar
        desktop_sidebar = driver.find_element(By.CSS_SELECTOR, "aside.hidden.lg\\:block")
        sidebar_displayed = desktop_sidebar.is_displayed()
        print(f"Desktop sidebar displayed at 1280px: {sidebar_displayed}")

        # Inspect mobile drawer element
        drawer_elements = driver.find_elements(By.CSS_SELECTOR, "div[role='dialog']")
        drawer_in_dom = len(drawer_elements) > 0
        drawer_displayed = drawer_elements[0].is_displayed() if drawer_in_dom else False
        print(f"Mobile drawer in DOM at 1280px: {drawer_in_dom}, displayed: {drawer_displayed}")

        # Inspect body styles after resize!
        ov_desktop = driver.execute_script("return document.body.style.overflow;")
        ta_desktop = driver.execute_script("return document.body.style.touchAction;")
        print(f"Body styles after resize to desktop while drawer was open: overflow='{ov_desktop}', touchAction='{ta_desktop}'")

        # Check whether the page can scroll on desktop!
        driver.execute_script("window.scrollTo(0, 500);")
        time.sleep(0.1)
        scroll_y = driver.execute_script("return window.scrollY;")
        print(f"window.scrollY after window.scrollTo(0, 500): {scroll_y}px")

        # Now test: what happens if user resizes back down to mobile (375x812)?
        driver.set_window_size(375, 812)
        time.sleep(0.3)
        drawer_back_on_mobile = len(driver.find_elements(By.CSS_SELECTOR, "div[role='dialog']")) > 0
        drawer_displayed_back = driver.find_elements(By.CSS_SELECTOR, "div[role='dialog']")[0].is_displayed() if drawer_back_on_mobile else False
        print(f"After resizing back to mobile 375px: drawer displayed: {drawer_displayed_back}")

        # Close the drawer now
        if drawer_back_on_mobile:
            close_b = driver.find_element(By.CSS_SELECTOR, "div[role='dialog'] button[aria-label='Close menu']")
            close_b.click()
            time.sleep(0.1)

        ov_final = driver.execute_script("return document.body.style.overflow;")
        print(f"After closing drawer on mobile: overflow='{ov_final}'")

        results['test4_resize_stress'] = {
            'sidebar_displayed_at_1280': sidebar_displayed,
            'drawer_hidden_by_css_at_1280': not drawer_displayed,
            'body_overflow_at_1280': ov_desktop,
            'body_touch_at_1280': ta_desktop,
            'stuck_body_lock_on_desktop': (ov_desktop == 'hidden'),
            'desktop_scroll_y_result': scroll_y,
            'drawer_remained_open_on_resize_back': drawer_displayed_back,
            'overflow_restored_after_close': (ov_final == initial_overflow)
        }

        # -------------------------------------------------------------
        # TEST 5: Strict Desktop Layout Baseline (1280x800)
        # -------------------------------------------------------------
        print("\n=== TEST 5: Desktop Baseline Preservation (1280x800) ===")
        driver.set_window_size(1280, 800)
        time.sleep(0.2)
        desktop_aside = driver.find_element(By.CSS_SELECTOR, "aside.hidden.lg\\:block")
        header = driver.find_element(By.CSS_SELECTOR, "header.lg\\:hidden")
        h_displayed = header.is_displayed()
        s_displayed = desktop_aside.is_displayed()
        s_box = desktop_aside.rect
        print(f"Desktop sidebar width: {s_box['width']}px, isDisplayed: {s_displayed}")
        print(f"Mobile header isDisplayed at 1280px: {h_displayed}")

        # Normal desktop scroll
        driver.execute_script("window.scrollTo(0, 500);")
        time.sleep(0.1)
        desktop_scroll = driver.execute_script("return window.scrollY;")
        print(f"Normal desktop scrollY: {desktop_scroll}px (expected > 0)")

        test5_pass = s_displayed and not h_displayed and desktop_scroll > 0
        results['test5_desktop_preservation'] = {
            'passed': test5_pass,
            'sidebar_width': s_box['width'],
            'sidebar_displayed': s_displayed,
            'header_hidden': not h_displayed,
            'desktop_scrollable': desktop_scroll > 0
        }

    finally:
        if driver:
            driver.quit()
        if vite_proc:
            print("[*] Terminating Vite process...")
            subprocess.run(f"taskkill /F /T /PID {vite_proc.pid}", shell=True, capture_output=True)

    print("\n==========================================")
    print("           CHALLENGE RESULTS SUMMARY       ")
    print("==========================================")
    for test_name, res in results.items():
        print(f"{test_name}: {res}")
    return results

if __name__ == "__main__":
    run_tests()
