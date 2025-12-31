"""
Human-like action utilities for browser automation
"""

import asyncio
import random
import math
from typing import Tuple
from config import WARM_UP_CONFIG


async def random_delay(min_sec: float, max_sec: float) -> None:
    """Wait for a random amount of time"""
    delay = random.uniform(min_sec, max_sec)
    await asyncio.sleep(delay)


async def human_delay() -> None:
    """Short human-like delay before actions"""
    await random_delay(
        WARM_UP_CONFIG['mouse_move_delay_min'],
        WARM_UP_CONFIG['mouse_move_delay_max']
    )


def get_random_offset() -> Tuple[int, int]:
    """Get random offset from center for clicks (not exact center)"""
    offset_range = WARM_UP_CONFIG['click_offset_range']
    x_offset = random.randint(-offset_range, offset_range)
    y_offset = random.randint(-offset_range, offset_range)
    return x_offset, y_offset


def bezier_curve(t: float, p0: float, p1: float, p2: float, p3: float) -> float:
    """Calculate point on cubic bezier curve for smooth mouse movement"""
    return (
        (1 - t) ** 3 * p0 +
        3 * (1 - t) ** 2 * t * p1 +
        3 * (1 - t) * t ** 2 * p2 +
        t ** 3 * p3
    )


def generate_mouse_path(
    start_x: float,
    start_y: float,
    end_x: float,
    end_y: float,
    num_points: int = 20
) -> list:
    """
    Generate a human-like mouse path using bezier curves
    Returns list of (x, y) coordinates
    """
    # Add some randomness to control points for natural curve
    distance = math.sqrt((end_x - start_x) ** 2 + (end_y - start_y) ** 2)
    deviation = distance * 0.2  # 20% deviation for natural curve

    # Random control points for bezier curve
    ctrl1_x = start_x + (end_x - start_x) * 0.25 + random.uniform(-deviation, deviation)
    ctrl1_y = start_y + (end_y - start_y) * 0.25 + random.uniform(-deviation, deviation)
    ctrl2_x = start_x + (end_x - start_x) * 0.75 + random.uniform(-deviation, deviation)
    ctrl2_y = start_y + (end_y - start_y) * 0.75 + random.uniform(-deviation, deviation)

    path = []
    for i in range(num_points + 1):
        t = i / num_points
        x = bezier_curve(t, start_x, ctrl1_x, ctrl2_x, end_x)
        y = bezier_curve(t, start_y, ctrl1_y, ctrl2_y, end_y)
        path.append((int(x), int(y)))

    return path


async def human_mouse_move(page, target_x: int, target_y: int) -> None:
    """
    Move mouse to target position with human-like curve
    """
    # Get current mouse position (approximate from viewport center if unknown)
    try:
        current_pos = await page.evaluate('''() => {
            return {x: window.mouseX || window.innerWidth/2, y: window.mouseY || window.innerHeight/2}
        }''')
        start_x, start_y = current_pos['x'], current_pos['y']
    except Exception:
        viewport = page.viewport_size
        start_x = viewport['width'] // 2 if viewport else 500
        start_y = viewport['height'] // 2 if viewport else 300

    # Generate curved path
    path = generate_mouse_path(start_x, start_y, target_x, target_y)

    # Move along path with variable speed
    for x, y in path:
        await page.mouse.move(x, y)
        # Random micro-delay for realistic movement (5-20ms)
        await asyncio.sleep(random.uniform(0.005, 0.02))


async def human_click(page, element) -> None:
    """
    Click an element with human-like behavior:
    1. Move mouse near element first
    2. Small pause
    3. Click with random offset from center
    """
    # Get element bounding box
    box = await element.bounding_box()
    if not box:
        # Fallback to regular click if can't get bounding box
        await element.click()
        return

    # Calculate target with random offset
    x_offset, y_offset = get_random_offset()
    target_x = box['x'] + box['width'] / 2 + x_offset
    target_y = box['y'] + box['height'] / 2 + y_offset

    # Move mouse to element with human-like curve
    await human_mouse_move(page, int(target_x), int(target_y))

    # Small pause before clicking (human hesitation)
    await human_delay()

    # Click
    await page.mouse.click(target_x, target_y)


async def human_scroll(page, pixels: int, smooth: bool = True) -> None:
    """
    Scroll the page with human-like behavior
    - Variable speed
    - Sometimes pauses mid-scroll
    """
    direction_text = "DOWN" if pixels > 0 else "UP"
    print(f"    🖱️  SCROLL {direction_text}: {abs(pixels)}px", end="", flush=True)

    if smooth:
        # Break scroll into smaller chunks for smooth effect
        direction = 1 if pixels > 0 else -1
        remaining = abs(pixels)
        chunks_done = 0

        while remaining > 0:
            # Random chunk size (50-150 pixels)
            chunk = min(remaining, random.randint(50, 150))
            await page.mouse.wheel(0, chunk * direction)
            remaining -= chunk
            chunks_done += 1

            # Small delay between scroll chunks (variable speed)
            await asyncio.sleep(random.uniform(0.02, 0.08))

            # Occasional micro-pause mid-scroll (5% chance)
            if random.random() < 0.05:
                print(".", end="", flush=True)  # Show pause indicator
                await asyncio.sleep(random.uniform(0.1, 0.3))

        print(f" ({chunks_done} chunks)")
    else:
        await page.mouse.wheel(0, pixels)
        print(" (instant)")


def weighted_random_choice(weights: dict) -> str:
    """
    Select a random action based on weights
    """
    actions = list(weights.keys())
    weight_values = list(weights.values())
    total = sum(weight_values)
    probabilities = [w / total for w in weight_values]

    return random.choices(actions, weights=probabilities, k=1)[0]
