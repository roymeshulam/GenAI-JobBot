"""
_summary_

Returns:
_type_: _description_
"""

import random
import time
from webbrowser import UnixBrowser

from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from src.logging_config import logger


class LinkedinAuthenticator:
    """
    A class used to authenticate a user to LinkedIn using a web browser.

    Attributes:
        browser (UnixBrowser): The web browser instance used for automation.
        email (str): The email address of the LinkedIn account.
        password (str): The password of the LinkedIn account.
    """

    def __init__(self, browser: UnixBrowser, email: str, password: str):
        self.browser = browser
        self.email = email
        self.password = password
        logger.debug("LinkedInAuthenticator initialized with browser: %s", browser)

    def login(self) -> bool:
        """
        Logs in to LinkedIn using the provided browser instance.

        Returns:
            bool: True if login was successful, False otherwise.
        """
        logger.info("Starting browser to log in to LinkedIn.")
        self.browser.get("https://www.linkedin.com/feed")
        time.sleep(random.uniform(1, 15))
        if "login" in self.browser.current_url:
            logger.info("User is not logged in. Proceeding with login.")
            return self.handle_login()
        else:
            logger.info("User is logged in.")
            return True

    def set_browser(self, browser: UnixBrowser):
        """
        Sets the browser instance for the LinkedInAuthenticator.

        Args:
            browser (UnixBrowser): The web browser instance to be used for automation.
        """
        self.browser = browser

    def handle_login(self) -> bool:
        """
        Handles the login process to LinkedIn.

        Returns:
            bool: True if login was successful, False otherwise.
        """
        logger.info("Navigating to the LinkedIn login page...")
        self.browser.get("https://www.linkedin.com/login")
        time.sleep(random.uniform(1, 15))
        try:
            logger.debug("Entering credentials...")
            username = self.browser.find_element(By.ID, "username")
            username.send_keys(self.email)
        except NoSuchElementException:
            logger.info("username element not found. using password only login.")
        try:
            password_field = self.browser.find_element(By.ID, "password")
            password_field.send_keys(self.password)
            login_button = self.browser.find_element(
                By.XPATH, '//button[@type="submit"]'
            )
            login_button.click()
            time.sleep(random.uniform(1, 15))
            logger.debug("Login form submitted.")
        except NoSuchElementException as e:
            logger.error("Could not log in to LinkedIn. Element not found: %s", e)
            return False

        if "checkpoint" in self.browser.current_url:
            try:
                logger.warning(
                    "Security checkpoint detected. Please complete the challenge."
                )
                WebDriverWait(self.browser, 300).until(
                    EC.url_contains("https://www.linkedin.com/feed/")
                )
                logger.info("Security check completed")
            except TimeoutException:
                logger.error("Security check not completed within the timeout.")
                return False
        return True
