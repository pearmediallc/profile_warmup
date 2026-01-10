"""
Chrome Browser Manager
- Uses undetected-chromedriver for local machines (Mac/Windows/Linux laptops)
- Falls back to regular Selenium for Docker/server environments
- Max concurrent browsers limit
- Timeout protection
- Auto cleanup on crash
"""

import threading
import signal
import logging
import time
import random
import platform
import os
from typing import Optional
from contextlib import contextmanager

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

logger = logging.getLogger(__name__)

# Configuration - FOR 2GB RAM
MAX_CONCURRENT_BROWSERS = 2  # Can run 2 browsers with 2GB RAM
WARMUP_TIMEOUT = 600  # 10 minutes max per warmup
PAGE_LOAD_TIMEOUT = 60  # Increased for slow networks

# Detect if running in Docker/container/server
IS_DOCKER = os.path.exists('/.dockerenv') or os.environ.get('RENDER', False) or os.environ.get('DOCKER', False)

# Try to import undetected_chromedriver (for local machines)
try:
    import undetected_chromedriver as uc
    UC_AVAILABLE = True
    logger.info("undetected-chromedriver available")
except ImportError:
    UC_AVAILABLE = False
    logger.info("undetected-chromedriver not available, will use regular Selenium")


def get_chrome_binary():
    """Get Chrome binary path based on platform"""
    system = platform.system()
    if system == "Darwin":  # macOS
        mac_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        if os.path.exists(mac_path):
            return mac_path
    elif system == "Linux":
        linux_paths = [
            "/usr/bin/google-chrome-stable",
            "/usr/bin/google-chrome",
            "/usr/bin/chromium-browser",
            "/usr/bin/chromium"
        ]
        for path in linux_paths:
            if os.path.exists(path):
                return path
    # Windows or not found - let Chrome auto-detect
    return None


class BrowserPool:
    """Manages browser instances with concurrency limits"""

    def __init__(self, max_browsers: int = MAX_CONCURRENT_BROWSERS):
        self.semaphore = threading.Semaphore(max_browsers)
        self.active_browsers = []
        self.lock = threading.Lock()

    def acquire(self) -> bool:
        """Try to acquire a browser slot"""
        return self.semaphore.acquire(blocking=True, timeout=60)

    def release(self):
        """Release a browser slot"""
        self.semaphore.release()

    def register_browser(self, driver):
        """Track active browser"""
        with self.lock:
            self.active_browsers.append(driver)

    def unregister_browser(self, driver):
        """Remove browser from tracking"""
        with self.lock:
            if driver in self.active_browsers:
                self.active_browsers.remove(driver)

    def cleanup_all(self):
        """Force cleanup all browsers"""
        with self.lock:
            for driver in self.active_browsers[:]:
                try:
                    driver.quit()
                except Exception:
                    pass
            self.active_browsers.clear()


# Global browser pool
browser_pool = BrowserPool()


def get_chrome_options(headless: bool = True) -> Options:
    """
    Get Chrome options optimized for 2GB RAM
    Works in both local and Docker environments
    """
    options = Options()

    # === CRITICAL FOR SERVER/DOCKER ===
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")

    # === DOCKER/RENDER SPECIFIC ===
    options.add_argument("--disable-setuid-sandbox")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--disable-features=VizDisplayCompositor")
    options.add_argument("--remote-debugging-port=9222")
    options.add_argument("--single-process")  # Required for some Docker environments
    options.add_argument("--disable-features=NetworkService")
    options.add_argument("--disable-features=NetworkServiceInProcess")

    # Set Chrome binary path (platform-aware)
    chrome_path = get_chrome_binary()
    if chrome_path:
        options.binary_location = chrome_path
        logger.info(f"Using Chrome at: {chrome_path}")

    # === MEMORY OPTIMIZATION ===
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-plugins")
    options.add_argument("--disable-translate")
    options.add_argument("--disable-sync")
    options.add_argument("--disable-background-networking")
    options.add_argument("--disable-default-apps")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")

    # === STABILITY ===
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-backgrounding-occluded-windows")
    options.add_argument("--disable-renderer-backgrounding")
    options.add_argument("--disable-features=TranslateUI")
    options.add_argument("--disable-ipc-flooding-protection")

    # === CRASH PREVENTION ===
    options.add_argument("--disable-crash-reporter")
    options.add_argument("--disable-breakpad")

    # === WINDOW SIZE ===
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--start-maximized")

    # === STEALTH ===
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-infobars")

    # User agent to look more human
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    return options


def create_driver(headless: bool = True):
    """
    Create a Chrome WebDriver
    - Local machines (Mac/Windows/Linux): Uses undetected-chromedriver for stealth
    - Docker/Server: Uses regular Selenium with webdriver-manager
    """

    # Strategy 1: Use undetected-chromedriver for local machines (better stealth)
    if UC_AVAILABLE and not IS_DOCKER:
        try:
            logger.info("Attempting undetected-chromedriver (local machine)...")
            uc_options = uc.ChromeOptions()

            if headless:
                uc_options.add_argument("--headless=new")

            # Memory optimization
            uc_options.add_argument("--disable-extensions")
            uc_options.add_argument("--disable-plugins")
            uc_options.add_argument("--disable-dev-shm-usage")
            uc_options.add_argument("--no-sandbox")
            uc_options.add_argument("--window-size=1920,1080")

            # Set Chrome path if found
            chrome_path = get_chrome_binary()
            if chrome_path:
                uc_options.binary_location = chrome_path

            driver = uc.Chrome(options=uc_options, use_subprocess=True)
            logger.info("Browser created with undetected-chromedriver (stealth mode)")
            return driver

        except Exception as e:
            logger.warning(f"undetected-chromedriver failed: {e}, falling back to regular Selenium")

    # Strategy 2: Use system chromedriver directly (for Docker)
    options = get_chrome_options(headless)

    # Check for system chromedriver first (installed in Docker)
    system_chromedriver = "/usr/local/bin/chromedriver"
    if os.path.exists(system_chromedriver):
        try:
            logger.info(f"Attempting system chromedriver at {system_chromedriver}...")
            from selenium.webdriver.chrome.service import Service as ChromeService
            service = ChromeService(executable_path=system_chromedriver)
            driver = webdriver.Chrome(service=service, options=options)
            logger.info("Browser created with system chromedriver")
            return driver
        except Exception as e:
            logger.warning(f"System chromedriver failed: {e}")

    # Strategy 3: Try webdriver-manager (for local development)
    try:
        from webdriver_manager.chrome import ChromeDriverManager
        from selenium.webdriver.chrome.service import Service as ChromeService

        logger.info("Attempting webdriver-manager...")
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)

        logger.info("Browser created with webdriver-manager")
        return driver

    except Exception as e:
        logger.warning(f"webdriver-manager failed: {e}, trying direct Chrome")

        # Strategy 4: Try direct Chrome without specifying chromedriver path
        try:
            driver = webdriver.Chrome(options=options)
            logger.info("Browser created with auto-detected chromedriver")
            return driver
        except Exception as e2:
            logger.error(f"All browser creation methods failed!")
            logger.error(f"  - undetected-chromedriver: {'not available' if not UC_AVAILABLE else 'failed'}")
            logger.error(f"  - system chromedriver: not found or failed")
            logger.error(f"  - webdriver-manager: {e}")
            logger.error(f"  - auto-detect: {e2}")
            raise Exception(f"Could not create browser. Make sure Chrome is installed. Error: {e2}")


class BrowserManager:
    """
    Manages a single browser instance for warmup
    with timeout and cleanup
    """

    def __init__(self, headless: bool = True):
        self.driver = None
        self.headless = headless
        self.start_time: Optional[float] = None

    def create_browser(self):
        """Create a new Chrome browser"""
        try:
            self.driver = create_driver(self.headless)
            self.driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
            self.driver.implicitly_wait(10)
            self.start_time = time.time()

            browser_pool.register_browser(self.driver)
            logger.info("Browser created successfully")
            return self.driver

        except Exception as e:
            logger.error(f"Failed to create browser: {e}")
            raise

    def quit(self):
        """Safely close the browser"""
        if self.driver:
            try:
                browser_pool.unregister_browser(self.driver)
                self.driver.quit()
                logger.info("Browser closed successfully")
            except Exception as e:
                logger.error(f"Error closing browser: {e}")
            finally:
                self.driver = None

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


@contextmanager
def browser_session(headless: bool = True):
    """
    Context manager for browser sessions
    Ensures proper cleanup even on errors

    Usage:
        with browser_session() as driver:
            driver.get("https://facebook.com")
            # do stuff
    """
    if not browser_pool.acquire():
        raise Exception("Could not acquire browser slot (max concurrent reached)")

    manager = BrowserManager(headless=headless)
    try:
        driver = manager.create_browser()
        yield driver
    except Exception as e:
        logger.error(f"Browser session error: {e}")
        raise
    finally:
        manager.quit()
        browser_pool.release()


def run_with_timeout(func, timeout: int = WARMUP_TIMEOUT):
    """
    Run a function with timeout
    Raises TimeoutError if exceeded
    """
    result = [None]
    error = [None]

    def target():
        try:
            result[0] = func()
        except Exception as e:
            error[0] = e

    thread = threading.Thread(target=target)
    thread.start()
    thread.join(timeout)

    if thread.is_alive():
        raise TimeoutError(f"Operation exceeded {timeout}s timeout")

    if error[0]:
        raise error[0]

    return result[0]


# Human-like actions for Selenium
def human_delay(min_sec: float = 0.5, max_sec: float = 2.0):
    """Random human-like delay"""
    time.sleep(random.uniform(min_sec, max_sec))


def human_type(element, text: str):
    """Type text with human-like speed"""
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(0.05, 0.15))
        if random.random() < 0.1:
            time.sleep(random.uniform(0.2, 0.5))


def scroll_page(driver, pixels: int = 500):
    """Scroll page with human-like behavior"""
    driver.execute_script(f"window.scrollBy(0, {pixels});")
    human_delay(1, 3)
