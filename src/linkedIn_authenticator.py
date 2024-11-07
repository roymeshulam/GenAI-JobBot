import random
import time
from webbrowser import UnixBrowser

from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from src.logging_config import logger


class LinkedInAuthenticator:

    def __init__(self, browser: UnixBrowser, email: str, password: str):
        self.browser = browser
        self.email = email
        self.password = password
        logger.debug(
            "LinkedInAuthenticator initialized with browser: %s", browser)

    def login(self) -> bool:
        logger.info("Starting browser to log in to LinkedIn.")
        self.browser.get('https://www.linkedin.com/feed')
        time.sleep(random.uniform(3, 5))
        if 'login' in self.browser.current_url:
            logger.info("User is not logged in. Proceeding with login.")
            return self.handle_login()
        else:
            logger.info("User is logged in.")
            return True

    def handle_login(self) -> bool:
        logger.info("Navigating to the LinkedIn login page...")
        self.browser.get("https://www.linkedin.com/login")
        time.sleep(random.uniform(3, 5))
        try:
            logger.debug("Entering credentials...")
            username = self.browser.find_element(By.ID, "username")
            username.send_keys(self.email)
        except NoSuchElementException as e:
            logger.info(
                "username element not found. using password only login.")
        try:
            password_field = self.browser.find_element(By.ID, "password")
            password_field.send_keys(self.password)
            login_button = self.browser.find_element(
                By.XPATH, '//button[@type="submit"]')
            login_button.click()
            time.sleep(random.uniform(1, 3))
            logger.debug("Login form submitted.")
        except NoSuchElementException as e:
            logger.error(
                "Could not log in to LinkedIn. Element not found: %s", e)
            return False

        if 'checkpoint' in self.browser.current_url:
            try:
                logger.warning(
                    "Security checkpoint detected. Please complete the challenge.")
                WebDriverWait(self.browser, 300).until(
                    EC.url_contains('https://www.linkedin.com/feed/')
                )
                logger.info("Security check completed")
            except TimeoutException:
                logger.error(
                    "Security check not completed within the timeout.")
                return False
        return True
