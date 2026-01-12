"""
Profile Warm-Up Configuration Package
"""

# =============================================================================
# WARMUP BEHAVIOR CONFIGURATION
# =============================================================================
WARM_UP_CONFIG = {
    'enabled': True,

    # ==========================================================================
    # SESSION PROFILES - Randomly selected for each warmup
    # Makes total session time highly variable (5-20+ minutes)
    # ==========================================================================
    'session_profiles': {
        'quick': {
            'weight': 25,  # 25% chance
            'scroll_minutes': (3, 5),      # 3-5 min scrolling
            'logout_delay_minutes': (1, 2), # 1-2 min before logout
            'friend_probability': 0.3,      # 30% chance to visit friends
            'max_likes': 3,
            'description': 'Quick check-in session'
        },
        'normal': {
            'weight': 45,  # 45% chance
            'scroll_minutes': (5, 10),      # 5-10 min scrolling
            'logout_delay_minutes': (2, 5), # 2-5 min before logout
            'friend_probability': 0.7,      # 70% chance to visit friends
            'max_likes': 6,
            'description': 'Normal browsing session'
        },
        'long': {
            'weight': 20,  # 20% chance
            'scroll_minutes': (10, 18),     # 10-18 min scrolling
            'logout_delay_minutes': (3, 7), # 3-7 min before logout
            'friend_probability': 0.9,      # 90% chance to visit friends
            'max_likes': 10,
            'description': 'Extended browsing session'
        },
        'very_short': {
            'weight': 10,  # 10% chance
            'scroll_minutes': (1, 3),       # 1-3 min scrolling (just checking)
            'logout_delay_minutes': (0.5, 1), # 30s-1min before logout
            'friend_probability': 0.1,      # 10% chance to visit friends
            'max_likes': 2,
            'description': 'Very brief check'
        },
    },

    # Fallback values (used if session profiles disabled)
    'min_duration_minutes': 3,
    'max_duration_minutes': 18,

    # Like actions
    'min_likes': 1,
    'max_likes': 10,
    'like_probability': 0.7,  # 70% chance to like when action chosen
    'min_time_between_likes': 30,  # seconds
    'max_time_between_likes': 90,  # seconds

    # Comment actions
    'min_comments': 1,
    'max_comments': 3,
    'comment_probability': 0.5,  # 50% chance to comment when action chosen
    'min_time_between_comments': 60,  # seconds
    'max_time_between_comments': 120,  # seconds
    'max_comments_per_session': 5,  # safety limit

    # Friend requests
    'min_friend_requests': 0,         # minimum friend requests per session
    'max_friend_requests': 3,         # maximum friend requests per session
    'min_time_between_requests': 60,  # seconds between requests
    'max_time_between_requests': 120, # seconds between requests
    'friend_suggestions_probability': 0.7,  # default - overridden by session profile

    # Scrolling behavior
    'scroll_min_pixels': 300,
    'scroll_max_pixels': 800,
    'scroll_pause_min': 2,  # seconds
    'scroll_pause_max': 5,  # seconds
    'scroll_back_probability': 0.1,  # 10% chance to scroll back up

    # Human-like delays
    'mouse_move_delay_min': 0.5,  # seconds
    'mouse_move_delay_max': 1.5,  # seconds
    'click_offset_range': 5,  # pixels from center

    # Safety guards
    'max_likes_per_session': 10,
    'max_friend_requests_per_session': 3,
    'min_time_between_actions': 30,  # seconds - minimum between significant actions

    # Logout timing (fallback - overridden by session profile)
    'min_logout_delay_minutes': 1,
    'max_logout_delay_minutes': 7,
    'perform_logout': True,          # whether to actually logout or just close browser
}

# Video watching settings
VIDEO_CONFIG = {
    'min_watch_time': 5,    # seconds - minimum time to watch video
    'max_watch_time': 30,   # seconds - maximum time to watch video
    'watch_probability': 0.7,  # 70% chance to watch when video found
}

# Action weights for random selection
# Higher weight = more likely to be chosen
ACTION_WEIGHTS = {
    'scroll_down': 50,      # 50% - main action (scrolling feed)
    'scroll_up': 10,        # 10% - occasional scroll back up
    'pause_reading': 25,    # 25% - reading pauses (simulates reading posts)
    'like_post': 15,        # 15% - like posts while scrolling
    # 'watch_video': 0,     # disabled - can enable if needed
}

# =============================================================================
# FACEBOOK SELECTORS (from selectors.py)
# =============================================================================
from config.selectors import (
    LOGIN_SELECTORS,
    HOME_SELECTORS,
    LIKE_SELECTORS,
    FRIEND_SELECTORS,
    LOGOUT_SELECTORS,
    ERROR_SELECTORS,
    COMMENT_SELECTORS,
)
