"""
Utility functions for handling scrollable elements in a web page.
Functions:
    is_scrollable(element):
        Checks if a given web element is scrollable.
        Args:
            element (WebElement): The web element to check.
        Returns:
            bool: True if the element is scrollable, False otherwise.
    scroll(driver, scrollable_element, start=0, end=5000, step=1000, reverse=False):
        Scrolls a given web element from a start position to an end position.
        Args:
            driver (WebDriver): The Selenium WebDriver instance.
            scrollable_element (WebElement): The web element to scroll.
            start (int, optional): The starting scroll position. Defaults to 0.
            end (int, optional): The ending scroll position. Defaults to 5000.
            step (int, optional): The step size for each scroll action. Defaults to 1000.
            reverse (bool, optional): If True, scrolls upwards. Defaults to False.
        Raises:
            ValueError: If the current_step value is zero.
"""

import random
import time

from src.logging_config import logger


def is_scrollable(element):
    """
    Checks if a given web element is scrollable.

    Args:
        element (WebElement): The web element to check.

    Returns:
        bool: True if the element is scrollable, False otherwise.
    """
    scroll_height = element.get_attribute("scrollHeight")
    client_height = element.get_attribute("clientHeight")
    scrollable = int(scroll_height) > int(client_height)
    logger.debug(
        "Element scrollable check: scrollHeight=%s, clientHeight=%s, scrollable=%s",
        scroll_height,
        client_height,
        scrollable,
    )
    return scrollable


def scroll(driver, scrollable_element, start=0, end=5000, step=1000, reverse=False):
    """
    Scrolls a scrollable element within a web page using a WebDriver instance.
    Args:
        driver (WebDriver): The WebDriver instance controlling the browser.
        scrollable_element (WebElement): The web element that is scrollable.
        start (int, optional): The starting scroll position. Defaults to 0.
        end (int, optional): The ending scroll position. Defaults to 5000.
        step (int, optional): The step size for each scroll increment. Defaults to 1000.
        reverse (bool, optional): If True, scrolls upwards. Defaults to False.
    Raises:
        ValueError: If `current_step` is zero.
    Logs:
        Various debug, warning, and error messages to help trace the scrolling process.
    Notes:
        - Adjusts the `end` value if it exceeds the maximum scroll height of the element.
        - Ensures the element is scrollable and visible before attempting to scroll.
        - Randomizes the scroll step size and includes delays to simulate human-like scrolling.
        - Ensures the final scroll position is set correctly.
    """
    logger.debug(
        "Starting slow scroll: start=%d, end=%d, step=%d, reverse=%s",
        start,
        end,
        step,
        reverse,
    )

    current_step = random.randint(1, step)
    if reverse:
        start, end = end, start
        current_step = -current_step

    if current_step == 0:
        logger.error("current_step value cannot be zero.")
        raise ValueError("current_step cannot be zero.")

    max_scroll_height = int(float(scrollable_element.get_attribute("scrollHeight")))
    current_scroll_position = int(float(scrollable_element.get_attribute("scrollTop")))
    logger.debug("Max scroll height of the element: %d", max_scroll_height)
    logger.debug("Current scroll position: %d", current_scroll_position)

    if reverse:
        if current_scroll_position < start:
            start = current_scroll_position
        logger.debug("Adjusted start position for upward scroll: %d", start)
    else:
        if end > max_scroll_height:
            logger.debug(
                "End value exceeds the scroll height. Adjusting end to %d",
                max_scroll_height,
            )
            end = max_scroll_height

    script_scroll_to = "arguments[0].scrollTop = arguments[1];"

    try:
        if scrollable_element.is_displayed():
            if not is_scrollable(scrollable_element):
                logger.warning("The element is not scrollable.")
                return

            if (current_step > 0 and start >= end) or (
                current_step < 0 and start <= end
            ):
                logger.warning(
                    "No scrolling will occur due to incorrect start/end values."
                )
                return

            position = start
            previous_position = (
                None  # Tracking the previous position to avoid duplicate scrolls
            )
            while (current_step > 0 and position < end) or (
                current_step < 0 and position > end
            ):
                if position == previous_position:
                    # Avoid re-scrolling to the same position
                    logger.debug(
                        "Stopping scroll as position hasn't changed: %d", position
                    )
                    break

                try:
                    driver.execute_script(
                        script_scroll_to, scrollable_element, position
                    )
                    logger.debug("Scrolled to position: %d", position)
                except Exception as e:
                    logger.error("Error during scrolling: %s", e)
                    print(f"Error during scrolling: {e}")

                previous_position = position
                position += current_step

                current_step = random.randint(1, step) * (-1 if reverse else 1)
                time.sleep(random.uniform(1, 15))

            # Ensure the final scroll position is correct
            driver.execute_script(script_scroll_to, scrollable_element, end)
            logger.debug("Scrolled to final position: %d", end)
            time.sleep(random.uniform(1, 15))
        else:
            logger.warning("The element is not visible.")
    except Exception as e:
        logger.error("Exception occurred during scrolling: %s", e)
