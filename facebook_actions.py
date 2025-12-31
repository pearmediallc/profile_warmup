"""
Facebook-specific actions: likes, comments, friend requests
"""

import asyncio
import random
import logging
import time
from typing import Optional, List
from config import WARM_UP_CONFIG, VIDEO_CONFIG
from human_actions import human_click, human_delay, random_delay
from scroll_behavior import ScrollBehavior

logger = logging.getLogger(__name__)


# Generic positive comments for random selection
RANDOM_COMMENTS = [
    "Nice! 👍",
    "Love this!",
    "Great post!",
    "Amazing! 🔥",
    "So true!",
    "This is awesome",
    "Wow!",
    "Beautiful ❤️",
    "Absolutely!",
    "Haha love it",
    "This made my day",
    "So cool!",
    "Couldn't agree more",
    "Fantastic!",
    "Yes! 🙌",
    "Perfect!",
    "This is great",
    "Lovely!",
    "Exactly!",
    "Well said!",
]


class FacebookActions:
    """Handles Facebook-specific interactions"""

    def __init__(self, page):
        self.page = page
        self.scroller = ScrollBehavior(page)
        self.likes_count = 0
        self.comments_count = 0
        self.videos_watched = 0
        self.friend_requests_count = 0
        self.last_like_time = 0
        self.last_comment_time = 0
        self.last_friend_request_time = 0
        self.actions_log = []

    def _log_action(self, action: str, details: str = "") -> None:
        """Log an action for debugging"""
        timestamp = time.strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {action}"
        if details:
            log_entry += f" - {details}"
        self.actions_log.append(log_entry)
        logger.info(log_entry)

    async def ensure_on_valid_page(self) -> bool:
        """Make sure we're on home feed or friend suggestions - nowhere else"""
        try:
            current_url = self.page.url

            # Valid pages we should be on
            valid_pages = [
                'facebook.com/?',  # Home feed
                'facebook.com/home',
                'facebook.com/#',
                'facebook.com/friends',  # Friend suggestions
            ]

            # Check if on valid page
            is_valid = any(valid in current_url for valid in valid_pages)

            # Also check if just on facebook.com main page
            if current_url.rstrip('/').endswith('facebook.com'):
                is_valid = True

            if not is_valid:
                logger.warning(f"Not on valid page: {current_url}")
                logger.info("Navigating back to home feed...")
                await self.navigate_to_news_feed()
                return False

            return True

        except Exception as e:
            logger.error(f"Error checking page: {e}")
            return False

    async def _can_like(self) -> bool:
        """Check if we can perform a like action (safety guards)"""
        if self.likes_count >= WARM_UP_CONFIG['max_likes_per_session']:
            logger.info("Max likes reached for session")
            return False

        time_since_last = time.time() - self.last_like_time
        if time_since_last < WARM_UP_CONFIG['min_time_between_likes']:
            logger.info(f"Too soon since last like ({time_since_last:.1f}s)")
            return False

        return True

    async def _can_send_friend_request(self) -> bool:
        """Check if we can send a friend request (safety guards)"""
        if self.friend_requests_count >= WARM_UP_CONFIG['max_friend_requests_per_session']:
            logger.info("Max friend requests reached for session")
            return False

        time_since_last = time.time() - self.last_friend_request_time
        if time_since_last < WARM_UP_CONFIG['min_time_between_requests']:
            logger.info(f"Too soon since last friend request ({time_since_last:.1f}s)")
            return False

        return True

    async def _can_comment(self) -> bool:
        """Check if we can post a comment (safety guards)"""
        max_comments = WARM_UP_CONFIG.get('max_comments_per_session', 5)
        if self.comments_count >= max_comments:
            logger.info("Max comments reached for session")
            return False

        min_time = WARM_UP_CONFIG.get('min_time_between_comments', 60)
        time_since_last = time.time() - self.last_comment_time
        if time_since_last < min_time:
            logger.info(f"Too soon since last comment ({time_since_last:.1f}s)")
            return False

        return True

    async def find_like_buttons(self) -> List:
        """Find visible like buttons on posts (not ads/sponsored)"""
        try:
            # EXCLUDED elements - buttons we should NEVER click
            excluded_texts = [
                'photo', 'video', 'live', 'feeling', 'activity',
                'tag', 'location', 'gif', 'sticker', 'poll',
                'create', 'post', 'story', 'reel', 'room',
                'marketplace', 'watch', 'gaming', 'fundraiser',
                'event', 'group', 'page', 'shop', 'messenger'
            ]

            # Only look for Like buttons inside the feed/posts area
            # These are the actual reaction buttons on posts
            selectors = [
                # Like button inside posts - most specific
                '[role="feed"] [aria-label="Like"]',
                '[data-pagelet*="Feed"] [aria-label="Like"]',
                # Post reaction buttons
                'div[aria-label="Like"][role="button"]',
                # The specific data attribute for like buttons
                'div[data-ad-rendering-role="like_button"]',
            ]

            buttons = []
            for selector in selectors:
                try:
                    found = await self.page.query_selector_all(selector)
                    buttons.extend(found)
                except Exception:
                    continue

            # Filter buttons carefully
            valid_buttons = []
            seen_positions = set()

            for button in buttons:
                try:
                    # Must be visible
                    if not await button.is_visible():
                        continue

                    # Get button text and aria-label
                    aria_label = await button.get_attribute('aria-label') or ''
                    inner_text = await button.text_content() or ''
                    combined_text = (aria_label + ' ' + inner_text).lower()

                    # Skip if contains excluded words
                    if any(excluded in combined_text for excluded in excluded_texts):
                        logger.debug(f"Skipping button with text: {combined_text[:50]}")
                        continue

                    # Must contain "like" specifically
                    if 'like' not in combined_text:
                        continue

                    # Get bounding box to avoid duplicates
                    box = await button.bounding_box()
                    if box:
                        # Skip if in top area (usually composer/create post area)
                        if box['y'] < 300:
                            logger.debug(f"Skipping button in top area: y={box['y']}")
                            continue

                        # Use position as key to avoid duplicates
                        pos_key = (int(box['x'] / 50), int(box['y'] / 50))
                        if pos_key in seen_positions:
                            continue
                        seen_positions.add(pos_key)

                    # Check parent is not in composer area
                    is_in_composer = await button.evaluate('''el => {
                        const parent = el.closest('[aria-label*="Create"]') ||
                                       el.closest('[aria-label*="Photo"]') ||
                                       el.closest('[data-pagelet="ProfileComposer"]') ||
                                       el.closest('[data-pagelet="Stories"]');
                        return parent !== null;
                    }''')

                    if is_in_composer:
                        logger.debug("Skipping button in composer area")
                        continue

                    valid_buttons.append(button)
                    logger.info(f"Found valid Like button: {aria_label}")

                except Exception as e:
                    logger.debug(f"Error checking button: {e}")
                    continue

            logger.info(f"Found {len(valid_buttons)} valid Like buttons")
            return valid_buttons[:5]  # Limit to first 5 valid

        except Exception as e:
            logger.error(f"Error finding like buttons: {e}")
            return []

    async def like_post(self) -> bool:
        """
        Like a random visible post
        - 70% chance to actually like (30% skip)
        - Respects rate limits
        """
        if not await self._can_like():
            return False

        # 70% chance to actually like
        if random.random() > WARM_UP_CONFIG['like_probability']:
            self._log_action("SKIP_LIKE", "Random skip (30% chance)")
            return False

        try:
            # Scroll a bit to find posts
            await self.scroller.scroll_down()

            # Find like buttons
            like_buttons = await self.find_like_buttons()
            if not like_buttons:
                self._log_action("LIKE_FAIL", "No like buttons found")
                return False

            # Pick a random button
            button = random.choice(like_buttons)

            # Human-like click
            await human_click(self.page, button)

            self.likes_count += 1
            self.last_like_time = time.time()
            self._log_action("LIKE", f"Liked post #{self.likes_count}")

            # Wait after liking
            await random_delay(
                WARM_UP_CONFIG['min_time_between_likes'],
                WARM_UP_CONFIG['max_time_between_likes']
            )

            return True

        except Exception as e:
            logger.error(f"Error liking post: {e}")
            self._log_action("LIKE_ERROR", str(e))
            return False

    async def view_comments(self) -> bool:
        """
        Expand and view comments on a post
        Just viewing, not interacting
        """
        try:
            # Find comment buttons/links
            selectors = [
                '[aria-label*="comment" i]',
                '[aria-label*="Comment" i]',
                'span:has-text("comments")',
            ]

            for selector in selectors:
                try:
                    elements = await self.page.query_selector_all(selector)
                    visible_elements = [el for el in elements if await el.is_visible()]

                    if visible_elements:
                        element = random.choice(visible_elements)
                        await human_click(self.page, element)
                        self._log_action("VIEW_COMMENTS", "Expanded comments section")

                        # "Read" comments for a bit
                        await random_delay(3, 8)

                        return True
                except Exception:
                    continue

            return False

        except Exception as e:
            logger.error(f"Error viewing comments: {e}")
            return False

    async def _human_type(self, element, text: str) -> None:
        """Type text with human-like speed variations"""
        for char in text:
            await element.type(char, delay=random.randint(80, 200))
            # Occasional longer pause (simulates thinking)
            if random.random() < 0.1:
                await asyncio.sleep(random.uniform(0.2, 0.5))

    async def find_comment_boxes(self) -> List:
        """Find comment input boxes on visible posts"""
        try:
            selectors = [
                '[aria-label*="Write a comment"]',
                '[aria-label*="write a comment"]',
                '[placeholder*="Write a comment"]',
                'div[contenteditable="true"][role="textbox"]',
            ]

            boxes = []
            for selector in selectors:
                found = await self.page.query_selector_all(selector)
                for box in found:
                    if await box.is_visible():
                        boxes.append(box)

            return boxes[:5]  # Limit to first 5 visible

        except Exception as e:
            logger.error(f"Error finding comment boxes: {e}")
            return []

    async def comment_on_post(self, custom_comment: str = None) -> bool:
        """
        Post a random comment on a visible post
        - Uses generic positive comments
        - Respects rate limits
        - 50% chance to actually comment (50% skip)

        Args:
            custom_comment: Optional custom comment text (uses random if not provided)
        """
        if not await self._can_comment():
            return False

        # 50% chance to actually comment
        comment_probability = WARM_UP_CONFIG.get('comment_probability', 0.5)
        if random.random() > comment_probability:
            self._log_action("SKIP_COMMENT", "Random skip")
            return False

        try:
            # Scroll a bit to find posts
            await self.scroller.scroll_down()
            await random_delay(1, 2)

            # First, click on the "Comment" button to open comment box
            comment_buttons = await self.page.query_selector_all(
                '[aria-label*="Leave a comment"], '
                '[aria-label*="Comment"], '
                'div[aria-label*="comment"][role="button"]'
            )

            visible_buttons = []
            for btn in comment_buttons:
                try:
                    if await btn.is_visible():
                        visible_buttons.append(btn)
                except Exception:
                    continue

            if visible_buttons:
                # Click a random comment button to open the input
                button = random.choice(visible_buttons)
                await human_click(self.page, button)
                await random_delay(1, 2)

            # Find comment input boxes
            comment_boxes = await self.find_comment_boxes()
            if not comment_boxes:
                self._log_action("COMMENT_FAIL", "No comment boxes found")
                return False

            # Pick a random box
            comment_box = random.choice(comment_boxes)

            # Click to focus
            await human_click(self.page, comment_box)
            await random_delay(0.5, 1)

            # Select comment text
            comment_text = custom_comment or random.choice(RANDOM_COMMENTS)

            # Type the comment with human-like speed
            await self._human_type(comment_box, comment_text)
            await random_delay(0.5, 1.5)

            # Press Enter to submit
            await self.page.keyboard.press('Enter')

            self.comments_count += 1
            self.last_comment_time = time.time()
            self._log_action("COMMENT", f"Posted: '{comment_text}' (#{self.comments_count})")

            # Wait after commenting
            min_wait = WARM_UP_CONFIG.get('min_time_between_comments', 60)
            max_wait = WARM_UP_CONFIG.get('max_time_between_comments', 120)
            await random_delay(min_wait, max_wait)

            return True

        except Exception as e:
            logger.error(f"Error posting comment: {e}")
            self._log_action("COMMENT_ERROR", str(e))
            return False

    async def pause_reading(self) -> None:
        """
        Pause and "read" content - just waiting
        Simulates user actually reading posts
        """
        pause_time = random.uniform(
            WARM_UP_CONFIG['scroll_pause_min'],
            WARM_UP_CONFIG['scroll_pause_max'] + 2  # Slightly longer for "reading"
        )
        self._log_action("PAUSE_READING", f"Reading for {pause_time:.1f}s")
        await asyncio.sleep(pause_time)

    async def find_videos(self) -> List:
        """Find video elements on the page"""
        try:
            # Facebook video selectors
            selectors = [
                'video',  # HTML5 video elements
                '[data-video-id]',  # Facebook video containers
                'div[data-pagelet*="Video"]',  # Video pagelets
                '[aria-label*="video" i]',  # Elements with video in aria-label
                'div[data-instancekey*="video" i]',  # Video instances
            ]

            videos = []
            for selector in selectors:
                try:
                    found = await self.page.query_selector_all(selector)
                    for video in found:
                        if await video.is_visible():
                            videos.append(video)
                except Exception:
                    continue

            return videos[:5]  # Limit to first 5 visible

        except Exception as e:
            logger.error(f"Error finding videos: {e}")
            return []

    async def watch_video(self) -> bool:
        """
        Find and watch a video for random duration
        - Scrolls to find videos
        - Clicks to play if needed
        - Watches for 5-30 seconds
        """
        # Random chance to actually watch
        if random.random() > VIDEO_CONFIG.get('watch_probability', 0.7):
            self._log_action("SKIP_VIDEO", "Random skip")
            return False

        try:
            # Scroll to find videos
            await self.scroller.scroll_down()
            await random_delay(1, 2)

            # Find videos
            videos = await self.find_videos()
            if not videos:
                self._log_action("VIDEO_FAIL", "No videos found")
                return False

            # Pick a random video
            video = random.choice(videos)

            # Scroll video into view
            await video.scroll_into_view_if_needed()
            await random_delay(0.5, 1)

            # Try to click to play (some videos auto-play)
            try:
                # Look for play button
                play_button = await self.page.query_selector(
                    '[aria-label*="Play" i], [aria-label*="play" i], '
                    'div[data-testid="play-button"]'
                )
                if play_button and await play_button.is_visible():
                    await human_click(self.page, play_button)
                else:
                    # Click on video itself
                    await human_click(self.page, video)
            except Exception:
                pass  # Video might auto-play

            # Watch for random duration
            watch_time = random.uniform(
                VIDEO_CONFIG.get('min_watch_time', 5),
                VIDEO_CONFIG.get('max_watch_time', 30)
            )

            self.videos_watched += 1
            self._log_action("WATCH_VIDEO", f"Watching for {watch_time:.1f}s (#{self.videos_watched})")

            await asyncio.sleep(watch_time)

            return True

        except Exception as e:
            logger.error(f"Error watching video: {e}")
            self._log_action("VIDEO_ERROR", str(e))
            return False

    async def navigate_to_friend_suggestions(self) -> bool:
        """Navigate to Facebook friend suggestions page"""
        try:
            await self.page.goto('https://www.facebook.com/friends/suggestions', timeout=30000)
            await asyncio.sleep(random.uniform(2, 4))  # Wait for page load
            self._log_action("NAVIGATE", "Went to friend suggestions")
            return True
        except Exception as e:
            logger.error(f"Error navigating to friend suggestions: {e}")
            return False

    async def navigate_to_news_feed(self) -> bool:
        """Navigate back to Facebook news feed"""
        try:
            await self.page.goto('https://www.facebook.com', timeout=30000)
            await asyncio.sleep(random.uniform(2, 4))
            self._log_action("NAVIGATE", "Returned to news feed")
            return True
        except Exception as e:
            logger.error(f"Error navigating to news feed: {e}")
            return False

    async def find_add_friend_buttons(self) -> List:
        """Find 'Add Friend' buttons on friend suggestions page"""
        try:
            selectors = [
                '[aria-label="Add friend"]',
                '[aria-label="Add Friend"]',
                'div[aria-label*="Add"][role="button"]',
            ]

            buttons = []
            for selector in selectors:
                found = await self.page.query_selector_all(selector)
                for btn in found:
                    if await btn.is_visible():
                        buttons.append(btn)

            return buttons[:10]

        except Exception as e:
            logger.error(f"Error finding add friend buttons: {e}")
            return []

    async def send_friend_request(self) -> bool:
        """
        Send a friend request from suggestions page
        - Respects rate limits
        - Random chance to skip
        """
        if not await self._can_send_friend_request():
            return False

        try:
            # Scroll to load suggestions
            await self.scroller.scroll_down()

            # Find add friend buttons
            buttons = await self.find_add_friend_buttons()
            if not buttons:
                self._log_action("FRIEND_REQUEST_FAIL", "No add friend buttons found")
                return False

            # Pick a random one
            button = random.choice(buttons)

            # Human-like click
            await human_click(self.page, button)

            self.friend_requests_count += 1
            self.last_friend_request_time = time.time()
            self._log_action("FRIEND_REQUEST", f"Sent request #{self.friend_requests_count}")

            # Wait after sending request
            await random_delay(
                WARM_UP_CONFIG['min_time_between_requests'],
                WARM_UP_CONFIG['max_time_between_requests']
            )

            return True

        except Exception as e:
            logger.error(f"Error sending friend request: {e}")
            return False

    async def friend_suggestions_session(self) -> None:
        """
        Complete friend suggestions interaction:
        - Navigate to suggestions
        - Scroll through
        - Send 0-3 requests (random)
        - Sometimes just view without adding
        """
        if not await self.navigate_to_friend_suggestions():
            return

        # Scroll through suggestions
        for _ in range(random.randint(2, 4)):
            await self.scroller.scroll_down()

        # Decide how many requests to send
        target_requests = random.randint(
            WARM_UP_CONFIG['min_friend_requests'],
            WARM_UP_CONFIG['max_friend_requests']
        )

        self._log_action("FRIEND_SUGGESTIONS", f"Planning to send {target_requests} requests")

        requests_sent = 0
        for _ in range(target_requests):
            # 60% chance to actually send each planned request
            if random.random() < 0.6:
                if await self.send_friend_request():
                    requests_sent += 1
            else:
                # Just scroll and view
                await self.scroller.scroll_down()
                await self.pause_reading()

        self._log_action("FRIEND_SUGGESTIONS_DONE", f"Sent {requests_sent} requests")

    def get_stats(self) -> dict:
        """Get action statistics"""
        return {
            'likes': self.likes_count,
            'videos_watched': self.videos_watched,
            'comments': self.comments_count,
            'friend_requests': self.friend_requests_count,
            'actions_log': self.actions_log,
            **self.scroller.get_stats()
        }
