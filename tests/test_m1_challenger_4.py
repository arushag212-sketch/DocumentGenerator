import os
import sys
import time
import subprocess
import urllib.request
import json

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

VITE_PORT = 5201
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

def set_viewport(driver, width, height, is_mobile=True):
    if is_mobile:
        driver.execute_cdp_cmd("Emulation.setDeviceMetricsOverride", {
            "width": int(width),
            "height": int(height),
            "deviceScaleFactor": 1,
            "mobile": True
        })
    else:
        driver.execute_cdp_cmd("Emulation.clearDeviceMetricsOverride", {})
        driver.set_window_size(int(width), int(height))


def run_challenger_suite():
    vite_proc = None
    driver = None
    summary = {
        'viewport_touch_targets': {},
        'backdrop_320_clearance': {},
        'rapid_toggle_test': {},
        'escape_key_test': {},
        'breakpoint_resize_test': {},
        'overall_pass': True
    }

    try:
        vite_proc = start_vite()
        driver = create_driver()
        wait = WebDriverWait(driver, 10)

        mobile_viewports = [
            (320, 568, 'iPhone SE 1st gen / 320px bounds'),
            (360, 640, 'Standard compact Android / 360px'),
            (375, 667, 'iPhone SE 2nd / iPhone 8 / 375px'),
            (390, 844, 'iPhone 12/13/14 / 390px'),
            (414, 896, 'iPhone Plus / Max / 414px'),
            (480, 854, 'Large Mobile / Phablet / 480px')
        ]

        # =========================================================================
        # PHASE 1: Viewport Touch Targets Across All 6 Mobile Breakpoints
        # =========================================================================
        print("\n=======================================================")
        print("  PHASE 1: TOUCH TARGETS ACROSS ALL MOBILE VIEWPORTS   ")
        print("=======================================================")

        for width, height, label in mobile_viewports:
            print(f"\n--- Testing Viewport: {width}x{height} ({label}) ---")
            set_viewport(driver, width, height, is_mobile=True)
            driver.get(BASE_URL)
            time.sleep(0.2)
            inner_w = driver.execute_script("return window.innerWidth;")
            print(f"  Emulated viewport innerWidth: {inner_w}px (target {width}px)")

            # 1. Hamburger button
            hamburger = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "header button[aria-label='Open menu']")))
            h_rect = hamburger.rect
            print(f"  Hamburger: {h_rect['width']}x{h_rect['height']} px (expected >= 44x44)")

            # 2. Header profile link
            profile = driver.find_element(By.CSS_SELECTOR, "header a[aria-label='Your profile']")
            p_rect = profile.rect
            print(f"  Header profile link: {p_rect['width']}x{p_rect['height']} px (expected >= 44x44)")

            # Open drawer
            hamburger.click()
            time.sleep(0.2)

            # 3. Drawer close button
            close_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "div[role='dialog'] button[aria-label='Close menu']")))
            c_rect = close_btn.rect
            print(f"  Drawer close button: {c_rect['width']}x{c_rect['height']} px (expected >= 44x44)")

            # 4. Aside bounds & backdrop clearance calculation
            aside = driver.find_element(By.CSS_SELECTOR, "div[role='dialog'] aside")
            aside_rect = aside.rect
            backdrop_width = inner_w - aside_rect['width']
            print(f"  Drawer aside rect: width={aside_rect['width']}px, height={aside_rect['height']}px")
            print(f"  Exposed backdrop width: {backdrop_width}px (expected >= 44px)")

            # 5. NavLinks
            nav_links = driver.find_elements(By.CSS_SELECTOR, "div[role='dialog'] nav[aria-label='Main'] a")
            nav_measurements = []
            for nl in nav_links:
                title = nl.text.strip().replace('\n', ' ')
                rect = nl.rect
                nav_measurements.append({'title': title, 'width': rect['width'], 'height': rect['height']})
                if rect['height'] < 44:
                    print(f"  [!] FAIL: Nav item '{title}' height {rect['height']}px < 44px")
                else:
                    print(f"  Nav item '{title}': {rect['width']}x{rect['height']} px (height >= 44)")

            # 6. New document CTA
            new_doc = driver.find_element(By.XPATH, "//div[@role='dialog']//aside//a[contains(., 'New document')]")
            nd_rect = new_doc.rect
            print(f"  New document CTA: {nd_rect['width']}x{nd_rect['height']} px (height expected >= 44)")

            # 7. Drawer sign out button
            signout = driver.find_element(By.CSS_SELECTOR, "div[role='dialog'] button[aria-label='Sign out']")
            so_rect = signout.rect
            print(f"  Sign out button: {so_rect['width']}x{so_rect['height']} px (expected >= 44x44)")

            # 8. Drawer profile link
            d_profile = driver.find_element(By.CSS_SELECTOR, "div[role='dialog'] aside div.border-t a[title='Your profile']")
            dp_rect = d_profile.rect
            print(f"  Drawer profile link: {dp_rect['width']}x{dp_rect['height']} px (height expected >= 44)")

            # 9. ClubSwitcher toggle button
            switcher = driver.find_element(By.CSS_SELECTOR, "div[role='dialog'] aside button[aria-haspopup='listbox']")
            sw_rect = switcher.rect
            print(f"  ClubSwitcher button: {sw_rect['width']}x{sw_rect['height']} px (height expected >= 44)")

            vp_pass = (
                h_rect['width'] >= 44 and h_rect['height'] >= 44 and
                p_rect['width'] >= 44 and p_rect['height'] >= 44 and
                c_rect['width'] >= 44 and c_rect['height'] >= 44 and
                so_rect['width'] >= 44 and so_rect['height'] >= 44 and
                nd_rect['height'] >= 44 and
                dp_rect['height'] >= 44 and
                sw_rect['height'] >= 44 and
                all(m['height'] >= 44 for m in nav_measurements) and
                backdrop_width >= 44
            )

            summary['viewport_touch_targets'][f'{width}px'] = {
                'passed': vp_pass,
                'label': label,
                'hamburger': h_rect,
                'header_profile': p_rect,
                'drawer_close': c_rect,
                'drawer_aside': aside_rect,
                'backdrop_width': backdrop_width,
                'signout': so_rect,
                'drawer_profile': dp_rect,
                'new_doc': nd_rect,
                'club_switcher': sw_rect,
                'nav_link_count': len(nav_measurements),
                'min_nav_height': min(m['height'] for m in nav_measurements)
            }

            if not vp_pass:
                summary['overall_pass'] = False

            # Close drawer
            close_btn.click()
            time.sleep(0.2)

        # =========================================================================
        # PHASE 2: 320px Minimum Screen Bounds & Backdrop Tap Dismissal Clearance
        # =========================================================================
        print("\n=======================================================")
        print("  PHASE 2: 320PX MINIMUM SCREEN BOUNDS & BACKDROP TAP  ")
        print("=======================================================")

        set_viewport(driver, 320, 568, is_mobile=True)
        driver.get(BASE_URL)
        time.sleep(0.2)

        h = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "header button[aria-label='Open menu']")))
        h.click()
        time.sleep(0.2)

        aside_320 = driver.find_element(By.CSS_SELECTOR, "div[role='dialog'] aside")
        aside_rect_320 = aside_320.rect
        actual_aside_w = aside_rect_320['width']
        # calc(100vw - 3rem) at 320px = 320 - 48 = 272px
        expected_max_w = 320 - 48
        exposed_backdrop_w = 320 - actual_aside_w
        print(f"  At 320px viewport:")
        print(f"    Aside measured width: {actual_aside_w}px (must be <= {expected_max_w}px)")
        print(f"    Exposed backdrop width: {exposed_backdrop_w}px (must be >= 48px)")

        # Verify elementFromPoint at coordinate (x=296, y=200) inside the exposed 48px backdrop band
        elem_at_point_tag = driver.execute_script("""
            var el = document.elementFromPoint(296, 200);
            return el ? el.className : 'null';
        """)
        print(f"    Element at exposed point (296, 200): '{elem_at_point_tag}'")
        is_backdrop_exposed = 'bg-slate-900/40' in elem_at_point_tag or 'backdrop' in elem_at_point_tag

        initial_overflow = driver.execute_script("return document.body.style.overflow;")
        print(f"    Pre-tap body overflow: '{initial_overflow}' (expected 'hidden')")

        # Tap the backdrop directly at the exposed coordinate (296, 200)
        driver.execute_script("document.elementFromPoint(296, 200).click();")
        time.sleep(0.3)


        dialogs_remaining = driver.find_elements(By.CSS_SELECTOR, "div[role='dialog']")
        post_tap_overflow = driver.execute_script("return document.body.style.overflow;")
        post_tap_touch = driver.execute_script("return document.body.style.touchAction;")
        dismissed_by_tap = len(dialogs_remaining) == 0

        print(f"    Drawer dismissed by backdrop click: {dismissed_by_tap}")
        print(f"    Post-tap body overflow: '{post_tap_overflow}' (expected '')")
        print(f"    Post-tap body touchAction: '{post_tap_touch}' (expected '')")

        b320_pass = (
            actual_aside_w <= expected_max_w + 1 and
            exposed_backdrop_w >= 44 and
            is_backdrop_exposed and
            dismissed_by_tap and
            post_tap_overflow == '' and
            post_tap_touch == ''
        )


        summary['backdrop_320_clearance'] = {
            'passed': b320_pass,
            'actual_aside_width': actual_aside_w,
            'expected_max_width': expected_max_w,
            'exposed_backdrop_width': exposed_backdrop_w,
            'dismissed_by_backdrop_tap': dismissed_by_tap,
            'overflow_restored': post_tap_overflow == '',
            'touch_action_restored': post_tap_touch == ''
        }

        if not b320_pass:
            summary['overall_pass'] = False

        # =========================================================================
        # PHASE 3: Rapid Open/Close Cycles & Escape Key Dismissal Stress Test
        # =========================================================================
        print("\n=======================================================")
        print("  PHASE 3: RAPID TOGGLE & ESCAPE DISMISSAL STRESS TEST ")
        print("=======================================================")

        rapid_failures = []
        CYCLES = 25
        print(f"  Executing {CYCLES} rapid open/close cycles on 320px viewport...")

        for i in range(CYCLES):
            h_btn = driver.find_element(By.CSS_SELECTOR, "header button[aria-label='Open menu']")
            h_btn.click()
            time.sleep(0.04)
            ov_open = driver.execute_script("return document.body.style.overflow;")
            ta_open = driver.execute_script("return document.body.style.touchAction;")

            c_btn = driver.find_element(By.CSS_SELECTOR, "div[role='dialog'] button[aria-label='Close menu']")
            c_btn.click()
            time.sleep(0.04)
            ov_closed = driver.execute_script("return document.body.style.overflow;")
            ta_closed = driver.execute_script("return document.body.style.touchAction;")

            if ov_open != 'hidden' or ta_open != 'none' or ov_closed != '' or ta_closed != '':
                rapid_failures.append({
                    'cycle': i,
                    'ov_open': ov_open,
                    'ta_open': ta_open,
                    'ov_closed': ov_closed,
                    'ta_closed': ta_closed
                })

        rapid_pass = len(rapid_failures) == 0
        print(f"  {CYCLES} rapid cycles result: {'PASS' if rapid_pass else 'FAIL'} (failures={len(rapid_failures)})")
        summary['rapid_toggle_test'] = {
            'passed': rapid_pass,
            'cycles_run': CYCLES,
            'failures': rapid_failures
        }
        if not rapid_pass:
            summary['overall_pass'] = False

        # Escape key dismissal test
        print("  Testing keyboard Escape dismissal...")
        h_btn = driver.find_element(By.CSS_SELECTOR, "header button[aria-label='Open menu']")
        h_btn.click()
        time.sleep(0.1)

        # Confirm open
        assert len(driver.find_elements(By.CSS_SELECTOR, "div[role='dialog']")) > 0
        assert driver.execute_script("return document.body.style.overflow;") == 'hidden'

        webdriver.ActionChains(driver).send_keys(Keys.ESCAPE).perform()
        time.sleep(0.15)

        esc_dialogs = driver.find_elements(By.CSS_SELECTOR, "div[role='dialog']")
        esc_overflow = driver.execute_script("return document.body.style.overflow;")
        esc_touch = driver.execute_script("return document.body.style.touchAction;")

        esc_pass = (len(esc_dialogs) == 0) and (esc_overflow == '') and (esc_touch == '')
        print(f"  Escape dismissal: {'PASS' if esc_pass else 'FAIL'} (dialog unmounted={len(esc_dialogs) == 0}, overflow='{esc_overflow}')")
        summary['escape_key_test'] = {
            'passed': esc_pass,
            'dialog_unmounted': len(esc_dialogs) == 0,
            'overflow_restored': esc_overflow == '',
            'touch_action_restored': esc_touch == ''
        }
        if not esc_pass:
            summary['overall_pass'] = False

        # =========================================================================
        # PHASE 4: Breakpoint Transition Stress (320px -> 1280px -> 360px)
        # =========================================================================
        print("\n=======================================================")
        print("  PHASE 4: BREAKPOINT TRANSITION STRESS TEST           ")
        print("=======================================================")

        # Open drawer on 320px
        set_viewport(driver, 320, 568, is_mobile=True)
        time.sleep(0.1)
        h_btn = driver.find_element(By.CSS_SELECTOR, "header button[aria-label='Open menu']")
        h_btn.click()
        time.sleep(0.1)
        print("  Opened drawer on 320px mobile viewport.")

        # Resize directly to 1280px desktop while drawer is open
        set_viewport(driver, 1280, 800, is_mobile=False)
        time.sleep(0.3)
        ov_desktop = driver.execute_script("return document.body.style.overflow;")
        ta_desktop = driver.execute_script("return document.body.style.touchAction;")
        desktop_dialogs = driver.find_elements(By.CSS_SELECTOR, "div[role='dialog']")
        desktop_sidebar = driver.find_element(By.CSS_SELECTOR, "aside.hidden.lg\\:block")

        sidebar_displayed_at_1280 = desktop_sidebar.is_displayed()
        print(f"  After resize to 1280px:")
        print(f"    Desktop sidebar displayed: {sidebar_displayed_at_1280}")
        print(f"    Drawer unmounted from DOM: {len(desktop_dialogs) == 0}")
        print(f"    Body overflow on desktop: '{ov_desktop}' (must be '')")
        print(f"    Body touchAction on desktop: '{ta_desktop}' (must be '')")

        # Verify scroll works on desktop
        driver.execute_script("window.scrollTo(0, 400);")
        time.sleep(0.1)
        scroll_pos = driver.execute_script("return window.scrollY;")
        print(f"    Desktop scrollY after window.scrollTo(0, 400): {scroll_pos}px (expected 400)")

        # Resize back to 360px mobile
        set_viewport(driver, 360, 640, is_mobile=True)
        time.sleep(0.3)
        mobile_dialogs_after = driver.find_elements(By.CSS_SELECTOR, "div[role='dialog']")
        ov_mobile_after = driver.execute_script("return document.body.style.overflow;")
        sidebar_hidden_at_360 = not desktop_sidebar.is_displayed()
        print(f"  After resizing back to 360px mobile:")
        print(f"    Desktop sidebar hidden: {sidebar_hidden_at_360}")
        print(f"    Drawer remains closed: {len(mobile_dialogs_after) == 0}")
        print(f"    Body overflow remains clean: '{ov_mobile_after}'")

        bp_pass = (
            sidebar_displayed_at_1280 and
            len(desktop_dialogs) == 0 and
            ov_desktop == '' and
            ta_desktop == '' and
            scroll_pos > 0 and
            sidebar_hidden_at_360 and
            len(mobile_dialogs_after) == 0 and
            ov_mobile_after == ''
        )

        summary['breakpoint_resize_test'] = {
            'passed': bp_pass,
            'desktop_sidebar_visible_at_1280': sidebar_displayed_at_1280,
            'desktop_sidebar_hidden_at_360': sidebar_hidden_at_360,
            'drawer_unmounted_on_desktop': len(desktop_dialogs) == 0,
            'desktop_overflow_clean': ov_desktop == '',
            'desktop_scrollable': scroll_pos > 0,
            'drawer_closed_on_return_to_mobile': len(mobile_dialogs_after) == 0
        }
        if not bp_pass:
            summary['overall_pass'] = False


    finally:
        if driver:
            driver.quit()
        if vite_proc:
            print("\n[*] Terminating Vite process...")
            subprocess.run(f"taskkill /F /T /PID {vite_proc.pid}", shell=True, capture_output=True)

    print("\n=======================================================")
    print("           CHALLENGER 4 FINAL VERDICT SUMMARY          ")
    print("=======================================================")
    print(f"OVERALL RESULT: {'APPROVE (ALL PASSED)' if summary['overall_pass'] else 'REQUEST_CHANGES (FAILURES DETECTED)'}")
    print(json.dumps(summary, indent=2))
    return summary

if __name__ == "__main__":
    res = run_challenger_suite()
    if not res['overall_pass']:
        sys.exit(1)
    sys.exit(0)
