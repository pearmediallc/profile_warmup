"""
Quick headless test for selectors
"""
from playwright.sync_api import sync_playwright
import time

print("Testing Playwright in headless mode...")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    print("1. Opening Facebook...")
    page.goto("https://www.facebook.com")
    time.sleep(2)

    print("2. Checking selectors...")

    # Email input
    email = page.locator('input[name="email"]')
    print(f"   Email input: {'FOUND' if email.count() > 0 else 'NOT FOUND'}")

    # Password input
    password = page.locator('input[name="pass"]')
    print(f"   Password input: {'FOUND' if password.count() > 0 else 'NOT FOUND'}")

    # Login button - try multiple selectors
    login_selectors = [
        ('div[role="none"]:has(span:text("Log in"))', 'div with span'),
        ('button[name="login"]', 'button name'),
        ('button:has-text("Log in")', 'button has-text'),
        ('[data-testid="royal_login_button"]', 'data-testid'),
    ]

    for selector, desc in login_selectors:
        try:
            btn = page.locator(selector)
            if btn.count() > 0:
                print(f"   Login button ({desc}): FOUND - {selector}")
        except:
            pass

    # Take screenshot
    page.screenshot(path="/tmp/fb_login_test.png")
    print("\n3. Screenshot saved to: /tmp/fb_login_test.png")

    browser.close()
    print("\nDone! Check the screenshot to see the page.")
