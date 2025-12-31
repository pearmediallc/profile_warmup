"""
Random scrolling behavior implementation
"""

import asyncio
import random
import logging
from config import WARM_UP_CONFIG
from human_actions import human_scroll, random_delay

logger = logging.getLogger(__name__)


class ScrollBehavior:
    """Handles all scrolling-related actions"""

    def __init__(self, page):
        self.page = page
        self.total_scrolled = 0
        self.scroll_count = 0

    async def scroll_down(self) -> None:
        """
        Scroll down by random pixels (300-800px)
        Then pause for random time (2-5 seconds) to "read" content
        """
        pixels = random.randint(
            WARM_UP_CONFIG['scroll_min_pixels'],
            WARM_UP_CONFIG['scroll_max_pixels']
        )

        logger.info(f"Scrolling down {pixels}px")
        await human_scroll(self.page, pixels)

        self.total_scrolled += pixels
        self.scroll_count += 1

        # Pause to "read" content
        await random_delay(
            WARM_UP_CONFIG['scroll_pause_min'],
            WARM_UP_CONFIG['scroll_pause_max']
        )

    async def scroll_up(self) -> None:
        """
        Sometimes scroll back up slightly (10% chance normally)
        This mimics re-reading behavior
        """
        # Scroll up less than we scroll down (100-300px)
        pixels = random.randint(100, 300)

        logger.info(f"Scrolling up {pixels}px")
        await human_scroll(self.page, -pixels)

        self.total_scrolled -= pixels
        self.scroll_count += 1

        # Short pause after scrolling up
        await random_delay(1, 2)

    async def maybe_scroll_back(self) -> bool:
        """
        10% chance to scroll back up after scrolling down
        Returns True if scrolled back
        """
        if random.random() < WARM_UP_CONFIG['scroll_back_probability']:
            await self.scroll_up()
            return True
        return False

    async def scroll_to_load_more(self) -> None:
        """
        Scroll to trigger lazy loading of more content
        Used when looking for elements like posts or friend suggestions
        """
        # Scroll a bit more to load content
        await human_scroll(self.page, random.randint(400, 600))
        # Wait for content to load
        await asyncio.sleep(random.uniform(1.5, 3))

    async def scroll_session(self, duration_seconds: float = 30) -> None:
        """
        Perform a scrolling session for specified duration
        Combines scroll down, occasional scroll up, and reading pauses
        """
        import time
        end_time = time.time() + duration_seconds

        while time.time() < end_time:
            # Primary action: scroll down
            await self.scroll_down()

            # Occasionally scroll back up
            await self.maybe_scroll_back()

            # Check if we're still within time
            if time.time() >= end_time:
                break

    async def get_scroll_position(self) -> int:
        """Get current scroll position"""
        return await self.page.evaluate('window.scrollY')

    async def scroll_to_top(self) -> None:
        """Scroll back to top of page"""
        current_pos = await self.get_scroll_position()
        if current_pos > 0:
            # Scroll up in chunks rather than instant jump
            while current_pos > 0:
                chunk = min(current_pos, random.randint(500, 800))
                await human_scroll(self.page, -chunk)
                current_pos -= chunk
                await asyncio.sleep(random.uniform(0.1, 0.2))

    def get_stats(self) -> dict:
        """Get scrolling statistics for logging"""
        return {
            'total_scrolled_pixels': self.total_scrolled,
            'scroll_count': self.scroll_count
        }
