"""
Warmup tasks for Facebook profile warming
Using Playwright for better memory efficiency (512MB RAM compatible)
"""

import logging
import time
import random
import os
import base64
import json
from datetime import datetime
from typing import Dict, Any, Optional

import redis
import cloudinary
import cloudinary.uploader

# Use Playwright browser (lighter than Selenium)
from app.playwright_browser import browser_session, browser_pool, human_delay, scroll_page

logger = logging.getLogger(__name__)

# Configure Cloudinary
CLOUDINARY_CONFIGURED = False
if os.getenv("CLOUDINARY_CLOUD_NAME"):
    cloudinary.config(
        cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
        api_key=os.getenv("CLOUDINARY_API_KEY"),
        api_secret=os.getenv("CLOUDINARY_API_SECRET"),
        secure=True
    )
    CLOUDINARY_CONFIGURED = True
    logger.info("Cloudinary configured")

# Redis for status broadcasting
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
try:
    redis_client = redis.from_url(REDIS_URL)
    redis_client.ping()
except Exception:
    redis_client = None

# Callback functions for direct status updates (when Redis not available)
_status_callbacks: Dict[str, Any] = {}


def set_status_callback(email: str, callback):
    """Set a callback function for status updates (used when Redis not available)"""
    if callback is None:
        _status_callbacks.pop(email, None)
    else:
        _status_callbacks[email] = callback


def broadcast_status(email: str, status: str, message: str, **extra):
    """Broadcast status update via Redis pub/sub or direct callback"""
    data = {
        "type": "status",
        "profile": email,
        "status": status,
        "message": message,
        "timestamp": datetime.utcnow().isoformat(),
        **extra
    }

    # Try Redis first
    if redis_client:
        try:
            redis_client.publish("warmup_status", json.dumps(data))
            logger.debug(f"Broadcast via Redis: {status} - {message}")
            return
        except Exception as e:
            logger.error(f"Redis broadcast error: {e}")

    # Fallback to direct callback if registered
    if email in _status_callbacks and _status_callbacks[email]:
        try:
            _status_callbacks[email](data)
            logger.debug(f"Broadcast via callback: {status} - {message}")
        except Exception as e:
            logger.error(f"Callback broadcast error: {e}")

# Screenshots directory
SCREENSHOTS_DIR = os.getenv("SCREENSHOTS_DIR", "/tmp/warmup_screenshots")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)


def take_screenshot(driver, name: str, email: str) -> Optional[Dict[str, str]]:
    """
    Take a screenshot, save locally and upload to Cloudinary
    Returns dict with local path and cloudinary URL, or None on failure
    """
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_email = email.split('@')[0].replace('.', '_')
        filename = f"{safe_email}_{name}_{timestamp}.png"
        filepath = os.path.join(SCREENSHOTS_DIR, filename)

        driver.save_screenshot(filepath)
        logger.info(f"Screenshot saved: {filepath}")

        result = {
            "local_path": filepath,
            "filename": filename,
            "url": None
        }

        # Upload to Cloudinary if configured
        if CLOUDINARY_CONFIGURED:
            try:
                public_id = f"warmup_screenshots/{safe_email}/{name}_{timestamp}"
                upload_result = cloudinary.uploader.upload(
                    filepath,
                    public_id=public_id,
                    folder="warmup_screenshots",
                    overwrite=True,
                    resource_type="image"
                )
                result["url"] = upload_result.get("secure_url")
                logger.info(f"Screenshot uploaded to Cloudinary: {result['url']}")
            except Exception as e:
                logger.error(f"Cloudinary upload failed: {e}")

        return result
    except Exception as e:
        logger.error(f"Failed to take screenshot: {e}")
        return None


def screenshot_to_base64(filepath: str) -> Optional[str]:
    """Convert screenshot to base64 for sending via WebSocket"""
    try:
        with open(filepath, "rb") as f:
            return base64.b64encode(f.read()).decode('utf-8')
    except Exception as e:
        logger.error(f"Failed to encode screenshot: {e}")
        return None

# Import config (from backend/config.py)
from config import WARM_UP_CONFIG
from config.selectors import LOGIN_SELECTORS, LIKE_SELECTORS, FRIEND_SELECTORS, LOGOUT_SELECTORS, HOME_SELECTORS


def warmup_profile_task(email: str, password: str) -> Dict[str, Any]:
    """
    Run warmup for a profile using Playwright (low memory)
    - 10 minute timeout
    - Auto cleanup on crash
    """
    stats = {
        "status": "started",
        "email": email,
        "likes": 0,
        "friend_requests": 0,
        "scroll_count": 0,
        "duration_seconds": 0
    }

    start_time = time.time()

    try:
        logger.info(f"Starting warmup for {email}")
        broadcast_status(email, "starting", "Starting browser...")

        # headless=True for server (Render), saves memory
        with browser_session(headless=True) as driver:
            broadcast_status(email, "browser_ready", "Browser launched, navigating to Facebook...")

            # Login with detailed tracking
            login_result = login_to_facebook(driver, email, password)
            stats["login_screenshots"] = login_result.get("screenshots", [])
            stats["login_url"] = login_result.get("current_url")

            if not login_result["success"]:
                stats["status"] = "login_failed"
                stats["error"] = login_result.get("error", "Unknown login error")
                broadcast_status(email, "login_failed", f"Login failed: {stats['error']}",
                               error=stats["error"], screenshots=len(stats["login_screenshots"]))
                logger.error(f"Login failed for {email}: {stats['error']}")
                return stats

            logger.info(f"Login successful for {email}")
            stats["status"] = "logged_in"
            broadcast_status(email, "logged_in", "Login successful! Starting warmup activities...")

            # Calculate session duration
            min_duration = WARM_UP_CONFIG.get('min_duration_minutes', 5) * 60
            max_duration = WARM_UP_CONFIG.get('max_duration_minutes', 10) * 60
            session_duration = random.uniform(min_duration, max_duration)
            session_end = time.time() + session_duration

            logger.info(f"Session duration: {session_duration/60:.1f} minutes")
            broadcast_status(email, "warmup_started", f"Warmup duration: {session_duration/60:.1f} minutes",
                           duration_minutes=round(session_duration/60, 1))

            # Track last status broadcast time
            last_broadcast = time.time()

            # Main warmup loop
            while time.time() < session_end:
                try:
                    # Random action
                    action = random.choices(
                        ["scroll", "scroll", "scroll", "like", "pause"],
                        weights=[50, 25, 10, 10, 5]
                    )[0]

                    if action == "scroll":
                        scroll_amount = random.randint(300, 800)
                        scroll_page(driver, scroll_amount)
                        stats["scroll_count"] += 1

                    elif action == "like":
                        if like_post(driver):
                            stats["likes"] += 1
                            broadcast_status(email, "liked", f"Liked a post (total: {stats['likes']})",
                                           likes=stats["likes"])

                    elif action == "pause":
                        human_delay(2, 5)

                    # Small delay between actions
                    human_delay(1, 3)

                    # Broadcast progress every 30 seconds
                    if time.time() - last_broadcast > 30:
                        remaining = session_end - time.time()
                        broadcast_status(email, "in_progress",
                                       f"Scrolling... ({stats['scroll_count']} scrolls, {stats['likes']} likes, {remaining/60:.1f} min left)",
                                       scrolls=stats["scroll_count"], likes=stats["likes"],
                                       remaining_minutes=round(remaining/60, 1))
                        last_broadcast = time.time()

                except Exception as e:
                    logger.warning(f"Action error: {e}")
                    continue

            # Visit friend suggestions (80% chance)
            if random.random() < WARM_UP_CONFIG.get('friend_suggestions_probability', 0.8):
                try:
                    broadcast_status(email, "friend_suggestions", "Visiting friend suggestions...")
                    requests_sent = visit_friend_suggestions(driver)
                    stats["friend_requests"] = requests_sent
                    if requests_sent > 0:
                        broadcast_status(email, "friends_added", f"Sent {requests_sent} friend request(s)",
                                       friend_requests=requests_sent)
                except Exception as e:
                    logger.warning(f"Friend suggestions error: {e}")

            # Random delay before logout
            logout_delay = random.uniform(
                WARM_UP_CONFIG.get('min_logout_delay_minutes', 3) * 60,
                WARM_UP_CONFIG.get('max_logout_delay_minutes', 7) * 60
            )
            logger.info(f"Waiting {logout_delay/60:.1f} min before logout")
            broadcast_status(email, "pre_logout", f"Waiting {logout_delay/60:.1f} minutes before logout...",
                           logout_delay_minutes=round(logout_delay/60, 1))

            # Light scrolling during logout delay
            delay_end = time.time() + logout_delay
            while time.time() < delay_end:
                scroll_page(driver, random.randint(200, 400))
                human_delay(10, 20)

            # Logout
            if WARM_UP_CONFIG.get('perform_logout', True):
                broadcast_status(email, "logging_out", "Logging out...")
                logout_from_facebook(driver)

            stats["status"] = "completed"
            broadcast_status(email, "completed", "Warmup completed successfully!",
                           stats=stats)

    except Exception as e:
        logger.error(f"Warmup error for {email}: {e}")
        stats["status"] = "error"
        stats["error"] = str(e)
        broadcast_status(email, "error", f"Error: {str(e)}", error=str(e))

        # Cleanup on error
        browser_pool.cleanup_all()

    finally:
        stats["duration_seconds"] = time.time() - start_time
        logger.info(f"Warmup completed for {email}: {stats}")

    return stats


def login_to_facebook(driver, email: str, password: str) -> Dict[str, Any]:
    """
    Login to Facebook using Playwright
    Returns dict with success status and screenshots
    """
    result = {
        "success": False,
        "error": None,
        "screenshots": [],
        "current_url": None,
        "page_title": None
    }

    try:
        logger.info(f"[{email}] Navigating to Facebook...")
        driver.get("https://www.facebook.com")
        human_delay(2, 4)

        # Screenshot: Login page loaded
        screenshot = take_screenshot(driver, "01_login_page", email)
        if screenshot:
            result["screenshots"].append({"stage": "login_page", **screenshot})

        # Find and fill email using Playwright
        # Selector from config/selectors.py - easy to update if Facebook changes HTML
        logger.info(f"[{email}] Entering email...")
        driver.human_type(LOGIN_SELECTORS["email_input"], email)
        human_delay(0.5, 1)

        # Find and fill password
        logger.info(f"[{email}] Entering password...")
        driver.human_type(LOGIN_SELECTORS["password_input"], password)
        human_delay(0.5, 1)

        # Screenshot: Before clicking login
        screenshot = take_screenshot(driver, "02_before_login_click", email)
        if screenshot:
            result["screenshots"].append({"stage": "before_login", **screenshot})

        # Click login button
        logger.info(f"[{email}] Clicking login button...")
        driver.human_click(LOGIN_SELECTORS["login_button"])
        human_delay(4, 6)

        # Screenshot: After login attempt
        screenshot = take_screenshot(driver, "03_after_login", email)
        if screenshot:
            result["screenshots"].append({"stage": "after_login", **screenshot})

        result["current_url"] = driver.current_url
        result["page_title"] = driver.page.title()

        # Check various failure conditions
        current_url = driver.current_url.lower()

        # Checkpoint/Security check
        if "checkpoint" in current_url:
            logger.error(f"[{email}] LOGIN FAILED: Security checkpoint detected")
            screenshot = take_screenshot(driver, "ERROR_checkpoint", email)
            if screenshot:
                result["screenshots"].append({"stage": "checkpoint_error", **screenshot})
            result["error"] = "Security checkpoint - Facebook wants verification"
            return result

        # Two-factor auth
        if "two_step_verification" in current_url or "twofactor" in current_url:
            logger.error(f"[{email}] LOGIN FAILED: Two-factor authentication required")
            screenshot = take_screenshot(driver, "ERROR_2fa", email)
            if screenshot:
                result["screenshots"].append({"stage": "2fa_error", **screenshot})
            result["error"] = "Two-factor authentication required"
            return result

        # Still on login page
        if "login" in current_url and "facebook.com/login" in current_url:
            logger.error(f"[{email}] LOGIN FAILED: Still on login page (wrong credentials?)")
            screenshot = take_screenshot(driver, "ERROR_login_failed", email)
            if screenshot:
                result["screenshots"].append({"stage": "login_failed", **screenshot})
            result["error"] = "Login failed - check credentials"
            return result

        # Account disabled
        page_source = driver.page_source.lower()
        if "account has been disabled" in page_source or "account is disabled" in page_source:
            logger.error(f"[{email}] LOGIN FAILED: Account disabled")
            screenshot = take_screenshot(driver, "ERROR_account_disabled", email)
            if screenshot:
                result["screenshots"].append({"stage": "account_disabled", **screenshot})
            result["error"] = "Account has been disabled by Facebook"
            return result

        # Success!
        logger.info(f"[{email}] LOGIN SUCCESSFUL! URL: {driver.current_url}")
        screenshot = take_screenshot(driver, "04_login_success", email)
        if screenshot:
            result["screenshots"].append({"stage": "login_success", **screenshot})

        result["success"] = True
        return result

    except Exception as e:
        logger.error(f"[{email}] LOGIN ERROR: {str(e)}")
        try:
            screenshot = take_screenshot(driver, "ERROR_exception", email)
            if screenshot:
                result["screenshots"].append({"stage": "exception_error", **screenshot})
            result["current_url"] = driver.current_url
        except:
            pass
        result["error"] = str(e)
        return result


def like_post(driver) -> bool:
    """Try to like a visible post using Playwright"""
    try:
        # Find like buttons using selector from config/selectors.py
        like_buttons = driver.find_elements("xpath", LIKE_SELECTORS["like_button_xpath"])

        visible_buttons = [btn for btn in like_buttons if btn.is_displayed()]

        if visible_buttons:
            button = random.choice(visible_buttons[:5])
            button.click()
            logger.info("Liked a post")
            human_delay(2, 5)
            return True

        return False

    except Exception as e:
        logger.debug(f"Like error: {e}")
        return False


def visit_friend_suggestions(driver) -> int:
    """Visit friend suggestions and send requests using Playwright"""
    requests_sent = 0

    try:
        driver.get("https://www.facebook.com/friends/suggestions")
        human_delay(3, 5)

        # Scroll through suggestions
        for _ in range(random.randint(2, 4)):
            scroll_page(driver, random.randint(300, 600))

        # Find Add Friend buttons using selector from config/selectors.py
        add_buttons = driver.find_elements("xpath", FRIEND_SELECTORS["add_friend_xpath"])

        visible_buttons = [btn for btn in add_buttons if btn.is_displayed()]

        # Send 1-3 requests
        target = random.randint(
            WARM_UP_CONFIG.get('min_friend_requests', 1),
            WARM_UP_CONFIG.get('max_friend_requests', 3)
        )

        for i, button in enumerate(visible_buttons[:target]):
            if random.random() < 0.6:  # 60% chance to actually send
                try:
                    button.click()
                    requests_sent += 1
                    logger.info(f"Sent friend request #{requests_sent}")
                    human_delay(60, 120)  # Wait between requests
                except Exception:
                    pass

        # Return to feed
        driver.get("https://www.facebook.com")
        human_delay(2, 4)

    except Exception as e:
        logger.error(f"Friend suggestions error: {e}")

    return requests_sent


def logout_from_facebook(driver) -> bool:
    """Logout from Facebook using Playwright"""
    try:
        # Click account menu using selector from config/selectors.py
        driver.human_click(LOGOUT_SELECTORS["profile_menu"])
        human_delay(1, 2)

        # Click logout
        driver.human_click(LOGOUT_SELECTORS["logout_button"])
        human_delay(2, 4)

        logger.info("Logged out successfully")
        return True

    except Exception as e:
        logger.error(f"Logout error: {e}")
        return False


def click_see_more(driver) -> bool:
    """Click 'See more' in sidebar to expand shortcuts"""
    try:
        driver.human_click(HOME_SELECTORS["see_more"])
        human_delay(1, 2)
        logger.info("Clicked 'See more' in sidebar")
        return True
    except Exception as e:
        logger.debug(f"See more click error: {e}")
        return False
