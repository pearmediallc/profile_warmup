"""
Run warm-up on multiple Facebook profiles
"""

import asyncio
from playwright.async_api import async_playwright
from warmup import run_warmup
from login import login_to_facebook
from config import WARM_UP_CONFIG

# Profiles to warm up
PROFILES = [
    {
        'email': 'kritikaverma290902@gmail.com',
        'password': 'kritika@2909'
    },
    {
        'email': 'devillover1225@gmail.com',
        'password': 'Hii@2000'
    },
]


async def warmup_profile(email: str, password: str, profile_num: int):
    """Warm up a single profile"""
    print(f"\n{'='*60}")
    print(f"Profile {profile_num}: {email}")
    print(f"{'='*60}")

    async with async_playwright() as p:
        # Launch browser with STEALTH settings to look more like real browser
        print(f"\n[{profile_num}] 🌐 Launching CHROMIUM browser (stealth mode)...")
        browser = await p.chromium.launch(
            headless=False,
            args=[
                '--start-maximized',
                '--disable-blink-features=AutomationControlled',  # Hide automation
                '--disable-infobars',  # Remove "Chrome is being controlled" bar
                '--no-sandbox',
                '--disable-dev-shm-usage',
            ]
        )
        print(f"[{profile_num}] ✅ Browser launched successfully!")

        # Create context with realistic settings
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='en-US',
            timezone_id='America/New_York',
            # Make it look like real browser
            java_script_enabled=True,
            has_touch=False,
            is_mobile=False,
        )

        # Remove webdriver property to avoid detection
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            // Remove automation indicators
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
        """)

        page = await context.new_page()

        try:
            # Step 1: Login
            print(f"[{profile_num}] Logging in...")
            login_success = await login_to_facebook(page, email, password)

            if not login_success:
                print(f"[{profile_num}] Login FAILED!")
                return {'email': email, 'status': 'login_failed'}

            print(f"[{profile_num}] Login successful!")

            # Step 2: Run warm-up
            if WARM_UP_CONFIG['enabled']:
                print(f"[{profile_num}] Starting warm-up session...")
                print(f"[{profile_num}] Actions: Scrolling, Likes, Video watching")

                stats = await run_warmup(page)

                print(f"\n[{profile_num}] Warm-up Complete!")
                print(f"  - Likes: {stats['likes']}")
                print(f"  - Videos watched: {stats['videos_watched']}")
                print(f"  - Total scroll: {stats['total_scrolled_pixels']}px")
                print(f"  - Duration: {stats['duration_minutes']:.1f} minutes")

                return {'email': email, 'status': 'success', 'stats': stats}
            else:
                print(f"[{profile_num}] Warm-up disabled in config")
                return {'email': email, 'status': 'disabled'}

        except Exception as e:
            print(f"[{profile_num}] Error: {e}")
            return {'email': email, 'status': 'error', 'error': str(e)}

        finally:
            await browser.close()


async def run_all_profiles():
    """Run warm-up on all profiles"""
    print("=" * 60)
    print("Facebook Profile Warm-Up")
    print(f"Profiles to process: {len(PROFILES)}")
    print("=" * 60)

    results = []

    for i, profile in enumerate(PROFILES, 1):
        result = await warmup_profile(
            profile['email'],
            profile['password'],
            i
        )
        results.append(result)

        # Wait between profiles (2 minutes)
        if i < len(PROFILES):
            wait_time = 120
            print(f"\nWaiting {wait_time} seconds before next profile...")
            await asyncio.sleep(wait_time)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for i, result in enumerate(results, 1):
        status = result['status']
        email = result['email']
        if status == 'success':
            stats = result['stats']
            print(f"[{i}] {email}: SUCCESS - {stats['likes']} likes, {stats['videos_watched']} videos")
        else:
            print(f"[{i}] {email}: {status.upper()}")

    return results


if __name__ == "__main__":
    asyncio.run(run_all_profiles())
