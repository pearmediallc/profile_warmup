"""
Test script to find and verify Facebook selectors
Run with: python3 test_selectors.py

This opens a visible browser so you can:
1. See the login page
2. Manually inspect elements
3. Test the selectors
"""

import time
from playwright.sync_api import sync_playwright

def test_login_selectors():
    """Test login page selectors"""
    print("\n" + "="*60)
    print("TESTING FACEBOOK LOGIN SELECTORS")
    print("="*60)

    with sync_playwright() as p:
        # Launch visible browser (not headless)
        browser = p.chromium.launch(headless=False)
        page = browser.new_page(
            viewport={'width': 1280, 'height': 720},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )

        print("\n[1] Opening Facebook...")
        page.goto("https://www.facebook.com")
        time.sleep(3)

        # Test email input
        print("\n[2] Testing email input selector: input[name='email']")
        try:
            email_input = page.locator('input[name="email"]')
            if email_input.count() > 0:
                print("    FOUND! Email input exists")
                email_input.highlight()
            else:
                print("    NOT FOUND!")
        except Exception as e:
            print(f"    ERROR: {e}")

        # Test password input
        print("\n[3] Testing password input selector: input[name='pass']")
        try:
            pass_input = page.locator('input[name="pass"]')
            if pass_input.count() > 0:
                print("    FOUND! Password input exists")
                pass_input.highlight()
            else:
                print("    NOT FOUND!")
        except Exception as e:
            print(f"    ERROR: {e}")

        # Test login button
        print("\n[4] Testing login button selector...")
        selectors_to_try = [
            'div[role="none"]:has(span:text("Log in"))',
            'button[name="login"]',
            'button:has-text("Log in")',
            'span:text("Log in")',
            '[data-testid="royal_login_button"]',
        ]

        for selector in selectors_to_try:
            try:
                btn = page.locator(selector)
                if btn.count() > 0:
                    print(f"    FOUND: {selector}")
                    btn.first.highlight()
                    break
            except Exception:
                pass

        print("\n" + "="*60)
        print("BROWSER IS NOW OPEN")
        print("="*60)
        print("""
What to do now:
1. Right-click on any element -> Inspect
2. Find the selector (name, aria-label, role, text)
3. Press Enter here when done to close browser
        """)

        input("\nPress Enter to close browser...")
        browser.close()


def test_home_selectors():
    """Test home page selectors (requires login)"""
    print("\n" + "="*60)
    print("TESTING HOME PAGE SELECTORS")
    print("="*60)
    print("""
To test home page selectors, you need to:
1. Run test_login_selectors() first
2. Manually log in
3. Then inspect the home page elements

For now, here are the selectors we're using:
- Like button: //div[@aria-label="Like"][@role="button"]
- See more: span:text("See more")
- Add friend: //span[text()="Add friend"]/ancestor::div[@role="button"]
    """)


if __name__ == "__main__":
    print("""
Facebook Selector Tester
========================
This will open a browser to test selectors.

Choose what to test:
1. Login page selectors
2. Show home page selector info
q. Quit
    """)

    choice = input("Enter choice (1/2/q): ").strip()

    if choice == "1":
        test_login_selectors()
    elif choice == "2":
        test_home_selectors()
    else:
        print("Exiting...")
