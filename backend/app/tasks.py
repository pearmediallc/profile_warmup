"""
Celery tasks for warmup operations
"""

import logging
import time
import random
from typing import Dict, Any

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded

from app.celery_app import celery_app
from app.browser import browser_session, browser_pool, human_delay, human_type, scroll_page
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

logger = logging.getLogger(__name__)

# Import config
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from config import WARM_UP_CONFIG


@celery_app.task(
    bind=True,
    max_retries=2,
    time_limit=660,
    soft_time_limit=600,
    acks_late=True
)
def warmup_profile_task(self, email: str, password: str) -> Dict[str, Any]:
    """
    Run warmup for a profile in background
    - 10 minute timeout
    - Max 2 retries on failure
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

        with browser_session(headless=False) as driver:
            # Login
            if not login_to_facebook(driver, email, password):
                stats["status"] = "login_failed"
                return stats

            logger.info(f"Login successful for {email}")
            stats["status"] = "logged_in"

            # Calculate session duration
            min_duration = WARM_UP_CONFIG.get('min_duration_minutes', 5) * 60
            max_duration = WARM_UP_CONFIG.get('max_duration_minutes', 10) * 60
            session_duration = random.uniform(min_duration, max_duration)
            session_end = time.time() + session_duration

            logger.info(f"Session duration: {session_duration/60:.1f} minutes")

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

                    elif action == "pause":
                        human_delay(2, 5)

                    # Small delay between actions
                    human_delay(1, 3)

                except Exception as e:
                    logger.warning(f"Action error: {e}")
                    continue

            # Visit friend suggestions (80% chance)
            if random.random() < WARM_UP_CONFIG.get('friend_suggestions_probability', 0.8):
                try:
                    requests_sent = visit_friend_suggestions(driver)
                    stats["friend_requests"] = requests_sent
                except Exception as e:
                    logger.warning(f"Friend suggestions error: {e}")

            # Random delay before logout
            logout_delay = random.uniform(
                WARM_UP_CONFIG.get('min_logout_delay_minutes', 3) * 60,
                WARM_UP_CONFIG.get('max_logout_delay_minutes', 7) * 60
            )
            logger.info(f"Waiting {logout_delay/60:.1f} min before logout")

            # Light scrolling during logout delay
            delay_end = time.time() + logout_delay
            while time.time() < delay_end:
                scroll_page(driver, random.randint(200, 400))
                human_delay(10, 20)

            # Logout
            if WARM_UP_CONFIG.get('perform_logout', True):
                logout_from_facebook(driver)

            stats["status"] = "completed"

    except SoftTimeLimitExceeded:
        logger.error(f"Warmup timeout for {email}")
        stats["status"] = "timeout"
        browser_pool.cleanup_all()

    except Exception as e:
        logger.error(f"Warmup error for {email}: {e}")
        stats["status"] = "error"
        stats["error"] = str(e)

        # Cleanup on error
        browser_pool.cleanup_all()

        # Retry
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=60)

    finally:
        stats["duration_seconds"] = time.time() - start_time
        logger.info(f"Warmup completed for {email}: {stats}")

    return stats


def login_to_facebook(driver, email: str, password: str) -> bool:
    """Login to Facebook"""
    try:
        driver.get("https://www.facebook.com")
        human_delay(2, 4)

        # Find and fill email
        email_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "email"))
        )
        human_type(email_field, email)
        human_delay(0.5, 1)

        # Find and fill password
        password_field = driver.find_element(By.ID, "pass")
        human_type(password_field, password)
        human_delay(0.5, 1)

        # Click login
        login_button = driver.find_element(By.NAME, "login")
        login_button.click()
        human_delay(3, 5)

        # Check if login successful
        if "login" in driver.current_url.lower() or "checkpoint" in driver.current_url.lower():
            logger.error("Login failed - still on login page or checkpoint")
            return False

        logger.info("Login successful")
        return True

    except Exception as e:
        logger.error(f"Login error: {e}")
        return False


def like_post(driver) -> bool:
    """Try to like a visible post"""
    try:
        # Find like buttons
        like_buttons = driver.find_elements(
            By.XPATH,
            '//div[@aria-label="Like"][@role="button"] | //span[text()="Like"]/ancestor::div[@role="button"]'
        )

        visible_buttons = [btn for btn in like_buttons if btn.is_displayed()]

        if visible_buttons:
            button = random.choice(visible_buttons[:5])
            driver.execute_script("arguments[0].click();", button)
            logger.info("Liked a post")
            human_delay(2, 5)
            return True

        return False

    except Exception as e:
        logger.debug(f"Like error: {e}")
        return False


def visit_friend_suggestions(driver) -> int:
    """Visit friend suggestions and send requests"""
    requests_sent = 0

    try:
        driver.get("https://www.facebook.com/friends/suggestions")
        human_delay(3, 5)

        # Scroll through suggestions
        for _ in range(random.randint(2, 4)):
            scroll_page(driver, random.randint(300, 600))

        # Find Add Friend buttons
        add_buttons = driver.find_elements(
            By.XPATH,
            '//span[text()="Add friend"]/ancestor::div[@role="button"] | //div[@aria-label="Add friend"]'
        )

        visible_buttons = [btn for btn in add_buttons if btn.is_displayed()]

        # Send 1-3 requests
        target = random.randint(
            WARM_UP_CONFIG.get('min_friend_requests', 1),
            WARM_UP_CONFIG.get('max_friend_requests', 3)
        )

        for i, button in enumerate(visible_buttons[:target]):
            if random.random() < 0.6:  # 60% chance to actually send
                try:
                    driver.execute_script("arguments[0].click();", button)
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
    """Logout from Facebook"""
    try:
        # Click account menu
        account_menu = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((
                By.XPATH,
                '//div[@aria-label="Your profile"] | //div[@aria-label="Account"] | //image[@data-visualcompletion="media-vc-image"]'
            ))
        )
        account_menu.click()
        human_delay(1, 2)

        # Click logout
        logout_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((
                By.XPATH,
                '//span[text()="Log Out"] | //span[text()="Log out"]'
            ))
        )
        logout_button.click()
        human_delay(2, 4)

        logger.info("Logged out successfully")
        return True

    except Exception as e:
        logger.error(f"Logout error: {e}")
        return False
