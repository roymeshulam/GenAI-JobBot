import random
import time
from itertools import product
from pathlib import Path
from typing import List, Optional
from webbrowser import UnixBrowser

import psycopg2
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

import src.utils as utils
from src.gpt import GPTAnswerer
from src.linkedin_easy_applier import LinkedinEasyApplier
from src.logging_config import logger
from src.models import Job


class LinkedinJobManager:
    """
    Manages job applications and recruiter connections on LinkedIn.
    Attributes:
        browser (UnixBrowser): The browser instance used for web automation.
        mode (str): The mode of operation (e.g., "reapply", "reconnect").
        positions (list): List of job positions to search for.
        locations (list): List of locations to search for jobs.
        resume_docx_path (Path): Path to the resume document.
        database_url (str): URL of the database for storing job and recruiter information.
        companies_blacklist (list): List of blacklisted companies.
        gpt_answerer (GPTAnswerer): Instance of GPTAnswerer for generating responses.
        base_search_url (str): Base URL for LinkedIn job search.
        easy_applier_component (LinkedInEasyApplier): Component for applying to jobs easily.
    Methods:
        set_browser(browser: UnixBrowser):
            Sets the browser instance for the manager and its components.
        _load_jobs() -> List[dict]:
            Loads jobs from the database that have not been applied to.
        _load_recruiters() -> List[str]:
            Loads unique recruiter URLs from the database.
        _save_recruiter(recruiter: str):
            Updates the recruiter status to connected in the database.
        _save_job(job: Job, applied: bool, connected: bool) -> None:
            Saves job information to the database.
        run():
            Runs the job application or recruiter connection process based on the mode.
        apply():
            Applies to jobs based on the specified positions and locations.
        _job_lefs() -> bool:
            Checks if there are no jobs left to apply to on the current page.
        _daily_application_exceeded() -> bool:
            Checks if the daily application limit has been exceeded.
        _find_button(xpath: str) -> Optional[WebElement]:
            Finds a button on the page using the specified XPath.
        reapply() -> None:
            Reapplies to jobs that were not successfully applied to previously.
        reconnect() -> None:
            Reconnects with recruiters that have not been connected with previously.
        _recruiter_connect(url: str) -> bool:
            Connects with a recruiter using the specified URL.
        get_base_search_url(parameters: dict) -> str:
            Constructs the base search URL for LinkedIn job search.
        extract_job_information_from_tile(job_tile):
            Extracts job information from a job tile element.
        _scroll_page() -> None:
            Scrolls the page to load more content.
    """

    def __init__(
        self, browser: UnixBrowser, parameters: dict, gpt_answerer: GPTAnswerer
    ):
        logger.debug("Initializing LinkedInJobManager")
        self.browser = browser
        self.mode = parameters["mode"]
        self.positions = parameters["positions"]
        self.locations = parameters["locations"]
        self.resume_docx_path = Path(parameters["uploads"]["resume_docx_path"])
        self.database_url = parameters["database_url"]
        self.companies_blacklist = parameters["companies_blacklist"]
        self.gpt_answerer = gpt_answerer
        self.base_search_url = self.get_base_search_url(parameters)
        self.easy_applier_component = LinkedinEasyApplier(
            self.browser, self.resume_docx_path, self.gpt_answerer, parameters
        )

    def set_browser(self, browser: UnixBrowser):
        self.browser = browser
        self.easy_applier_component.set_browser(browser=browser)

    def _load_jobs(self) -> List[dict]:
        try:
            conn = psycopg2.connect(self.database_url)
            cursor = conn.cursor()
            query = """
                SELECT *
                FROM jobs
                WHERE applied = FALSE
                ORDER BY id DESC
                """
            cursor.execute(query)
            results = cursor.fetchall()
            column_names = [desc[0] for desc in cursor.description]
            result_dicts = [dict(zip(column_names, row)) for row in results]
            if results:
                return result_dicts
            else:
                return []
        except Exception as e:
            logger.error("Error loading jobs: %s", e)
            raise RuntimeError(f"Error loading jobs: {e}") from e
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def _load_recruiters(self) -> List[str]:
        logger.debug("loading recruiters URLs")
        try:
            conn = psycopg2.connect(self.database_url)
            cursor = conn.cursor()
            query = """
            WITH DistinctRecruiters AS (
                SELECT recruiter, MIN(id) AS min_id
                FROM jobs
                WHERE connected = FALSE
                GROUP BY recruiter
            )
            SELECT recruiter
            FROM DistinctRecruiters
            ORDER BY min_id DESC;
            """
            cursor.execute(query)
            results = cursor.fetchall()
            unique_recruiters = [row[0] for row in results]
            return unique_recruiters if results else []
        except Exception as e:
            logger.error("Error loading _load_recruiters: %s", e)
            raise RuntimeError(f"Error loading _load_recruiters: {e}") from e
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def _save_recruiter(self, recruiter: str):
        logger.debug("Updating recruiter status to connected for: %s", recruiter)
        try:
            conn = psycopg2.connect(self.database_url)
            cursor = conn.cursor()
            query = """
            UPDATE jobs
            SET connected = TRUE
            WHERE recruiter = %s;
            """
            cursor.execute(query, (recruiter,))
            conn.commit()
        except Exception as e:
            logger.error("Error updating recruiter status: %s", e)
            raise RuntimeError(f"Error updating recruiter status: {e}") from e
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def _save_job(self, job: Job, applied: bool, connected: bool) -> None:
        logger.debug("Saving job: %s", job)
        try:
            conn = psycopg2.connect(self.database_url)
            cursor = conn.cursor()
            insert_query = """
            INSERT INTO jobs (company, title, link, recruiter, location, applied, connected)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (link)
            DO UPDATE SET
                applied = EXCLUDED.applied,
                connected = EXCLUDED.connected;
            """
            cursor.execute(
                insert_query,
                (
                    job.company,
                    job.title,
                    job.link,
                    job.recruiter,
                    job.location,
                    applied,
                    connected,
                ),
            )
            conn.commit()
        except Exception as e:
            logger.error("Error saving job: %s %s", job, e)
            raise RuntimeError(f"Error saving job: {job} {e}") from e
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def run(self):
        """
        Executes the job application or recruiter connection process based on the mode.
        """
        if "reapply" in self.mode:
            self.reapply()
        elif "reconnect" in self.mode:
            self.reconnect()
        else:
            self.apply()
            self.reconnect(15)

    def apply(self):
        logger.info("Starting job application process")
        searches = list(product(self.positions, self.locations))
        random.shuffle(searches)
        successful_applications = 0
        failed_applications = 0
        for position, location in searches:
            job_page_number = -1
            logger.info(
                "Starting the search for position %s in %s.", position, location
            )
            while True:
                if successful_applications > 100:
                    logger.info("Daily applications target reached.")
                    return

                job_page_number += 1
                url = (
                    "https://www.linkedin.com/jobs/search/"
                    + self.base_search_url
                    + "&keywords="
                    + position
                    + "&location="
                    + location
                    + "&start="
                    + str(job_page_number * 25)
                )
                logger.info(
                    "Navigating to results page #%d at URL: %s", job_page_number, url
                )
                self.browser.get(url)
                time.sleep(random.uniform(3, 5))

                if self._job_lefs() is False:
                    logger.info(
                        "No jobs left, applications = %d/%d",
                        successful_applications,
                        failed_applications,
                    )
                    break

                try:
                    job_list_elements = self.browser.find_elements(
                        By.XPATH, "//li[@data-occludable-job-id]"
                    )
                    job_list = [
                        Job(*self.extract_job_information_from_tile(job_element))
                        for job_element in job_list_elements
                    ]
                    logger.info(
                        "Found %d jobs on this page",
                        len(
                            [
                                job
                                for job in job_list
                                if job.apply_method in ["Easy Apply", "Promoted"]
                            ]
                        ),
                    )
                    for job in job_list:
                        try:
                            if job.apply_method in ["Easy Apply", "Promoted"]:
                                if job.company.strip() in self.companies_blacklist:
                                    logger.info(
                                        "%s is blacklisted, skipping", job.company
                                    )
                                    continue

                                self.browser.get(job.link)
                                time.sleep(random.uniform(3, 5))

                                if self._daily_application_exceeded() is True:
                                    logger.info(
                                        "Daily applications exceeded, applications = %d/%d",
                                        successful_applications,
                                        failed_applications,
                                    )
                                    return

                                logger.info(
                                    "Applying for job: %s at %s %s",
                                    job.title,
                                    job.company,
                                    job.link,
                                )
                                self.easy_applier_component.job_apply(job)
                                successful_applications += 1
                                logger.info(
                                    "Successfully applied to job %s at %s %s, applications = %d/%d",
                                    job.title,
                                    job.company,
                                    job.link,
                                    successful_applications,
                                    failed_applications,
                                )
                                self._save_job(
                                    job=job,
                                    applied=True,
                                    connected=True if job.recruiter == "" else False,
                                )
                        except Exception:
                            failed_applications += 1
                            logger.info(
                                "Failed applying to job %s at %s, applications = %d/%d",
                                job.title,
                                job.company,
                                successful_applications,
                                failed_applications,
                            )
                            self._save_job(
                                job,
                                applied=False,
                                connected=True if job.recruiter == "" else False,
                            )
                            continue
                except Exception as e:
                    logger.error("Error during job application: %s", e)
                    continue
                logger.info(
                    "Applying to jobs on this page has been completed, applications = %d/%d",
                    successful_applications,
                    failed_applications,
                )
                time.sleep(random.uniform(5, 10))

    def _job_lefs(self) -> bool:
        try:
            no_jobs_element = self.browser.find_element(
                By.CLASS_NAME, "jobs-search-no-results-banner"
            )
            if no_jobs_element and "No matching jobs found" in no_jobs_element.text:
                logger.info("No matching jobs found.")
                return False
        except NoSuchElementException:
            pass
        return True

    def _daily_application_exceeded(self) -> bool:
        try:
            daily_applications_exceeded_element = self.browser.find_element(
                By.CLASS_NAME, "artdeco-inline-feedback--error"
            )
            if daily_applications_exceeded_element.text in [
                "The application feature is temporarily unavailable",
                "You’ve reached the Easy Apply application limit for today. Save this job and come back tomorrow to continue applying.",
            ]:
                return True
        except NoSuchElementException:
            pass
        return False

    def _find_button(self, xpath: str) -> Optional[WebElement]:
        logger.debug("Searching button")

        buttons = self.browser.find_elements(By.XPATH, xpath)
        if buttons:
            for button in buttons:
                try:
                    WebDriverWait(self.browser, random.uniform(5, 10)).until(
                        EC.visibility_of(button)
                    )
                except Exception:
                    continue
                try:
                    WebDriverWait(self.browser, random.uniform(5, 10)).until(
                        EC.element_to_be_clickable(button)
                    )
                    return button
                except Exception:
                    pass
        return None

    def reapply(self) -> None:
        jobs = self._load_jobs()
        for i in range(len(jobs)):
            if jobs[i]["applied"] == False:
                try:
                    job = Job(**jobs[i])
                    if job.company.strip() in self.companies_blacklist:
                        logger.info("%s is blacklisted, skipping", job.company)
                        continue

                    logger.info("Applying for job: %s at %s", job.title, job.company)
                    if self.easy_applier_component.job_apply(job=job) == True:
                        logger.info("Reaplied succeed")
                        self._save_job(job=job, applied=True, connected=job.connected)
                    else:
                        logger.error("Error during reapply: %s", jobs[i]["link"])
                except Exception:
                    logger.error("Error during reapply: %s", jobs[i]["link"])

    def reconnect(self, target: int = 0) -> None:
        """
        Reconnects with recruiters that have not been connected with previously.

        Args:
            target (int): The target number of successful connections. Defaults to 0.
        """
        failures = 0
        successes = 0
        recruiters = self._load_recruiters()
        for recruiter in recruiters:
            if target and successes > target:
                logger.info("Successful connections target reached.")
                break
            try:
                if self._recruiter_connect(url=recruiter) is True:
                    successes += 1
                    logger.info(
                        "Success reconnecting with %s, %d/%d/%d",
                        recruiter,
                        successes,
                        failures,
                        len(recruiters) - successes,
                    )
                    self._save_recruiter(recruiter=recruiter)
                else:
                    failures += 1
                    logger.error(
                        "Failed reconnecting with %s, %d/%d/%d",
                        recruiter,
                        successes,
                        failures,
                        len(recruiters) - successes,
                    )
            except Exception:
                failures += 1
                logger.error(
                    "Failed reconnecting with %s, %d/%d/%d",
                    recruiter,
                    successes,
                    failures,
                    len(recruiters) - successes,
                )

    def _recruiter_connect(self, url: str) -> bool:
        self.browser.get(url)
        time.sleep(random.uniform(3, 5))

        if self._find_button(
            '//button[contains(@class, "artdeco-button--secondary") and contains(., "Pending")]'
        ):
            return True

        self._scroll_page()

        def connect(self, button: WebElement, actions: ActionChains):
            actions.move_to_element(button).click().perform()
            time.sleep(random.uniform(1, 3))

            actions.move_to_element(
                self._find_button('//button[@aria-label="Send without a note"]')
            ).click().perform()
            time.sleep(random.uniform(1, 3))

            try:
                weekly_connections_exceeded_element = self.browser.find_element(
                    By.CLASS_NAME, "ip-fuse-limit-alert__header"
                )
                if (
                    weekly_connections_exceeded_element
                    and "reached the weekly invitation limit"
                    in weekly_connections_exceeded_element.text
                ):
                    logger.info("Weekly invitation limit reached.")
                    return False
            except NoSuchElementException:
                pass
            return True

        actions = ActionChains(self.browser)

        button = self._find_button(
            '//button[contains(@class, "artdeco-button artdeco-button--2 artdeco-button--primary ember-view") and contains(., "Connect")]'
        )
        if button:
            return connect(self=self, button=button, actions=actions)

        button = self._find_button(
            '//button[contains(@class, "artdeco-button artdeco-button--2 artdeco-button--secondary ember-view") and contains(., "Connect")]'
        )
        if button:
            return connect(self=self, button=button, actions=actions)

        actions.move_to_element(
            self._find_button('//button[@aria-label="More actions"]')
        ).click().perform()
        time.sleep(random.uniform(1, 3))

        if self._find_button(
            '//div[@role="button" and contains(., "Remove Connection")]'
        ):
            return True

        button = self._find_button('//div[@role="button" and contains(., "Connect")]')
        if button:
            return connect(self=self, button=button, actions=actions)

        return False

    def get_base_search_url(self, parameters: dict) -> str:
        logger.debug("Constructing base search URL")
        url_parts = []
        experience_levels = [
            str(i + 1)
            for i, v in enumerate(parameters.get("experience_level", {}).values())
            if v
        ]
        if experience_levels:
            url_parts.append(f"f_E={','.join(experience_levels)}")
        work_types = [
            str(i + 1)
            for i, v in enumerate(parameters.get("work_types", {}).values())
            if v
        ]
        if work_types:
            url_parts.append(f"f_WT={','.join(work_types)}")
        job_types = [
            key[0].upper()
            for key, value in parameters.get("job_types", {}).items()
            if value
        ]
        if job_types:
            url_parts.append(f"f_JT={','.join(job_types)}")
        date_mapping = {
            "all time": "",
            "month": "&f_TPR=r2592000",
            "week": "&f_TPR=r604800",
            "24 hours": "&f_TPR=r86400",
        }
        date_param = next(
            (v for k, v in date_mapping.items() if parameters.get("date", {}).get(k)),
            "",
        )
        url_parts.append("f_LF=f_AL")  # Easy Apply
        base_url = "&".join(url_parts)
        full_url = f"?{base_url}{date_param}"
        logger.debug("Base search URL constructed: %s", full_url)
        return full_url

    def extract_job_information_from_tile(self, job_tile):
        self.browser.execute_script("arguments[0].scrollIntoView();", job_tile)
        time.sleep(random.uniform(1, 2))

        job_title, company, job_location, apply_method, link = "", "", "", "", ""
        try:
            job_title = job_tile.find_element(
                By.CLASS_NAME, "job-card-list__title--link"
            ).get_attribute("aria-label")
        except NoSuchElementException:
            pass
        try:
            link = (
                job_tile.find_element(By.CLASS_NAME, "job-card-list__title--link")
                .get_attribute("href")
                .split("?")[0]
            )
        except NoSuchElementException:
            pass
        try:
            company = job_tile.find_element(
                By.CLASS_NAME, "artdeco-entity-lockup__subtitle"
            ).text
        except NoSuchElementException:
            pass
        try:
            job_location = job_tile.find_element(
                By.CLASS_NAME, "job-card-container__metadata-wrapper"
            ).text
        except NoSuchElementException:
            pass
        try:
            apply_method = job_tile.find_element(
                By.XPATH,
                '//li[contains(@class, "job-card-container__footer-item") and contains(@class, "inline-flex")]',
            ).text
        except NoSuchElementException:
            pass

        logger.debug(
            "Job inofrmation: title %s, company %s, location %s, link %s, apply method %s",
            job_title,
            company,
            job_location,
            link,
            apply_method,
        )
        return job_title, company, job_location, link, apply_method

    def _scroll_page(self) -> None:
        logger.debug("Scrolling the page")
        scrollable_element = self.browser.find_element(By.TAG_NAME, "html")
        utils.scroll(self.browser, scrollable_element, reverse=False)
        utils.scroll(self.browser, scrollable_element, reverse=True)
