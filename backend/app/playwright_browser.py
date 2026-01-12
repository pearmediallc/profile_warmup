"""
Playwright Browser Manager for Profile Warmup
- Lower memory than Selenium
- Built-in human-like behavior
- Better stealth (harder to detect as bot)
- Works on Mac, Linux, Docker, Cloud
WITH COMPREHENSIVE LOGGING
"""

import logging
import sys
import time
import random
import platform
import os
import subprocess
from typing import Optional, Dict, Any
from contextlib import contextmanager

print("[PLAYWRIGHT] Loading playwright_browser module...", flush=True)

# Playwright imports
try:
    from playwright.sync_api import sync_playwright, Page, Browser, Playwright
    print("[PLAYWRIGHT] ✓ Playwright imports successful", flush=True)
except Exception as e:
    print(f"[PLAYWRIGHT] ✗ Failed to import Playwright: {e}", flush=True)
    raise

logger = logging.getLogger(__name__)

# Configuration
MAX_CONCURRENT_BROWSERS = 1  # Only 1 browser for 512MB RAM
WARMUP_TIMEOUT = 600  # 10 minutes max
PAGE_LOAD_TIMEOUT = 60000  # 60 seconds in milliseconds

# Detect environment
IS_DOCKER = os.path.exists('/.dockerenv') or os.environ.get('RENDER', False) or os.environ.get('DOCKER', False)


def find_chrome_executable() -> Optional[str]:
    """
    Find the Chrome executable path explicitly.
    This ensures we find the browser regardless of PLAYWRIGHT_BROWSERS_PATH env var.
    """
    # Search paths in order of preference
    search_paths = [
        os.environ.get('PLAYWRIGHT_BROWSERS_PATH', '/ms-playwright'),
        '/ms-playwright',
        '/root/.cache/ms-playwright',
        '/home/.cache/ms-playwright',
    ]

    for base_path in search_paths:
        if not os.path.exists(base_path):
            continue

        try:
            # Find chrome executable
            result = subprocess.run(
                ['find', base_path, '-name', 'chrome', '-type', 'f'],
                capture_output=True, text=True, timeout=30
            )
            if result.stdout:
                paths = result.stdout.strip().split('\n')
                for path in paths:
                    if path and os.path.isfile(path) and os.access(path, os.X_OK):
                        print(f"[BROWSER] Found executable Chrome at: {path}", flush=True)
                        return path
        except Exception as e:
            print(f"[BROWSER] Error searching {base_path}: {e}", flush=True)

    print("[BROWSER] ✗ Could not find Chrome executable!", flush=True)
    return None


def cleanup_browser_processes():
    """Kill orphaned browser processes to free memory"""
    try:
        system = platform.system()
        if system == "Darwin":  # macOS
            subprocess.run(["pkill", "-9", "-f", "Chromium"], capture_output=True)
            subprocess.run(["pkill", "-9", "-f", "Google Chrome"], capture_output=True)
        elif system == "Linux":
            subprocess.run(["pkill", "-9", "-f", "chromium"], capture_output=True)
            subprocess.run(["pkill", "-9", "-f", "chrome"], capture_output=True)
        elif system == "Windows":
            subprocess.run(["taskkill", "/F", "/IM", "chromium.exe"], capture_output=True)
            subprocess.run(["taskkill", "/F", "/IM", "chrome.exe"], capture_output=True)
        time.sleep(1)
        logger.info("Cleaned up orphaned browser processes")
    except Exception as e:
        logger.warning(f"Could not cleanup browser processes: {e}")


def get_browser_args():
    """Get browser launch arguments optimized for low memory (512MB)"""
    args = [
        '--no-sandbox',
        '--disable-dev-shm-usage',
        '--disable-gpu',
        '--disable-extensions',
        '--disable-plugins',
        '--disable-translate',
        '--disable-sync',
        '--disable-background-networking',
        '--disable-default-apps',
        '--no-first-run',
        '--no-default-browser-check',
        # Aggressive memory saving for 512MB
        '--disable-features=IsolateOrigins,site-per-process',
        '--disable-site-isolation-trials',
        '--aggressive-cache-discard',
        '--disable-hang-monitor',
        '--disable-client-side-phishing-detection',
        '--disable-component-update',
        '--disable-domain-reliability',
        '--disable-features=AudioServiceOutOfProcess',
        '--disable-renderer-accessibility',
        '--disable-speech-api',
        '--disable-webgl',
        '--disable-webgl2',
        '--js-flags=--max-old-space-size=256',
        '--renderer-process-limit=1',
        '--memory-pressure-off',
        # Container stability
        '--disable-setuid-sandbox',
        '--disable-software-rasterizer',
        '--disable-features=VizDisplayCompositor',
        # Crash prevention
        '--disable-crash-reporter',
        '--disable-breakpad',
    ]

    # NOTE: Removed --single-process flag - causes instability and crashes
    # Even in Docker, it's better to let Chromium manage its processes

    return args


class PlaywrightBrowser:
    """
    Playwright-based browser with human-like behavior
    Drop-in replacement for Selenium browser
    """

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.start_time: Optional[float] = None

    def start(self, max_retries: int = 3):
        """Start the browser with retry logic"""
        print("[BROWSER] ========================================", flush=True)
        print("[BROWSER] Starting browser...", flush=True)
        print(f"[BROWSER] Headless mode: {self.headless}", flush=True)
        print(f"[BROWSER] Platform: {platform.system()}", flush=True)
        print(f"[BROWSER] IS_DOCKER: {IS_DOCKER}", flush=True)
        print("[BROWSER] ========================================", flush=True)

        cleanup_browser_processes()

        # Debug: Log browser path info
        print("[BROWSER] Checking Playwright installation...", flush=True)
        try:
            result = subprocess.run(['playwright', '--version'],
                                   capture_output=True, text=True, timeout=10)
            print(f"[BROWSER] Playwright version: {result.stdout.strip() if result.stdout else result.stderr.strip()}", flush=True)
        except Exception as e:
            print(f"[BROWSER] ✗ Could not get Playwright version: {e}", flush=True)

        # Check for chromium in correct location
        print("[BROWSER] Searching for Chromium...", flush=True)
        # Check PLAYWRIGHT_BROWSERS_PATH env var first, then default locations
        browser_path = os.environ.get('PLAYWRIGHT_BROWSERS_PATH', '/ms-playwright')
        search_paths = [browser_path, '/ms-playwright', '/root/.cache/ms-playwright']

        for search_path in search_paths:
            try:
                if not os.path.exists(search_path):
                    print(f"[BROWSER] Path {search_path} does not exist, skipping...", flush=True)
                    continue

                print(f"[BROWSER] Checking {search_path}...", flush=True)
                find_result = subprocess.run(['find', search_path, '-name', 'chrome', '-type', 'f'],
                                            capture_output=True, text=True, timeout=30)
                if find_result.stdout:
                    print(f"[BROWSER] ✓ Found Chromium at: {find_result.stdout.strip()[:200]}", flush=True)
                    break
                else:
                    print(f"[BROWSER] Chromium NOT found in {search_path}", flush=True)
            except Exception as e:
                print(f"[BROWSER] Could not search {search_path}: {e}", flush=True)
        else:
            print("[BROWSER] ✗ Chromium NOT found in any expected location!", flush=True)

        last_error = None

        for attempt in range(max_retries):
            try:
                print(f"[BROWSER] Starting Playwright browser (attempt {attempt + 1}/{max_retries})...", flush=True)
                logger.info(f"Starting Playwright browser (attempt {attempt + 1}/{max_retries})...")

                print("[BROWSER] Calling sync_playwright().start()...", flush=True)
                self.playwright = sync_playwright().start()
                print("[BROWSER] ✓ Playwright started", flush=True)
                self.start_time = time.time()

                # Find Chrome executable explicitly
                chrome_path = find_chrome_executable()

                # Launch browser with explicit path if found
                print("[BROWSER] Launching Chromium...", flush=True)
                launch_options = {
                    'headless': self.headless,
                    'args': get_browser_args(),
                }

                # Use explicit executable path if we found one
                if chrome_path:
                    print(f"[BROWSER] Using explicit executable_path: {chrome_path}", flush=True)
                    launch_options['executable_path'] = chrome_path
                else:
                    print("[BROWSER] No explicit path, using Playwright default...", flush=True)

                self.browser = self.playwright.chromium.launch(**launch_options)
                print("[BROWSER] ✓ Chromium launched successfully!", flush=True)

                # Create page with realistic settings
                print("[BROWSER] Creating new page...", flush=True)
                self.page = self.browser.new_page(
                    viewport={'width': 1280, 'height': 720},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    locale='en-US',
                    timezone_id='America/New_York',
                )

                # Set timeouts
                self.page.set_default_timeout(PAGE_LOAD_TIMEOUT)
                self.page.set_default_navigation_timeout(PAGE_LOAD_TIMEOUT)

                # Add stealth script to hide automation
                self.page.add_init_script("""
                    // Hide webdriver flag
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});

                    // Mock plugins (real browsers have plugins)
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5]
                    });

                    // Mock languages
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['en-US', 'en']
                    });
                """)

                print("[BROWSER] ✓ Page created successfully!", flush=True)
                print("[BROWSER] ========================================", flush=True)
                print("[BROWSER] BROWSER READY TO USE", flush=True)
                print("[BROWSER] ========================================", flush=True)
                logger.info("Playwright browser started successfully")
                return self.page

            except Exception as e:
                last_error = e
                print(f"[BROWSER] ✗ Attempt {attempt + 1} FAILED: {e}", flush=True)
                logger.warning(f"Browser start attempt {attempt + 1} failed: {e}")

                # Cleanup before retry
                self.stop()

                if attempt < max_retries - 1:
                    time.sleep(2)
                    cleanup_browser_processes()

        raise Exception(f"Could not start browser after {max_retries} attempts. Error: {last_error}")

    def stop(self):
        """Stop browser and cleanup"""
        try:
            if self.page:
                self.page.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
            logger.info("Browser stopped")
        except Exception as e:
            logger.error(f"Error stopping browser: {e}")
        finally:
            self.page = None
            self.browser = None
            self.playwright = None

    # ==================== NAVIGATION ====================

    def get(self, url: str):
        """Navigate to URL (same as Selenium driver.get())"""
        self.page.goto(url, wait_until='domcontentloaded')
        self.human_delay(1, 2)

    def goto(self, url: str):
        """Alias for get()"""
        self.get(url)

    @property
    def current_url(self) -> str:
        """Get current URL (same as Selenium driver.current_url)"""
        return self.page.url

    @property
    def page_source(self) -> str:
        """Get page HTML (same as Selenium driver.page_source)"""
        return self.page.content()

    # ==================== HUMAN-LIKE DELAYS ====================

    def human_delay(self, min_sec: float = 0.5, max_sec: float = 2.0):
        """Wait random time (like human thinking)"""
        delay = random.uniform(min_sec, max_sec)
        time.sleep(delay)

    def _typing_delay(self) -> int:
        """Random delay between keystrokes (milliseconds)"""
        return random.randint(50, 150)

    def _click_delay(self) -> int:
        """Random delay before click (milliseconds)"""
        return random.randint(30, 100)

    # ==================== FIND ELEMENTS ====================

    def find_element(self, by: str, value: str):
        """Find element (Selenium-compatible interface)"""
        selector = self._convert_selector(by, value)
        return PlaywrightElement(self.page, selector, self)

    def find_elements(self, by: str, value: str):
        """Find multiple elements (Selenium-compatible interface)"""
        selector = self._convert_selector(by, value)
        locator = self.page.locator(selector)
        count = locator.count()
        return [PlaywrightElement(self.page, selector, self, index=i) for i in range(count)]

    def _convert_selector(self, by: str, value: str) -> str:
        """Convert Selenium By.XXX to Playwright selector"""
        # Handle common Selenium selectors
        if by == "xpath" or by == "XPATH":
            return f"xpath={value}"
        elif by == "css selector" or by == "CSS_SELECTOR":
            return value
        elif by == "id" or by == "ID":
            return f"#{value}"
        elif by == "name" or by == "NAME":
            return f"[name='{value}']"
        elif by == "class name" or by == "CLASS_NAME":
            return f".{value}"
        elif by == "tag name" or by == "TAG_NAME":
            return value
        elif by == "link text" or by == "LINK_TEXT":
            return f"text={value}"
        elif by == "partial link text" or by == "PARTIAL_LINK_TEXT":
            return f"text={value}"
        else:
            # Assume it's already a valid selector
            return value

    # ==================== HUMAN-LIKE ACTIONS ====================

    def human_type(self, selector: str, text: str):
        """Type text with human-like delays"""
        element = self.page.locator(selector)
        element.click(delay=self._click_delay())
        self.human_delay(0.2, 0.5)

        # Clear existing text
        element.fill('')

        # Type with random delays between characters
        for char in text:
            element.type(char, delay=self._typing_delay())

            # 10% chance of longer pause (simulates thinking)
            if random.random() < 0.1:
                self.human_delay(0.3, 0.8)

    def human_click(self, selector: str):
        """Click with human-like behavior"""
        self.human_delay(0.1, 0.3)
        self.page.locator(selector).click(delay=self._click_delay())
        self.human_delay(0.5, 1.5)

    def human_scroll(self, pixels: int = 500):
        """Scroll with human-like behavior"""
        # Add randomness to scroll amount
        actual_pixels = pixels + random.randint(-50, 50)

        # Scroll in small steps (more human-like)
        steps = random.randint(2, 4)
        step_size = actual_pixels // steps

        for _ in range(steps):
            self.page.evaluate(f"window.scrollBy(0, {step_size})")
            self.human_delay(0.1, 0.3)

        self.human_delay(0.5, 1.5)

    def scroll_down(self, pixels: int = 500):
        """Scroll down (alias)"""
        self.human_scroll(pixels)

    def scroll_up(self, pixels: int = 500):
        """Scroll up"""
        self.human_scroll(-pixels)

    # ==================== SCREENSHOTS ====================

    def screenshot(self, path: str):
        """Take screenshot and save to file"""
        self.page.screenshot(path=path)

    def get_screenshot_as_base64(self) -> str:
        """Take screenshot and return as base64 string"""
        import base64
        screenshot_bytes = self.page.screenshot()
        return base64.b64encode(screenshot_bytes).decode('utf-8')

    def save_screenshot(self, path: str) -> bool:
        """Save screenshot (Selenium-compatible)"""
        try:
            self.screenshot(path)
            return True
        except Exception:
            return False

    # ==================== JAVASCRIPT ====================

    def execute_script(self, script: str, *args):
        """Execute JavaScript (Selenium-compatible)"""
        return self.page.evaluate(script)

    # ==================== UTILITY ====================

    def is_timeout(self) -> bool:
        """Check if warmup has exceeded timeout"""
        if self.start_time is None:
            return False
        return (time.time() - self.start_time) > WARMUP_TIMEOUT

    def get_elapsed_time(self) -> float:
        """Get elapsed time in seconds"""
        if self.start_time is None:
            return 0
        return time.time() - self.start_time

    def quit(self):
        """Close browser (Selenium-compatible)"""
        self.stop()


class PlaywrightElement:
    """
    Wrapper to make Playwright element work like Selenium WebElement
    """

    def __init__(self, page: Page, selector: str, browser: PlaywrightBrowser, index: int = 0):
        self.page = page
        self.selector = selector
        self.browser = browser
        self.index = index

    def _get_locator(self):
        """Get the actual Playwright locator"""
        locator = self.page.locator(self.selector)
        if self.index > 0:
            return locator.nth(self.index)
        return locator.first

    def click(self):
        """Click element with human-like delay"""
        self.browser.human_delay(0.1, 0.3)
        self._get_locator().click(delay=self.browser._click_delay())
        self.browser.human_delay(0.3, 0.8)

    def send_keys(self, text: str):
        """Type text with human-like delays"""
        locator = self._get_locator()

        # Type character by character
        for char in text:
            locator.type(char, delay=self.browser._typing_delay())

            # 10% chance of pause
            if random.random() < 0.1:
                self.browser.human_delay(0.2, 0.5)

    def clear(self):
        """Clear element text"""
        self._get_locator().fill('')

    def get_attribute(self, name: str) -> Optional[str]:
        """Get element attribute"""
        return self._get_locator().get_attribute(name)

    @property
    def text(self) -> str:
        """Get element text"""
        return self._get_locator().text_content() or ''

    def is_displayed(self) -> bool:
        """Check if element is visible"""
        try:
            return self._get_locator().is_visible()
        except Exception:
            return False

    def is_enabled(self) -> bool:
        """Check if element is enabled"""
        try:
            return self._get_locator().is_enabled()
        except Exception:
            return False


class BrowserPool:
    """Manages browser instances (same interface as Selenium version)"""

    def __init__(self, max_browsers: int = MAX_CONCURRENT_BROWSERS):
        self.active_browsers = []
        self.max_browsers = max_browsers

    def register_browser(self, browser: PlaywrightBrowser):
        """Track active browser"""
        self.active_browsers.append(browser)

    def unregister_browser(self, browser: PlaywrightBrowser):
        """Remove browser from tracking"""
        if browser in self.active_browsers:
            self.active_browsers.remove(browser)

    def cleanup_all(self):
        """Force cleanup all browsers"""
        for browser in self.active_browsers[:]:
            try:
                browser.stop()
            except Exception:
                pass
        self.active_browsers.clear()
        cleanup_browser_processes()


# Global browser pool
browser_pool = BrowserPool()


@contextmanager
def browser_session(headless: bool = True):
    """
    Context manager for browser sessions
    Same interface as Selenium version

    Usage:
        with browser_session() as driver:
            driver.get("https://facebook.com")
            driver.human_type("#email", "user@example.com")
    """
    browser = PlaywrightBrowser(headless=headless)
    try:
        browser.start()
        browser_pool.register_browser(browser)
        yield browser
    except Exception as e:
        logger.error(f"Browser session error: {e}")
        raise
    finally:
        browser_pool.unregister_browser(browser)
        browser.stop()


# ==================== HELPER FUNCTIONS (Same as Selenium version) ====================

def human_delay(min_sec: float = 0.5, max_sec: float = 2.0):
    """Random human-like delay"""
    time.sleep(random.uniform(min_sec, max_sec))


def human_type(element: PlaywrightElement, text: str):
    """Type text with human-like speed"""
    element.send_keys(text)


def scroll_page(driver: PlaywrightBrowser, pixels: int = 500):
    """Scroll page with human-like behavior"""
    driver.human_scroll(pixels)
