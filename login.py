"""
Facebook Login Handler
"""

import asyncio
import random
import logging
from playwright.async_api import Page
from human_actions import human_click, random_delay, human_delay

logger = logging.getLogger(__name__)


class FacebookLogin:
    """Handles Facebook login with human-like behavior"""

    def __init__(self, page: Page):
        self.page = page

    async def login(self, email: str, password: str) -> bool:
        """
        Login to Facebook with human-like typing and delays

        Args:
            email: Facebook email/phone
            password: Facebook password

        Returns:
            True if login successful, False otherwise
        """
        try:
            logger.info("Starting Facebook login...")

            # Navigate to Facebook
            await self.page.goto('https://www.facebook.com', timeout=30000)
            await random_delay(2, 4)

            # Handle cookie consent if present
            await self._handle_cookie_consent()

            # ========== STEP 1: Enter Email ==========
            # Using exact data-testid from Facebook HTML
            email_selectors = [
                'input[data-testid="royal_email"]',
                'input[data-testid="royal-email"]',
                'input#email',
                'input[name="email"]',
            ]

            email_input = None
            for selector in email_selectors:
                try:
                    email_input = await self.page.wait_for_selector(selector, timeout=5000)
                    if email_input:
                        logger.info(f"Found email input with: {selector}")
                        break
                except Exception:
                    continue

            if not email_input:
                logger.error("Could not find email input field")
                await self.page.screenshot(path="error_no_email_field.png")
                return False

            logger.info("Clicking email input...")
            await human_click(self.page, email_input)
            await random_delay(0.3, 0.7)

            # Clear any existing text first
            await email_input.fill('')
            await random_delay(0.2, 0.4)

            # Type email with human-like speed
            logger.info(f"Typing email: {email}")
            await self._human_type(email_input, email)
            await random_delay(0.5, 1.5)

            # ========== STEP 2: Enter Password ==========
            # Using exact data-testid from Facebook HTML
            password_selectors = [
                'input[data-testid="royal_pass"]',
                'input[data-testid="royal-pass"]',
                'input#pass',
                'input[name="pass"]',
            ]

            password_input = None
            for selector in password_selectors:
                try:
                    password_input = await self.page.wait_for_selector(selector, timeout=5000)
                    if password_input:
                        logger.info(f"Found password input with: {selector}")
                        break
                except Exception:
                    continue

            if not password_input:
                logger.error("Could not find password input field")
                await self.page.screenshot(path="error_no_password_field.png")
                return False

            logger.info("Clicking password input...")
            await human_click(self.page, password_input)
            await random_delay(0.3, 0.7)

            # Clear any existing text first
            await password_input.fill('')
            await random_delay(0.2, 0.4)

            # Type password with human-like speed
            logger.info("Typing password...")
            await self._human_type(password_input, password)
            await random_delay(0.5, 1.0)

            # ========== STEP 3: Click Login Button ==========
            # Using exact data-testid from Facebook HTML
            login_selectors = [
                'button[data-testid="royal_login_button"]',
                'button[data-testid="royal-login-button"]',
                'button#u_0_5_aZ',
                'button[name="login"]',
                'button[type="submit"]._42ft',
                'button._42ft._4jy0._6lth',
                'button[type="submit"]',
            ]

            login_button = None
            for selector in login_selectors:
                try:
                    login_button = await self.page.query_selector(selector)
                    if login_button and await login_button.is_visible():
                        logger.info(f"Found login button with: {selector}")
                        break
                except Exception:
                    continue

            if login_button:
                logger.info("Clicking login button...")
                await random_delay(0.3, 0.5)
                await human_click(self.page, login_button)
            else:
                # Fallback: press Enter
                logger.info("No login button found, pressing Enter...")
                await self.page.keyboard.press('Enter')

            # Wait for navigation after login
            logger.info("Waiting for page load after login...")
            await self.page.wait_for_load_state('networkidle', timeout=30000)

            # Wait 1 minute for page to fully load and stabilize
            logger.info("⏳ Waiting 60 seconds for page to fully load...")
            print("⏳ Waiting 60 seconds for Facebook to fully load...")
            for i in range(60, 0, -10):
                print(f"    {i} seconds remaining...")
                await asyncio.sleep(10)
            print("✅ Page load wait complete!")

            # Check if login was successful
            if await self._is_logged_in():
                logger.info("Login successful!")
                return True
            else:
                # Take screenshot to see what happened
                screenshot_path = f"login_failed_{email.split('@')[0]}.png"
                await self.page.screenshot(path=screenshot_path)
                logger.error(f"Login failed - screenshot saved: {screenshot_path}")

                # Check for specific issues
                current_url = self.page.url
                page_content = await self.page.content()

                if 'checkpoint' in current_url:
                    logger.error("❌ SECURITY CHECKPOINT - Facebook needs verification!")
                    print("⚠️  Facebook security checkpoint detected!")
                    print("    Please verify your account manually in the browser.")
                elif 'two_step_verification' in current_url or '2fa' in current_url.lower():
                    logger.error("❌ 2FA REQUIRED - Two-factor authentication needed!")
                    print("⚠️  Two-factor authentication required!")
                elif 'login' in current_url:
                    logger.error("❌ WRONG CREDENTIALS - Email or password incorrect!")
                    print("⚠️  Login failed - check email/password!")
                elif 'captcha' in page_content.lower() or 'robot' in page_content.lower():
                    logger.error("❌ CAPTCHA - Facebook thinks this is a bot!")
                    print("⚠️  Captcha detected!")
                else:
                    logger.error(f"❌ UNKNOWN - Current URL: {current_url}")
                    print(f"⚠️  Unknown login issue. Check screenshot: {screenshot_path}")

                return False

        except Exception as e:
            logger.error(f"Login error: {e}")
            return False

    async def navigate_to_pages(self) -> bool:
        """
        After login, navigate to Pages section:
        1. Click "See more" in sidebar
        2. Click on "Pages" option
        """
        try:
            logger.info("Navigating to Pages section...")

            # ========== STEP 1: Click "See more" ==========
            await random_delay(2, 4)

            see_more_selectors = [
                # Exact match for "See more" text
                'span:has-text("See more")',
                'div:has-text("See more"):not(:has(div:has-text("See more")))',
                '[aria-label*="See more"]',
                # Using the class structure provided
                'div.x6s0dn4 span:has-text("See more")',
            ]

            see_more_button = None
            for selector in see_more_selectors:
                try:
                    elements = await self.page.query_selector_all(selector)
                    for el in elements:
                        if await el.is_visible():
                            text = await el.text_content()
                            if text and 'see more' in text.lower().strip():
                                see_more_button = el
                                logger.info(f"Found 'See more' with selector: {selector}")
                                break
                    if see_more_button:
                        break
                except Exception:
                    continue

            if see_more_button:
                await human_click(self.page, see_more_button)
                await random_delay(1, 2)
                logger.info("Clicked 'See more'")
            else:
                logger.warning("Could not find 'See more' button")
                # Try direct navigation as fallback
                return await self._navigate_to_pages_direct()

            # ========== STEP 2: Click "Pages" ==========
            await random_delay(1, 2)

            pages_selectors = [
                # Text-based selectors for "Pages"
                'a[href*="/pages"] span:has-text("Pages")',
                'a:has-text("Pages")',
                'div[role="link"]:has-text("Pages")',
                'span:has-text("Pages")',
                # CSS selector provided by user
                'ul li a div div:has-text("Pages")',
            ]

            pages_button = None
            for selector in pages_selectors:
                try:
                    elements = await self.page.query_selector_all(selector)
                    for el in elements:
                        if await el.is_visible():
                            text = await el.text_content()
                            if text and text.strip().lower() == 'pages':
                                pages_button = el
                                logger.info(f"Found 'Pages' with selector: {selector}")
                                break
                    if pages_button:
                        break
                except Exception:
                    continue

            if pages_button:
                await human_click(self.page, pages_button)
                await random_delay(2, 4)
                logger.info("Clicked 'Pages' - navigated successfully!")
                return True
            else:
                logger.warning("Could not find 'Pages' option")
                return await self._navigate_to_pages_direct()

        except Exception as e:
            logger.error(f"Error navigating to Pages: {e}")
            return await self._navigate_to_pages_direct()

    async def _navigate_to_pages_direct(self) -> bool:
        """Fallback: Navigate directly to Pages URL"""
        try:
            logger.info("Using direct navigation to Pages...")
            await self.page.goto('https://www.facebook.com/pages/', timeout=30000)
            await self.page.wait_for_load_state('networkidle')
            await random_delay(2, 3)
            logger.info("Navigated to Pages directly")
            return True
        except Exception as e:
            logger.error(f"Direct navigation failed: {e}")
            return False

    async def _human_type(self, element, text: str) -> None:
        """Type text with human-like speed variations"""
        for char in text:
            await element.type(char, delay=random.randint(50, 150))
            # Occasional longer pause (simulates thinking)
            if random.random() < 0.1:
                await asyncio.sleep(random.uniform(0.2, 0.5))

    async def _handle_cookie_consent(self) -> None:
        """Handle cookie consent popup if present"""
        try:
            # Common cookie consent button selectors
            selectors = [
                'button[data-cookiebanner="accept_button"]',
                'button[title*="Accept"]',
                'button[title*="Allow"]',
                '[aria-label*="Accept"]',
                '[aria-label*="Allow all cookies"]',
                'button:has-text("Allow")',
                'button:has-text("Accept")',
            ]

            for selector in selectors:
                try:
                    button = await self.page.query_selector(selector)
                    if button and await button.is_visible():
                        await human_click(self.page, button)
                        await random_delay(1, 2)
                        logger.info("Accepted cookie consent")
                        return
                except Exception:
                    continue

        except Exception as e:
            logger.debug(f"No cookie consent or error: {e}")

    async def _is_logged_in(self) -> bool:
        """Check if we're successfully logged in"""
        try:
            current_url = self.page.url
            logger.info(f"Checking login status... Current URL: {current_url}")

            # First check URL - if still on login page or checkpoint, not logged in
            if 'login' in current_url and 'facebook.com/login' in current_url:
                logger.info("Still on login page")
                return False

            if 'checkpoint' in current_url:
                logger.info("On checkpoint page")
                return False

            # Check for elements that only appear when logged in
            logged_in_indicators = [
                # Profile/Account indicators
                '[aria-label="Your profile"]',
                '[aria-label="Account"]',
                '[aria-label="Account Controls and Settings"]',
                # Navigation elements
                '[aria-label="Facebook"]',
                '[data-pagelet="LeftRail"]',
                # Feed indicators
                '[data-pagelet="Feed"]',
                '[role="feed"]',
                'div[role="main"]',
                # Composer (create post)
                '[aria-label="Create a post"]',
                '[aria-label*="What\'s on your mind"]',
                # Stories
                '[data-pagelet="Stories"]',
                # Messenger
                '[aria-label="Messenger"]',
                # Notifications
                '[aria-label="Notifications"]',
            ]

            for selector in logged_in_indicators:
                try:
                    element = await self.page.query_selector(selector)
                    if element and await element.is_visible():
                        logger.info(f"✅ Logged in! Found: {selector}")
                        return True
                except Exception:
                    continue

            # Check if we're on the main facebook.com page (not login)
            if 'facebook.com' in current_url and '/login' not in current_url:
                # Wait a bit more and check for any interactive element
                await asyncio.sleep(2)

                # Try to find any logged-in element
                page_content = await self.page.content()
                if 'composer' in page_content.lower() or 'feed' in page_content.lower():
                    logger.info("✅ Logged in based on page content")
                    return True

            logger.info("❌ Not logged in - no indicators found")
            return False

        except Exception as e:
            logger.error(f"Error checking login status: {e}")
            return False

    async def handle_checkpoint(self) -> bool:
        """
        Handle security checkpoint if triggered
        Returns True if handled, False if manual intervention needed
        """
        try:
            current_url = self.page.url

            if 'checkpoint' in current_url:
                logger.warning("Security checkpoint detected!")
                logger.warning("Manual verification may be required.")

                # Wait for user to handle checkpoint manually
                await asyncio.sleep(5)
                return False

            return True

        except Exception as e:
            logger.error(f"Checkpoint handling error: {e}")
            return False


async def login_to_facebook(page: Page, email: str, password: str) -> bool:
    """
    Convenience function for Facebook login

    Args:
        page: Playwright page object
        email: Facebook email/phone
        password: Facebook password

    Returns:
        True if successful
    """
    login_handler = FacebookLogin(page)
    return await login_handler.login(email, password)


async def login_and_go_to_pages(page: Page, email: str, password: str) -> bool:
    """
    Login and navigate to Pages section

    Args:
        page: Playwright page object
        email: Facebook email/phone
        password: Facebook password

    Returns:
        True if successful
    """
    login_handler = FacebookLogin(page)

    # First login
    if not await login_handler.login(email, password):
        return False

    # Then navigate to Pages
    return await login_handler.navigate_to_pages()
