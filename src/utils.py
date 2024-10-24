from src.logging_config import logger
import random
import time


def is_scrollable(element):
    scroll_height = element.get_attribute("scrollHeight")
    client_height = element.get_attribute("clientHeight")
    scrollable = int(scroll_height) > int(client_height)
    logger.debug("Element scrollable check: scrollHeight=%s, clientHeight=%s, scrollable=%s", scroll_height,
                 client_height, scrollable)
    return scrollable


def scroll(driver, scrollable_element, start=0, end=5000, step=1000, reverse=False):
    logger.debug("Starting slow scroll: start=%d, end=%d, step=%d, reverse=%s",
                 start, end, step, reverse)

    current_step = random.randint(1, step)
    if reverse:
        start, end = end, start
        current_step = -current_step

    if current_step == 0:
        logger.error("current_step value cannot be zero.")
        raise ValueError("current_step cannot be zero.")

    max_scroll_height = int(
        float(scrollable_element.get_attribute("scrollHeight")))
    current_scroll_position = int(
        float(scrollable_element.get_attribute("scrollTop")))
    logger.debug("Max scroll height of the element: %d", max_scroll_height)
    logger.debug("Current scroll position: %d", current_scroll_position)

    if reverse:
        if current_scroll_position < start:
            start = current_scroll_position
        logger.debug("Adjusted start position for upward scroll: %d", start)
    else:
        if end > max_scroll_height:
            logger.debug(
                "End value exceeds the scroll height. Adjusting end to %d", max_scroll_height)
            end = max_scroll_height

    script_scroll_to = "arguments[0].scrollTop = arguments[1];"

    try:
        if scrollable_element.is_displayed():
            if not is_scrollable(scrollable_element):
                logger.warning("The element is not scrollable.")
                return

            if (current_step > 0 and start >= end) or (current_step < 0 and start <= end):
                logger.warning(
                    "No scrolling will occur due to incorrect start/end values.")
                return

            position = start
            previous_position = None  # Tracking the previous position to avoid duplicate scrolls
            while (current_step > 0 and position < end) or (current_step < 0 and position > end):
                if position == previous_position:
                    # Avoid re-scrolling to the same position
                    logger.debug(
                        "Stopping scroll as position hasn't changed: %d", position)
                    break

                try:
                    driver.execute_script(
                        script_scroll_to, scrollable_element, position)
                    logger.debug("Scrolled to position: %d", position)
                except Exception as e:
                    logger.error("Error during scrolling: %s", e)
                    print(f"Error during scrolling: {e}")

                previous_position = position
                position += current_step

                current_step = random.randint(1, step) * (-1 if reverse else 1)
                time.sleep(random.uniform(1, 2))

            # Ensure the final scroll position is correct
            driver.execute_script(script_scroll_to, scrollable_element, end)
            logger.debug("Scrolled to final position: %d", end)
            time.sleep(random.uniform(1, 2))
        else:
            logger.warning("The element is not visible.")
    except Exception as e:
        logger.error("Exception occurred during scrolling: %s", e)
