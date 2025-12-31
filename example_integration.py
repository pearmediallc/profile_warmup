"""
Facebook Profile Warm-Up
Includes: Login -> Scrolling -> Likes -> Comments
"""

import asyncio
from playwright.async_api import async_playwright
from warmup import ProfileWarmUp, run_warmup
from login import login_to_facebook
from config import WARM_UP_CONFIG


async def warmup_profile(email: str, password: str):
    """
    Complete warm-up flow:
    1. Login to profile
    2. Run warm-up session (scrolling, likes, comments)
    """
    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(
            headless=False,  # Set True for production
            args=['--start-maximized']
        )

        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )

        page = await context.new_page()

        try:
            # ========== STEP 1: Login ==========
            print("=" * 50)
            print("Step 1: Logging in to Facebook...")
            print("=" * 50)

            login_success = await login_to_facebook(page, email, password)

            if not login_success:
                print("Login failed! Please check credentials.")
                return None

            print("Login successful!")

            # ========== STEP 2: Warm-Up ==========
            if WARM_UP_CONFIG['enabled']:
                print("\n" + "=" * 50)
                print("Step 2: Running warm-up session...")
                print("=" * 50)
                print("This will perform:")
                print("  - Random scrolling through news feed")
                print("  - Liking 3-8 posts")
                print("  - Posting 1-3 random comments")
                print("  - Possibly visiting friend suggestions")
                print("=" * 50 + "\n")

                stats = await run_warmup(page)

                print("\n" + "=" * 50)
                print("Warm-up completed!")
                print(f"  - Likes: {stats['likes']}")
                print(f"  - Comments: {stats['comments']}")
                print(f"  - Friend requests: {stats['friend_requests']}")
                print(f"  - Duration: {stats['duration_minutes']:.1f} minutes")
                print("=" * 50)

                return stats
            else:
                print("Warm-up disabled in config.")
                return {'status': 'disabled'}

        except Exception as e:
            print(f"Error: {e}")
            return None

        finally:
            await browser.close()


async def warmup_single_profile_manual():
    """
    Run warm-up with manual login (for testing)
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            await page.goto('https://www.facebook.com')

            print("=" * 50)
            print("Please login to Facebook manually")
            print("Press Enter when logged in...")
            print("=" * 50)
            input()

            # Run warm-up
            print("\nStarting warm-up session...")
            stats = await run_warmup(page)

            print("\n" + "=" * 50)
            print("Session Statistics:")
            print("=" * 50)
            for key, value in stats.items():
                if key != 'actions_log':
                    print(f"  {key}: {value}")

            print("\nAction Log:")
            for log in stats.get('actions_log', [])[-10:]:  # Last 10 actions
                print(f"  {log}")

        finally:
            await browser.close()


async def warmup_multiple_profiles(profiles: list):
    """
    Warm up multiple profiles in sequence

    Args:
        profiles: List of dicts with 'email' and 'password' keys
    """
    results = []

    for i, profile in enumerate(profiles):
        print(f"\n{'='*60}")
        print(f"Processing profile {i+1}/{len(profiles)}: {profile['email']}")
        print(f"{'='*60}")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()

            try:
                # Login
                success = await login_to_facebook(
                    page,
                    profile['email'],
                    profile['password']
                )

                if success:
                    # Warm up
                    stats = await run_warmup(page)
                    results.append({
                        'email': profile['email'],
                        'status': 'success',
                        'stats': stats
                    })
                    print(f"Profile {i+1} completed: {stats['likes']} likes, {stats['comments']} comments")
                else:
                    results.append({
                        'email': profile['email'],
                        'status': 'login_failed'
                    })
                    print(f"Profile {i+1} login failed")

            except Exception as e:
                results.append({
                    'email': profile['email'],
                    'status': 'error',
                    'error': str(e)
                })
                print(f"Profile {i+1} error: {e}")

            finally:
                await browser.close()

        # Wait between profiles
        if i < len(profiles) - 1:
            wait_time = 120  # 2 minutes
            print(f"\nWaiting {wait_time}s before next profile...")
            await asyncio.sleep(wait_time)

    return results


# Quick test function
async def quick_scroll_test():
    """Quick test of just scrolling behavior"""
    from scroll_behavior import ScrollBehavior

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        await page.goto('https://www.facebook.com')
        print("Login manually and press Enter...")
        input()

        scroller = ScrollBehavior(page)

        print("Testing scroll down...")
        for i in range(5):
            await scroller.scroll_down()
            print(f"  Scroll {i+1} complete")

        print(f"\nStats: {scroller.get_stats()}")
        await browser.close()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] == '--manual':
            # Manual login test
            asyncio.run(warmup_single_profile_manual())
        elif sys.argv[1] == '--scroll-test':
            # Quick scroll test
            asyncio.run(quick_scroll_test())
        else:
            print("Usage:")
            print("  python example_integration.py              # Full warm-up with auto login")
            print("  python example_integration.py --manual     # Manual login test")
            print("  python example_integration.py --scroll-test # Quick scroll test")
    else:
        # Default: prompt for credentials and run warm-up
        print("Facebook Profile Warm-Up")
        print("=" * 50)
        email = input("Enter Facebook email: ")
        password = input("Enter Facebook password: ")
        asyncio.run(warmup_profile(email, password))
