"""
Chrome Browser Manager with undetected-chromedriver
- Max concurrent browsers limit
- Timeout protection
- Auto cleanup on crash
"""

import threading
import signal
import logging
import time
import random
from typing import Optional
from contextlib import contextmanager

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

logger = logging.getLogger(__name__)

# Configuration
MAX_CONCURRENT_BROWSERS = 2
WARMUP_TIMEOUT = 600  # 10 minutes max per warmup
PAGE_LOAD_TIMEOUT = 30


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


def get_chrome_options(headless: bool = True) -> uc.ChromeOptions:
    """
    Get Chrome options optimized for stability and stealth
    """
    options = uc.ChromeOptions()

    # === CRITICAL FOR SERVER/DOCKER ===
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")

    # === MEMORY MANAGEMENT ===
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-plugins")
    options.add_argument("--memory-pressure-off")
    options.add_argument("--max_old_space_size=512")

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

    return options


class BrowserManager:
    """
    Manages a single browser instance for warmup
    with timeout and cleanup
    """

    def __init__(self, headless: bool = True):
        self.driver: Optional[uc.Chrome] = None
        self.headless = headless
        self.start_time: Optional[float] = None

    def create_browser(self) -> uc.Chrome:
        """Create a new undetected Chrome browser"""
        options = get_chrome_options(self.headless)

        try:
            self.driver = uc.Chrome(
                options=options,
                use_subprocess=True,
                version_main=None  # Auto-detect Chrome version
            )
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
    import threading

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
