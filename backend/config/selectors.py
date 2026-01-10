"""
Facebook Selectors Configuration
Update these if Facebook changes their HTML structure

How to find selectors:
1. Open Facebook in Chrome
2. Right-click element → Inspect
3. Look for: name, aria-label, role, or text content
4. Avoid using: id (Facebook uses dynamic IDs like "_r_e_")
"""

# =============================================================================
# LOGIN PAGE SELECTORS
# =============================================================================
LOGIN_SELECTORS = {
    # Email input field
    # HTML: <input class="x1i10hfl..." name="email" type="text" id="_r_e_" ...>
    # Note: id is dynamic (changes), so use name attribute
    "email_input": 'input[name="email"]',

    # Password input field
    # HTML: <input class="x1i10hfl..." name="pass" type="password" id="_r_h_" ...>
    # Note: id is dynamic (changes), so use name attribute
    "password_input": 'input[name="pass"]',

    # Login button
    # HTML: <button name="login" ...>Log in</button>
    # VERIFIED working via test
    "login_button": 'button[name="login"]',

    # Alternative login button selector (fallback)
    "login_button_alt": 'button:has-text("Log in")',
}

# =============================================================================
# HOME PAGE SELECTORS (after login)
# =============================================================================
HOME_SELECTORS = {
    # "See more" link in sidebar shortcuts
    # HTML: <div class="x6s0dn4..."><span>See more</span></div>
    # The span is nested deep inside divs
    "see_more": 'span:text("See more")',

    # Alternative: More specific selector for sidebar "See more"
    "see_more_sidebar": 'div.x6s0dn4 span:text("See more")',

    # Feed container
    "feed": 'div[role="feed"]',

    # Individual post
    "post": 'div[role="article"]',
}

# =============================================================================
# LIKE BUTTON SELECTORS
# =============================================================================
LIKE_SELECTORS = {
    # Like button (not yet liked)
    # HTML: <div aria-label="Like" role="button">
    "like_button": 'div[aria-label="Like"][role="button"]',

    # Alternative: Find by text
    "like_button_text": 'span:text("Like")',

    # XPath version (more reliable for complex structures)
    "like_button_xpath": '//div[@aria-label="Like"][@role="button"]',

    # Already liked button (to avoid re-clicking)
    "liked_button": 'div[aria-label="Remove Like"][role="button"]',
}

# =============================================================================
# FRIEND SUGGESTIONS SELECTORS
# =============================================================================
FRIEND_SELECTORS = {
    # Add friend button
    # HTML: <div aria-label="Add friend" role="button">
    "add_friend_button": 'div[aria-label="Add friend"][role="button"]',

    # Alternative: Find by text
    "add_friend_text": 'span:text("Add friend")',

    # XPath version
    "add_friend_xpath": '//span[text()="Add friend"]/ancestor::div[@role="button"]',

    # Confirm friend request (if popup appears)
    "confirm_button": 'span:text("Confirm")',
}

# =============================================================================
# LOGOUT SELECTORS
# =============================================================================
LOGOUT_SELECTORS = {
    # Profile/Account menu button (top right)
    # HTML: <div aria-label="Your profile"> or <div aria-label="Account">
    "profile_menu": 'div[aria-label="Your profile"], div[aria-label="Account"]',

    # Alternative: Avatar image
    "profile_avatar": 'image[data-visualcompletion="media-vc-image"]',

    # Logout button in dropdown
    # HTML: <span>Log Out</span> or <span>Log out</span>
    "logout_button": 'span:text("Log Out"), span:text("Log out")',

    # Settings & Privacy (if needed to navigate)
    "settings_privacy": 'span:text("Settings & privacy")',
}

# =============================================================================
# ERROR DETECTION SELECTORS
# =============================================================================
ERROR_SELECTORS = {
    # Wrong password error
    "wrong_password": 'div:text("Wrong password")',

    # Account disabled
    "account_disabled": 'div:text("account has been disabled")',

    # Security checkpoint
    "checkpoint": 'div:text("Security Check")',

    # Two-factor auth
    "two_factor": 'div:text("Two-factor authentication")',
}

# =============================================================================
# COMMENT SELECTORS (if you want to add commenting)
# =============================================================================
COMMENT_SELECTORS = {
    # Comment input box
    "comment_input": 'div[aria-label="Write a comment"]',

    # Comment button
    "comment_button": 'div[aria-label="Comment"][role="button"]',
}
