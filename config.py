"""
Profile Warm-Up Configuration
"""

WARM_UP_CONFIG = {
    'enabled': True,

    # Session duration (in minutes)
    'min_duration_minutes': 5,
    'max_duration_minutes': 10,

    # Like actions
    'min_likes': 3,
    'max_likes': 8,
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
    'min_friend_requests': 0,
    'max_friend_requests': 3,
    'min_time_between_requests': 60,  # seconds
    'max_time_between_requests': 120,  # seconds
    'friend_suggestions_probability': 0.7,  # 70% chance to visit suggestions

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
    'max_likes_per_session': 8,
    'max_friend_requests_per_session': 3,
    'min_time_between_actions': 30,  # seconds - minimum between significant actions
}

# Video watching settings
VIDEO_CONFIG = {
    'min_watch_time': 5,    # seconds - minimum time to watch video
    'max_watch_time': 30,   # seconds - maximum time to watch video
    'watch_probability': 0.7,  # 70% chance to watch when video found
}

# Action weights for random selection
# SAFE MODE: Only scrolling and pauses (no clicking to avoid random click issues)
ACTION_WEIGHTS = {
    'scroll_down': 60,      # 60% - main action
    'scroll_up': 15,        # 15% - occasional scroll back
    'pause_reading': 25,    # 25% - reading pauses (just waiting, no clicks)
    # DISABLED FOR NOW - uncomment when click targeting is fixed:
    # 'like_post': 0,       # 0% - disabled
    # 'watch_video': 0,     # 0% - disabled
}
