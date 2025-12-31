"""
Main Profile Warm-Up Orchestrator
Coordinates all warm-up actions with human-like behavior
"""

import asyncio
import random
import time
import logging
import os
from datetime import datetime
from typing import Optional
from playwright.async_api import Page, Browser

from config import WARM_UP_CONFIG, ACTION_WEIGHTS
from human_actions import weighted_random_choice, random_delay
from scroll_behavior import ScrollBehavior
from facebook_actions import FacebookActions

# Create screenshots folder
SCREENSHOTS_DIR = "screenshots"
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ProfileWarmUp:
    """
    Main orchestrator for profile warm-up sessions

    Usage:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            # ... login to Facebook ...

            warmup = ProfileWarmUp(page)
            await warmup.run()
    """

    def __init__(self, page: Page, profile_name: str = "default"):
        self.page = page
        self.profile_name = profile_name
        self.scroller = ScrollBehavior(page)
        self.fb_actions = FacebookActions(page)
        self.session_start_time: Optional[float] = None
        self.session_end_time: Optional[float] = None
        self.actions_performed = []
        self.screenshot_count = 0

    async def take_screenshot(self, label: str = "") -> str:
        """Take a screenshot and save it"""
        self.screenshot_count += 1
        timestamp = datetime.now().strftime("%H%M%S")
        filename = f"{SCREENSHOTS_DIR}/{self.profile_name}_{timestamp}_{label}_{self.screenshot_count}.png"
        await self.page.screenshot(path=filename)
        print(f"    📸 Screenshot saved: {filename}")
        return filename

    def _calculate_session_duration(self) -> float:
        """Calculate random session duration in seconds"""
        min_minutes = WARM_UP_CONFIG['min_duration_minutes']
        max_minutes = WARM_UP_CONFIG['max_duration_minutes']
        duration_minutes = random.uniform(min_minutes, max_minutes)
        return duration_minutes * 60

    def _should_visit_friend_suggestions(self) -> bool:
        """Decide if this session should visit friend suggestions"""
        return random.random() < WARM_UP_CONFIG['friend_suggestions_probability']

    async def _execute_action(self, action: str) -> None:
        """Execute a single action from the action pool"""
        logger.info(f"Executing action: {action}")
        print(f"\n  ▶️  ACTION: {action.upper()}")

        try:
            if action == 'scroll_down':
                await self.scroller.scroll_down()
                self.actions_performed.append(('scroll_down', time.time()))
                print(f"    ✅ Scroll down complete")

            elif action == 'scroll_up':
                await self.scroller.scroll_up()
                self.actions_performed.append(('scroll_up', time.time()))
                print(f"    ✅ Scroll up complete")

            elif action == 'like_post':
                success = await self.fb_actions.like_post()
                self.actions_performed.append(('like_post', time.time(), success))
                if success:
                    print(f"    ❤️  Liked a post! (Total: {self.fb_actions.likes_count})")
                else:
                    print(f"    ⏭️  Skipped like (rate limit or no buttons)")

            elif action == 'pause_reading':
                await self.fb_actions.pause_reading()
                self.actions_performed.append(('pause_reading', time.time()))
                print(f"    📖 Reading pause complete")

            elif action == 'view_comments':
                success = await self.fb_actions.view_comments()
                self.actions_performed.append(('view_comments', time.time(), success))
                print(f"    💬 View comments: {'success' if success else 'skipped'}")

            elif action == 'comment_post':
                success = await self.fb_actions.comment_on_post()
                self.actions_performed.append(('comment_post', time.time(), success))
                print(f"    💬 Comment: {'posted!' if success else 'skipped'}")

            elif action == 'watch_video':
                success = await self.fb_actions.watch_video()
                self.actions_performed.append(('watch_video', time.time(), success))
                if success:
                    print(f"    🎬 Watched video! (Total: {self.fb_actions.videos_watched})")
                else:
                    print(f"    ⏭️  No video found/skipped")

        except Exception as e:
            logger.error(f"Error executing {action}: {e}")
            # Safety: if error, just scroll to continue
            await self.scroller.scroll_down()

    async def _main_loop(self) -> None:
        """Main warm-up loop - pick and execute random actions"""
        action_num = 0
        while time.time() < self.session_end_time:
            action_num += 1
            remaining = self.session_end_time - time.time()

            print(f"\n{'─'*40}")
            print(f"⏱️  Time remaining: {remaining/60:.1f} min | Action #{action_num}")
            print(f"{'─'*40}")

            # IMPORTANT: Check we're on valid page (home feed or friend suggestions)
            print(f"    🔍 Checking page location...")
            await self.fb_actions.ensure_on_valid_page()

            # Pick random action based on weights
            action = weighted_random_choice(ACTION_WEIGHTS)

            # Execute the action
            await self._execute_action(action)

            # Minimum delay between actions (safety)
            delay = random.uniform(1, 3)
            print(f"    ⏳ Waiting {delay:.1f}s before next action...")
            await asyncio.sleep(delay)

            # Check we didn't accidentally navigate away
            await self.fb_actions.ensure_on_valid_page()

            # Check remaining time
            if remaining < 30:
                logger.info(f"Session ending in {remaining:.0f}s")
                print(f"\n⚠️  Session ending soon! ({remaining:.0f}s left)")

    async def run(self) -> dict:
        """
        Run a complete warm-up session

        Returns:
            dict with session statistics
        """
        if not WARM_UP_CONFIG['enabled']:
            logger.info("Warm-up is disabled in config")
            return {'status': 'disabled'}

        logger.info("=" * 50)
        logger.info("Starting Profile Warm-Up Session")
        logger.info("=" * 50)

        # Calculate session timing
        self.session_start_time = time.time()
        duration = self._calculate_session_duration()
        self.session_end_time = self.session_start_time + duration

        logger.info(f"Session duration: {duration/60:.1f} minutes")
        logger.info(f"Target likes: {WARM_UP_CONFIG['min_likes']}-{WARM_UP_CONFIG['max_likes']}")

        try:
            # Ensure we're on news feed
            current_url = self.page.url
            if 'facebook.com' not in current_url:
                await self.fb_actions.navigate_to_news_feed()

            # Initial scroll and view
            logger.info("Phase 1: Initial browsing")
            await self._main_loop_for_duration(60)  # First minute

            # Maybe visit friend suggestions (around 40% into session)
            if self._should_visit_friend_suggestions():
                elapsed = time.time() - self.session_start_time
                if elapsed < duration * 0.6:  # Only if we have time
                    logger.info("Phase 2: Friend suggestions")
                    await self.fb_actions.friend_suggestions_session()
                    await self.fb_actions.navigate_to_news_feed()

            # Continue main loop for remaining time
            logger.info("Phase 3: Continued browsing")
            await self._main_loop()

        except Exception as e:
            logger.error(f"Error during warm-up: {e}")
            # Try to recover and continue with minimal browsing
            try:
                await self.fb_actions.navigate_to_news_feed()
                await self.scroller.scroll_session(30)
            except Exception:
                pass

        # Session complete
        actual_duration = time.time() - self.session_start_time
        stats = self._get_session_stats(actual_duration)

        logger.info("=" * 50)
        logger.info("Warm-Up Session Complete")
        logger.info(f"Duration: {actual_duration/60:.1f} minutes")
        logger.info(f"Likes: {stats['likes']}")
        logger.info(f"Videos watched: {stats['videos_watched']}")
        logger.info(f"Total scroll: {stats['total_scrolled_pixels']}px")
        logger.info("=" * 50)

        return stats

    async def _main_loop_for_duration(self, seconds: float) -> None:
        """Run main loop for a specific duration"""
        end_time = time.time() + seconds
        original_end = self.session_end_time
        self.session_end_time = min(end_time, original_end)
        await self._main_loop()
        self.session_end_time = original_end

    def _get_session_stats(self, duration: float) -> dict:
        """Compile session statistics"""
        fb_stats = self.fb_actions.get_stats()
        return {
            'status': 'completed',
            'duration_seconds': duration,
            'duration_minutes': duration / 60,
            **fb_stats,
            'actions_count': len(self.actions_performed)
        }


async def run_warmup(page: Page) -> dict:
    """
    Convenience function to run warm-up on a page

    Args:
        page: Playwright page object (should already be logged in)

    Returns:
        dict with session statistics
    """
    warmup = ProfileWarmUp(page)
    return await warmup.run()


# Example usage / testing
if __name__ == "__main__":
    async def main():
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            # Launch browser (use persistent context for logged-in session)
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()

            # Navigate to Facebook (assumes you'll manually login for testing)
            await page.goto('https://www.facebook.com')

            print("Please login to Facebook manually, then press Enter...")
            input()

            # Run warm-up
            warmup = ProfileWarmUp(page)
            stats = await warmup.run()

            print("\nSession Statistics:")
            for key, value in stats.items():
                if key != 'actions_log':
                    print(f"  {key}: {value}")

            await browser.close()

    asyncio.run(main())
