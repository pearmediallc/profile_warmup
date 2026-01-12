"""
Warmup tasks for Facebook profile warming
Using Playwright for better memory efficiency (512MB RAM compatible)
WITH DETAILED LOGGING - shows exactly what posts were liked, who was friended, timing info
"""

import logging
import time
import random
import os
import base64
import json
import traceback
from datetime import datetime
from typing import Dict, Any, Optional, List

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
    logger.info("Redis connected for status broadcasting")
except Exception:
    redis_client = None
    logger.warning("Redis not available - using log-only mode")


def broadcast_status(email: str, status: str, message: str, **extra):
    """
    Broadcast status update via Redis pub/sub.
    Also logs to console for visibility.
    """
    timestamp = datetime.utcnow().strftime("%H:%M:%S")

    # Always log to console with clear formatting
    log_msg = f"[{timestamp}] [{email.split('@')[0]}] {status.upper()}: {message}"
    print(f"📢 {log_msg}", flush=True)
    logger.info(log_msg)

    data = {
        "type": "status",
        "profile": email,
        "status": status,
        "message": message,
        "timestamp": datetime.utcnow().isoformat(),
        **extra
    }

    # Broadcast via Redis if available
    if redis_client:
        try:
            redis_client.publish("warmup_status", json.dumps(data))
        except Exception as e:
            logger.error(f"Redis broadcast error: {e}")


def set_status_callback(email: str, callback):
    """
    Legacy callback setter - no longer used.
    Status updates now go through Redis pub/sub and console logs.
    Kept for backwards compatibility.
    """
    pass  # No-op - we use Redis pub/sub now

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

# Main Facebook feed URL - always redirect here if navigated away
FACEBOOK_FEED_URL = "https://www.facebook.com/"


def ensure_on_feed(driver) -> bool:
    """
    Check if we're on the main Facebook feed, redirect if not.
    Returns True if we had to redirect, False if already on feed.
    """
    try:
        current_url = driver.current_url.lower()

        # Check if we're on the main feed
        # Allow: facebook.com/ or facebook.com (with optional query params like ?sk=h_chr)
        is_on_feed = (
            current_url == "https://www.facebook.com/" or
            current_url == "https://www.facebook.com" or
            current_url.startswith("https://www.facebook.com/?") or
            current_url.startswith("https://www.facebook.com/#")
        )

        if not is_on_feed:
            logger.info(f"Not on feed ({current_url}), redirecting to main feed...")
            driver.get(FACEBOOK_FEED_URL)
            human_delay(2, 4)
            return True

        return False

    except Exception as e:
        logger.warning(f"Error checking URL: {e}")
        # Try to redirect anyway
        try:
            driver.get(FACEBOOK_FEED_URL)
            human_delay(2, 4)
        except:
            pass
        return True


def warmup_profile_task(email: str, password: str) -> Dict[str, Any]:
    """
    Run warmup for a profile using Playwright (low memory)

    TIMING BREAKDOWN (all random within ranges from config):
    --------------------------------------------------------
    1. Login: ~10-20 seconds
    2. Main scrolling/liking: 5-10 minutes (from min/max_duration_minutes)
    3. Friend suggestions: 1-5 minutes (depends on requests sent)
    4. Pre-logout delay: 3-7 minutes (from min/max_logout_delay_minutes)
    5. Logout: ~5-10 seconds
    --------------------------------------------------------
    TOTAL: approximately 10-25 minutes per profile
    """
    stats = {
        "status": "started",
        "email": email,
        "likes": 0,
        "liked_posts": [],  # Detailed info about each liked post
        "friend_requests": 0,
        "friends_requested": [],  # Detailed info about each friend requested
        "scroll_count": 0,
        "duration_seconds": 0,
        "timing": {}  # Timing breakdown
    }

    start_time = time.time()

    # Get timing config
    min_duration = WARM_UP_CONFIG.get('min_duration_minutes', 5)
    max_duration = WARM_UP_CONFIG.get('max_duration_minutes', 10)
    min_logout_delay = WARM_UP_CONFIG.get('min_logout_delay_minutes', 3)
    max_logout_delay = WARM_UP_CONFIG.get('max_logout_delay_minutes', 7)

    print("\n" + "="*60, flush=True)
    print(f"🚀 STARTING WARMUP FOR: {email}", flush=True)
    print("="*60, flush=True)
    print(f"📋 TIMING PLAN:", flush=True)
    print(f"   • Scrolling/Liking phase: {min_duration}-{max_duration} minutes (random)", flush=True)
    print(f"   • Friend suggestions: ~1-5 minutes", flush=True)
    print(f"   • Pre-logout delay: {min_logout_delay}-{max_logout_delay} minutes (random)", flush=True)
    print(f"   • TOTAL ESTIMATED: {min_duration + min_logout_delay}-{max_duration + max_logout_delay + 5} minutes", flush=True)
    print("="*60 + "\n", flush=True)

    try:
        broadcast_status(email, "starting", "Starting browser...")

        # headless=True for server (Render), saves memory
        with browser_session(headless=True) as driver:
            broadcast_status(email, "browser_ready", "Browser launched, navigating to Facebook...")

            # ==================== LOGIN PHASE ====================
            login_start = time.time()
            login_result = login_to_facebook(driver, email, password)
            stats["timing"]["login_seconds"] = round(time.time() - login_start, 1)
            stats["login_screenshots"] = login_result.get("screenshots", [])
            stats["login_url"] = login_result.get("current_url")

            if not login_result["success"]:
                stats["status"] = "login_failed"
                stats["error"] = login_result.get("error", "Unknown login error")
                broadcast_status(email, "login_failed", f"Login failed: {stats['error']}",
                               error=stats["error"])
                return stats

            print(f"✅ LOGIN SUCCESSFUL (took {stats['timing']['login_seconds']}s)", flush=True)
            stats["status"] = "logged_in"
            broadcast_status(email, "logged_in", "Login successful! Starting warmup activities...")

            # ==================== SCROLLING/LIKING PHASE ====================
            session_duration = random.uniform(min_duration * 60, max_duration * 60)
            session_end = time.time() + session_duration
            stats["timing"]["planned_scroll_duration_minutes"] = round(session_duration / 60, 1)

            print(f"\n📜 SCROLLING PHASE: {stats['timing']['planned_scroll_duration_minutes']} minutes", flush=True)
            broadcast_status(email, "warmup_started",
                           f"Scrolling/Liking for {stats['timing']['planned_scroll_duration_minutes']:.1f} minutes",
                           duration_minutes=stats["timing"]["planned_scroll_duration_minutes"])

            scroll_start = time.time()
            last_broadcast = time.time()

            while time.time() < session_end:
                try:
                    ensure_on_feed(driver)

                    # Random action with weights
                    action = random.choices(
                        ["scroll", "scroll", "scroll", "like", "pause"],
                        weights=[50, 25, 10, 10, 5]
                    )[0]

                    if action == "scroll":
                        scroll_amount = random.randint(300, 800)
                        scroll_page(driver, scroll_amount)
                        stats["scroll_count"] += 1

                    elif action == "like":
                        post_info = like_post(driver, email)
                        if post_info:
                            stats["likes"] += 1
                            stats["liked_posts"].append(post_info)
                            broadcast_status(email, "liked",
                                           f"Liked post by {post_info['author']} (total: {stats['likes']})",
                                           likes=stats["likes"], post_author=post_info["author"])

                    elif action == "pause":
                        human_delay(2, 5)

                    human_delay(1, 3)

                    # Progress update every 30 seconds
                    if time.time() - last_broadcast > 30:
                        remaining = max(0, session_end - time.time())
                        elapsed = time.time() - scroll_start
                        print(f"⏱️  Progress: {elapsed/60:.1f}min elapsed, {remaining/60:.1f}min remaining | "
                              f"Scrolls: {stats['scroll_count']}, Likes: {stats['likes']}", flush=True)
                        broadcast_status(email, "in_progress",
                                       f"{stats['scroll_count']} scrolls, {stats['likes']} likes, {remaining/60:.1f} min left",
                                       scrolls=stats["scroll_count"], likes=stats["likes"],
                                       remaining_minutes=round(remaining/60, 1))
                        last_broadcast = time.time()

                except Exception as e:
                    logger.warning(f"Action error: {e}")
                    continue

            stats["timing"]["actual_scroll_duration_minutes"] = round((time.time() - scroll_start) / 60, 1)
            print(f"✅ SCROLLING COMPLETE: {stats['scroll_count']} scrolls, {stats['likes']} likes", flush=True)

            # ==================== FRIEND SUGGESTIONS PHASE ====================
            if random.random() < WARM_UP_CONFIG.get('friend_suggestions_probability', 0.8):
                try:
                    print(f"\n👥 FRIEND SUGGESTIONS PHASE", flush=True)
                    broadcast_status(email, "friend_suggestions", "Visiting friend suggestions...")

                    friend_start = time.time()
                    friends_list = visit_friend_suggestions(driver, email)
                    stats["timing"]["friend_suggestions_minutes"] = round((time.time() - friend_start) / 60, 1)

                    stats["friend_requests"] = len(friends_list)
                    stats["friends_requested"] = friends_list

                    if friends_list:
                        friend_names = [f["name"] for f in friends_list]
                        broadcast_status(email, "friends_added",
                                       f"Sent {len(friends_list)} friend request(s): {', '.join(friend_names)}",
                                       friend_requests=len(friends_list),
                                       friend_names=friend_names)
                except Exception as e:
                    logger.warning(f"Friend suggestions error: {e}")
                    traceback.print_exc()

            # ==================== PRE-LOGOUT DELAY PHASE ====================
            logout_delay = random.uniform(min_logout_delay * 60, max_logout_delay * 60)
            stats["timing"]["planned_logout_delay_minutes"] = round(logout_delay / 60, 1)

            print(f"\n⏳ PRE-LOGOUT DELAY: {stats['timing']['planned_logout_delay_minutes']:.1f} minutes", flush=True)
            print(f"   (Light scrolling while waiting...)", flush=True)
            broadcast_status(email, "pre_logout",
                           f"Waiting {stats['timing']['planned_logout_delay_minutes']:.1f} minutes before logout...",
                           logout_delay_minutes=stats["timing"]["planned_logout_delay_minutes"])

            delay_start = time.time()
            delay_end = time.time() + logout_delay
            while time.time() < delay_end:
                scroll_page(driver, random.randint(200, 400))
                human_delay(10, 20)

            stats["timing"]["actual_logout_delay_minutes"] = round((time.time() - delay_start) / 60, 1)

            # ==================== LOGOUT PHASE ====================
            if WARM_UP_CONFIG.get('perform_logout', True):
                print(f"\n🚪 LOGGING OUT...", flush=True)
                broadcast_status(email, "logging_out", "Logging out...")
                logout_from_facebook(driver)
                print(f"✅ LOGGED OUT", flush=True)

            stats["status"] = "completed"

    except Exception as e:
        logger.error(f"Warmup error for {email}: {e}")
        traceback.print_exc()
        stats["status"] = "error"
        stats["error"] = str(e)
        broadcast_status(email, "error", f"Error: {str(e)}", error=str(e))
        browser_pool.cleanup_all()

    finally:
        stats["duration_seconds"] = round(time.time() - start_time, 1)
        stats["timing"]["total_minutes"] = round(stats["duration_seconds"] / 60, 1)

        # Print final summary
        print("\n" + "="*60, flush=True)
        print(f"🏁 WARMUP COMPLETE FOR: {email}", flush=True)
        print("="*60, flush=True)
        print(f"📊 FINAL STATS:", flush=True)
        print(f"   • Status: {stats['status'].upper()}", flush=True)
        print(f"   • Total Duration: {stats['timing']['total_minutes']} minutes", flush=True)
        print(f"   • Scrolls: {stats['scroll_count']}", flush=True)
        print(f"   • Likes: {stats['likes']}", flush=True)
        if stats["liked_posts"]:
            print(f"   • Liked posts by: {', '.join([p['author'] for p in stats['liked_posts'][:5]])}", flush=True)
        print(f"   • Friend Requests: {stats['friend_requests']}", flush=True)
        if stats["friends_requested"]:
            print(f"   • Friends requested: {', '.join([f['name'] for f in stats['friends_requested']])}", flush=True)
        print("="*60 + "\n", flush=True)

        broadcast_status(email, "completed" if stats["status"] == "completed" else stats["status"],
                        f"Warmup {'completed' if stats['status'] == 'completed' else 'failed'} - "
                        f"{stats['timing']['total_minutes']} min, {stats['likes']} likes, {stats['friend_requests']} friends",
                        stats=stats)

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


def like_post(driver, email: str) -> Optional[Dict[str, str]]:
    """
    Try to like a visible post using Playwright.
    Returns dict with post details if successful, None if failed.
    """
    try:
        # Find like buttons using selector from config/selectors.py
        like_buttons = driver.find_elements("xpath", LIKE_SELECTORS["like_button_xpath"])
        visible_buttons = [btn for btn in like_buttons if btn.is_displayed()]

        if not visible_buttons:
            return None

        button = random.choice(visible_buttons[:5])

        # Try to get post author/content before clicking
        post_info = {"author": "Unknown", "content_preview": ""}
        try:
            # Navigate up to find the post container
            post_container = driver.page.locator('div[role="article"]').filter(has=driver.page.locator(LIKE_SELECTORS["like_button_xpath"])).first

            # Try to get author name (usually in a link with role="link")
            author_elem = post_container.locator('a[role="link"] strong, h4 a, span[dir="auto"] a').first
            if author_elem.count() > 0:
                post_info["author"] = author_elem.text_content()[:50] or "Unknown"

            # Try to get content preview
            content_elem = post_container.locator('div[data-ad-preview="message"], div[dir="auto"]').first
            if content_elem.count() > 0:
                content = content_elem.text_content() or ""
                post_info["content_preview"] = content[:100] + "..." if len(content) > 100 else content
        except Exception:
            pass  # Post info extraction is best-effort

        # Click the like button
        button.click()
        human_delay(2, 5)

        # Log detailed info
        print(f"❤️  LIKED POST by '{post_info['author']}'", flush=True)
        if post_info["content_preview"]:
            print(f"    Preview: {post_info['content_preview']}", flush=True)
        logger.info(f"Liked post by {post_info['author']}: {post_info['content_preview'][:50]}")

        return post_info

    except Exception as e:
        logger.debug(f"Like error: {e}")
        return None


def visit_friend_suggestions(driver, email: str) -> List[Dict[str, str]]:
    """
    Visit friend suggestions and send requests using Playwright.
    Returns list of dicts with friend names who were requested.
    """
    friends_requested = []

    try:
        print(f"👥 Navigating to friend suggestions page...", flush=True)
        driver.get("https://www.facebook.com/friends/suggestions")
        human_delay(3, 5)

        # Scroll through suggestions
        for _ in range(random.randint(2, 4)):
            scroll_page(driver, random.randint(300, 600))

        # Find Add Friend buttons using selector from config/selectors.py
        add_buttons = driver.find_elements("xpath", FRIEND_SELECTORS["add_friend_xpath"])
        visible_buttons = [btn for btn in add_buttons if btn.is_displayed()]

        print(f"👥 Found {len(visible_buttons)} friend suggestions", flush=True)

        # Send 1-3 requests
        target = random.randint(
            WARM_UP_CONFIG.get('min_friend_requests', 1),
            WARM_UP_CONFIG.get('max_friend_requests', 3)
        )

        for i, button in enumerate(visible_buttons[:target]):
            if random.random() < 0.6:  # 60% chance to actually send
                try:
                    # Try to get the person's name before clicking
                    friend_name = "Unknown"
                    try:
                        # The name is usually in a nearby span or link
                        # Look for the card container and find the name
                        card = driver.page.locator('div[role="listitem"], div[data-visualcompletion="ignore-dynamic"]').nth(i)
                        name_elem = card.locator('a[role="link"] span, span[dir="auto"]').first
                        if name_elem.count() > 0:
                            friend_name = name_elem.text_content()[:50] or "Unknown"
                    except Exception:
                        pass

                    button.click()
                    friends_requested.append({"name": friend_name, "timestamp": datetime.utcnow().isoformat()})

                    print(f"➕ FRIEND REQUEST SENT to: {friend_name}", flush=True)
                    logger.info(f"Friend request sent to: {friend_name}")

                    broadcast_status(email, "friend_request_sent",
                                   f"Sent friend request to {friend_name}",
                                   friend_name=friend_name,
                                   total_requests=len(friends_requested))

                    # Wait between requests (1-2 minutes)
                    wait_time = random.randint(60, 120)
                    print(f"    Waiting {wait_time}s before next action...", flush=True)
                    human_delay(wait_time - 10, wait_time + 10)

                except Exception as e:
                    logger.debug(f"Failed to send friend request: {e}")

        # Return to feed
        print(f"👥 Returning to feed. Total friend requests sent: {len(friends_requested)}", flush=True)
        driver.get("https://www.facebook.com")
        human_delay(2, 4)

    except Exception as e:
        logger.error(f"Friend suggestions error: {e}")
        traceback.print_exc()

    return friends_requested


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
