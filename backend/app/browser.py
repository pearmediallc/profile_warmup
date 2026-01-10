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
import subprocess
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

# Configuration - FOR 512MB RAM (Render free tier)
MAX_CONCURRENT_BROWSERS = 1  # Only 1 browser for 512MB RAM
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
    # Check environment variable first (Docker/Render)
    chrome_bin = os.environ.get('CHROME_BIN')
    if chrome_bin and os.path.exists(chrome_bin):
        logger.info(f"Using CHROME_BIN from environment: {chrome_bin}")
        return chrome_bin

    system = platform.system()
    if system == "Darwin":  # macOS
        mac_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        if os.path.exists(mac_path):
            return mac_path
    elif system == "Linux":
        # Check Chromium FIRST (Docker/Render uses Chromium which is lighter)
        linux_paths = [
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/google-chrome",
        ]
        for path in linux_paths:
            if os.path.exists(path):
                return path
    # Windows or not found - let Chrome auto-detect
    return None


def cleanup_chrome_processes():
    """Kill orphaned Chrome/chromedriver processes to free memory"""
    try:
        system = platform.system()
        if system == "Darwin":
            subprocess.run(["pkill", "-9", "-f", "Google Chrome"], capture_output=True)
            subprocess.run(["pkill", "-9", "-f", "chromedriver"], capture_output=True)
        elif system == "Linux":
            subprocess.run(["pkill", "-9", "-f", "chrome"], capture_output=True)
            subprocess.run(["pkill", "-9", "-f", "chromium"], capture_output=True)
            subprocess.run(["pkill", "-9", "-f", "chromedriver"], capture_output=True)
        elif system == "Windows":
            subprocess.run(["taskkill", "/F", "/IM", "chrome.exe"], capture_output=True)
            subprocess.run(["taskkill", "/F", "/IM", "chromedriver.exe"], capture_output=True)
        time.sleep(1)
        logger.info("Cleaned up orphaned Chrome processes")
    except Exception as e:
        logger.warning(f"Could not cleanup Chrome processes: {e}")


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
    Get Chrome options optimized for 512MB RAM (Render free tier)
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
    options.add_argument("--disable-features=NetworkService")
    options.add_argument("--disable-features=NetworkServiceInProcess")

    # === ADDITIONAL CONTAINER STABILITY ===
    options.add_argument("--disable-shared-memory-usage")

    # Set Chrome binary path (platform-aware)
    chrome_path = get_chrome_binary()
    if chrome_path:
        options.binary_location = chrome_path
        logger.info(f"Using Chrome at: {chrome_path}")

    # === MEMORY OPTIMIZATION (Basic) ===
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-plugins")
    options.add_argument("--disable-translate")
    options.add_argument("--disable-sync")
    options.add_argument("--disable-background-networking")
    options.add_argument("--disable-default-apps")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")

    # === AGGRESSIVE MEMORY SAVING FOR 512MB ===
    options.add_argument("--disable-features=IsolateOrigins,site-per-process")
    options.add_argument("--disable-site-isolation-trials")
    options.add_argument("--aggressive-cache-discard")
    options.add_argument("--disable-hang-monitor")
    options.add_argument("--disable-client-side-phishing-detection")
    options.add_argument("--disable-component-update")
    options.add_argument("--disable-domain-reliability")
    options.add_argument("--disable-features=AudioServiceOutOfProcess")
    options.add_argument("--disable-javascript-harmony-shipping")
    options.add_argument("--disable-renderer-accessibility")
    options.add_argument("--disable-speech-api")
    options.add_argument("--disable-webgl")
    options.add_argument("--disable-webgl2")
    options.add_argument("--disable-accelerated-2d-canvas")
    options.add_argument("--disable-accelerated-video-decode")
    options.add_argument("--js-flags=--max-old-space-size=256")
    options.add_argument("--renderer-process-limit=1")
    options.add_argument("--single-process")  # Re-enabled for 512MB RAM
    options.add_argument("--memory-pressure-off")

    # === STABILITY ===
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-backgrounding-occluded-windows")
    options.add_argument("--disable-renderer-backgrounding")
    options.add_argument("--disable-features=TranslateUI")
    options.add_argument("--disable-ipc-flooding-protection")

    # === CRASH PREVENTION ===
    options.add_argument("--disable-crash-reporter")
    options.add_argument("--disable-breakpad")
    options.add_argument("--crash-dumps-dir=/tmp")

    # === WINDOW SIZE (Smaller = Less Memory) ===
    options.add_argument("--window-size=1280,720")

    # === RANDOM DEBUG PORT (Avoid conflicts) ===
    debug_port = random.randint(9222, 9999)
    options.add_argument(f"--remote-debugging-port={debug_port}")

    # === STEALTH ===
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-infobars")

    # User agent to look more human
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    # === EXPERIMENTAL OPTIONS ===
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    prefs = {
        "profile.default_content_setting_values.notifications": 2,
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False,
    }
    options.add_experimental_option("prefs", prefs)

    return options


def create_driver(headless: bool = True, max_retries: int = 3):
    """
    Create a Chrome WebDriver with retry logic
    - Local machines (Mac/Windows/Linux): Uses undetected-chromedriver for stealth
    - Docker/Server: Uses regular Selenium with webdriver-manager
    - Includes cleanup of orphaned processes and retry on failure
    """
    # Cleanup orphaned Chrome processes before starting
    cleanup_chrome_processes()

    last_error = None

    for attempt in range(max_retries):
        try:
            logger.info(f"Starting Chrome (attempt {attempt + 1}/{max_retries})...")

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
                    uc_options.add_argument("--window-size=1280,720")

                    # Set Chrome path if found
                    chrome_path = get_chrome_binary()
                    if chrome_path:
                        uc_options.binary_location = chrome_path

                    driver = uc.Chrome(options=uc_options, use_subprocess=True)

                    # Remove webdriver flag
                    driver.execute_script(
                        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
                    )

                    logger.info("Browser created with undetected-chromedriver (stealth mode)")
                    return driver

                except Exception as e:
                    logger.warning(f"undetected-chromedriver failed: {e}, falling back to regular Selenium")

            # Strategy 2: Use system chromedriver directly (for Docker)
            options = get_chrome_options(headless)

            # Check for system chromedriver (both paths)
            system_chromedrivers = ["/usr/local/bin/chromedriver", "/usr/bin/chromedriver"]
            for system_chromedriver in system_chromedrivers:
                if os.path.exists(system_chromedriver):
                    try:
                        logger.info(f"Attempting system chromedriver at {system_chromedriver}...")
                        from selenium.webdriver.chrome.service import Service as ChromeService
                        service = ChromeService(executable_path=system_chromedriver)
                        driver = webdriver.Chrome(service=service, options=options)

                        # Remove webdriver flag
                        driver.execute_script(
                            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
                        )

                        logger.info("Browser created with system chromedriver")
                        return driver
                    except Exception as e:
                        logger.warning(f"System chromedriver at {system_chromedriver} failed: {e}")

            # Strategy 3: Try webdriver-manager (for local development)
            try:
                from webdriver_manager.chrome import ChromeDriverManager
                from selenium.webdriver.chrome.service import Service as ChromeService

                logger.info("Attempting webdriver-manager...")
                driver_path = ChromeDriverManager().install()

                # Fix: webdriver-manager sometimes returns wrong path (e.g., THIRD_PARTY_NOTICES)
                # Ensure we get the actual chromedriver binary
                if driver_path and not driver_path.endswith('chromedriver'):
                    driver_dir = os.path.dirname(driver_path)
                    # Look for the actual chromedriver binary
                    for name in ['chromedriver', 'chromedriver.exe']:
                        potential_path = os.path.join(driver_dir, name)
                        if os.path.exists(potential_path) and os.access(potential_path, os.X_OK):
                            driver_path = potential_path
                            break
                    else:
                        # Check parent directory
                        parent_dir = os.path.dirname(driver_dir)
                        for name in ['chromedriver', 'chromedriver.exe']:
                            potential_path = os.path.join(parent_dir, name)
                            if os.path.exists(potential_path) and os.access(potential_path, os.X_OK):
                                driver_path = potential_path
                                break

                logger.info(f"Using chromedriver at: {driver_path}")
                service = ChromeService(executable_path=driver_path)
                driver = webdriver.Chrome(service=service, options=options)

                # Remove webdriver flag
                driver.execute_script(
                    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
                )

                logger.info("Browser created with webdriver-manager")
                return driver

            except Exception as e:
                logger.warning(f"webdriver-manager failed: {e}, trying direct Chrome")

                # Strategy 4: Try direct Chrome without specifying chromedriver path
                driver = webdriver.Chrome(options=options)

                # Remove webdriver flag
                driver.execute_script(
                    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
                )

                logger.info("Browser created with auto-detected chromedriver")
                return driver

        except (WebDriverException, Exception) as e:
            last_error = e
            logger.warning(f"Chrome start attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                logger.info(f"Waiting 2 seconds before retry...")
                time.sleep(2)
                cleanup_chrome_processes()

    # All retries exhausted
    logger.error(f"All browser creation methods failed after {max_retries} attempts!")
    logger.error(f"  - undetected-chromedriver: {'not available' if not UC_AVAILABLE else 'failed'}")
    logger.error(f"  - system chromedriver: not found or failed")
    logger.error(f"  - webdriver-manager: failed")
    logger.error(f"  - auto-detect: failed")
    logger.error(f"  - Last error: {last_error}")
    raise Exception(f"Could not create browser after {max_retries} attempts. Error: {last_error}")


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
