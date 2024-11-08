import random
import time
from itertools import product
from pathlib import Path
from typing import List, Optional
from webbrowser import UnixBrowser

import psycopg2
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By

from src.gpt import GPTAnswerer
import src.utils as utils
from src.models import Job
from src.linkedIn_easy_applier import LinkedInEasyApplier
from src.logging_config import logger
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class LinkedInJobManager:
    def __init__(self, browser: UnixBrowser, parameters: dict, gpt_answerer: GPTAnswerer):
        logger.debug("Initializing LinkedInJobManager")
        self.browser = browser
        self.mode = parameters['mode']
        self.positions = parameters['positions']
        self.locations = parameters['locations']
        self.resume_docx_path = Path(parameters['uploads']['resume_docx_path'])
        self.database_url = parameters['database_url']
        self.companies_blacklist = parameters['companies_blacklist']
        self.gpt_answerer = gpt_answerer
        self.base_search_url = self.get_base_search_url(parameters)
        self.easy_applier_component = LinkedInEasyApplier(
            self.browser, self.resume_docx_path, self.gpt_answerer, parameters)

    def _load_jobs(self) -> List[dict]:
        logger.debug("Loading cache from JSON file: %s", type)
        try:
            conn = psycopg2.connect(self.database_url)
            cursor = conn.cursor()
            if 'reapply' in self.mode:
                query = """
                SELECT *
                FROM jobs
                WHERE applied = FALSE
                ORDER BY id DESC
                """
            elif 'reconnect' in self.mode:
                query = """
                SELECT *
                FROM jobs
                WHERE connected = FALSE
                AND applied = TRUE
                ORDER BY id DESC;
                """
            else:
                query = """
                SELECT *
                FROM jobs;
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
            logger.error(f'Error loading jobs: {e}')
            raise RuntimeError(f'Error loading jobs: {e}')
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
            cursor.execute(insert_query, (job.company, job.title, job.link,
                           job.recruiter, job.location, applied, connected))
            conn.commit()
        except Exception as e:
            logger.error(f'Error saving job: {job} {e}')
            raise RuntimeError(f'Error saving job: {job} {e}')
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def run(self):
        if ('reapply' in self.mode):
            self.reapply()
        elif ('reconnect' in self.mode):
            self.reconnect()
        else:
            self.apply()

        self.browser.get(
            'https://www.linkedin.com/feed')

    def apply(self):
        logger.info("Starting job application process")
        searches = list(product(self.positions, self.locations))
        random.shuffle(searches)
        successful_applications = 0
        failed_applications = 0
        for position, location in searches:
            job_page_number = -1
            logger.info(f"Starting the search for position {
                        position} in {location}.")
            while True:
                job_page_number += 1
                url = "https://www.linkedin.com/jobs/search/"+self.base_search_url + \
                    "&keywords="+position+"&location=" + \
                    location+"&start="+str(job_page_number*25)
                logger.info("Navigating to results page #%d at URL: %s",
                            job_page_number, url)
                self.browser.get(url)
                time.sleep(random.uniform(3, 5))

                if (self._job_lefs() == False):
                    logger.info(f'No jobs left, applications = {
                        successful_applications}/{failed_applications}')
                    break

                try:
                    job_results = self.browser.find_element(
                        By.CLASS_NAME, "jobs-search-results-list")
                    utils.scroll(self.browser, job_results, reverse=False)
                    utils.scroll(self.browser, job_results, reverse=True)

                    job_list_elements = self.browser.find_elements(By.CLASS_NAME, 'scaffold-layout__list-container')[
                        0].find_elements(By.CLASS_NAME, 'jobs-search-results__list-item')

                    job_list = [Job(*self.extract_job_information_from_tile(job_element))
                                for job_element in job_list_elements]
                    logger.info("Found %d jobs on this page", len(
                        [job for job in job_list if job.apply_method == 'Easy Apply']))
                    for job in job_list:
                        try:
                            if job.apply_method == 'Easy Apply':
                                if job.company.strip() in self.companies_blacklist:
                                    logger.info(
                                        f'{job.company} is blacklisted, skipping')
                                    continue

                                self.browser.get(job.link)
                                time.sleep(random.uniform(3, 5))

                                if (self._daily_application_exceeded() == True):
                                    logger.info(f'Daily applications exceeded, applications = {
                                                successful_applications}/{failed_applications}')
                                    return

                                logger.info(f"Applying for job: {
                                            job.title} at {job.company}")
                                self.easy_applier_component.job_apply(job)
                                successful_applications += 1
                                logger.info(f'Successfully applied to job {job.title} at {job.company}, applications = {
                                            successful_applications}/{failed_applications}')
                                self._save_job(
                                    job=job, applied=True, connected=True if job.recruiter == '' else False)
                        except Exception:
                            failed_applications += 1
                            logger.info(f'Failed applying to job {job.title} at {job.company}, applications = {
                                successful_applications}/{failed_applications}')
                            self._save_job(
                                job, applied=False, connected=True if job.recruiter == '' else False)
                            continue
                except Exception as e:
                    logger.error("Error during job application: %s", e)
                    continue
                logger.info(f'Applying to jobs on this page has been completed, applications = {
                    successful_applications}/{failed_applications}')
                time.sleep(random.uniform(5, 10))

    def _job_lefs(self) -> bool:
        try:
            no_jobs_element = self.browser.find_element(
                By.CLASS_NAME, 'jobs-search-no-results-banner')
            if no_jobs_element and 'No matching jobs found' in no_jobs_element.text:
                logger.info(
                    "No matching jobs found.")
                return False
        except NoSuchElementException:
            pass
        return True

    def _daily_application_exceeded(self) -> bool:
        try:
            daily_applications_exceeded_element = self.browser.find_element(
                By.CLASS_NAME, 'artdeco-inline-feedback--error')
            if daily_applications_exceeded_element.text in ['The application feature is temporarily unavailable',
                                                            'You’ve reached the Easy Apply application limit for today. Save this job and come back tomorrow to continue applying.']:
                return True
        except NoSuchElementException:
            pass
        return False

    def _find_button(self, xpath: str) -> Optional[WebElement]:
        logger.debug('Searching button')

        buttons = self.browser.find_elements(
            By.XPATH, xpath)
        if buttons:
            for button in buttons:
                try:
                    WebDriverWait(self.browser, random.uniform(5, 10)).until(
                        EC.visibility_of(button))
                except Exception:
                    continue
                try:
                    WebDriverWait(self.browser, random.uniform(5, 10)).until(
                        EC.element_to_be_clickable(button))
                    return button
                except Exception:
                    pass
        return None

    def reapply(self) -> None:
        jobs = self._load_jobs()
        for i in range(len(jobs)):
            if jobs[i]['applied'] == False:
                try:
                    job = Job(**jobs[i])
                    if job.company.strip() in self.companies_blacklist:
                        logger.info(
                            f'{job.company} is blacklisted, skipping')
                        continue

                    logger.info(f"Applying for job: {
                        job.title} at {job.company}")
                    if self.easy_applier_component.job_apply(job=job) == True:
                        logger.info("Reaplied succeed")
                        self._save_job(job=job, applied=True,
                                       connected=job.connected)
                    else:
                        logger.warning("Failed reapply: %s", jobs[i]['link'])
                except Exception:
                    logger.error("Error during reapply: %s", jobs[i]['link'])

    def reconnect(self) -> None:
        successes = 0
        failures = 0
        jobs = self._load_jobs()
        for i in range(len(jobs)):
            if jobs[i]['connected'] == False:
                try:
                    job = Job(**jobs[i])
                    if self._recruiter_connect(job=job) == True:
                        successes += 1
                        logger.info("Success reconnecting: %d/%d, %s",
                                    successes, failures, jobs[i]['recruiter'])
                        self._save_job(job=job, applied=job.applied,
                                       connected=True)
                    else:
                        failures += 1
                        logger.error("Failed reconnect: %d/%d, %s",
                                     successes, failures, jobs[i]['recruiter'])
                except Exception:
                    failures += 1
                    logger.error("Error during reconnect: %d/%d, %s",
                                 successes, failures, jobs[i]['recruiter'])

    def _recruiter_connect(self, job: Job) -> bool:
        if job.recruiter == '':
            return True

        self.browser.get(job.recruiter)
        time.sleep(random.uniform(3, 5))

        if (self._find_button(
                '//button[contains(@class, "artdeco-button--secondary") and contains(., "Pending")]')):
            return True

        self._scroll_page()

        def connect(self, button: WebElement, actions: ActionChains):
            actions.move_to_element(button).click().perform()
            time.sleep(random.uniform(1, 3))

            actions.move_to_element(self._find_button(
                '//button[@aria-label="Send without a note"]')).click().perform()
            time.sleep(random.uniform(1, 3))

            try:
                weekly_connections_exceeded_element = self.browser.find_element(
                    By.CLASS_NAME, 'ip-fuse-limit-alert__header')
                if weekly_connections_exceeded_element and 'reached the weekly invitation limit' in weekly_connections_exceeded_element.text:
                    logger.info(
                        "Weekly invitation limit reached.")
                    return False
            except NoSuchElementException:
                pass
            return True

        actions = ActionChains(self.browser)

        button = self._find_button(
            '//button[contains(@class, "artdeco-button artdeco-button--2 artdeco-button--primary ember-view pvs-profile-actions__action") and contains(., "Connect")]')
        if button:
            return connect(self=self, button=button, actions=actions)

        button = self._find_button(
            '//button[contains(@class, "artdeco-button artdeco-button--2 artdeco-button--secondary ember-view pvs-profile-actions__action") and contains(., "Connect")]')
        if button:
            return connect(self=self, button=button, actions=actions)

        actions.move_to_element(self._find_button(
            '//button[@aria-label="More actions"]')).click().perform()
        time.sleep(random.uniform(1, 3))

        if (self._find_button(
                '//div[@role="button" and contains(., "Remove Connection")]')):
            return True

        button = self._find_button(
            '//div[@role="button" and contains(., "Connect")]')
        if button:
            return connect(self=self, button=button, actions=actions)

        return False

    def get_base_search_url(self, parameters: dict) -> str:
        logger.debug("Constructing base search URL")
        url_parts = []
        experience_levels = [str(
            i + 1) for i, v in enumerate(parameters.get('experience_level', {}).values()) if v]
        if experience_levels:
            url_parts.append(f"f_E={','.join(experience_levels)}")
        work_types = [
            str(i + 1) for i, v in enumerate(parameters.get('work_types', {}).values()) if v]
        if work_types:
            url_parts.append(f"f_WT={','.join(work_types)}")
        job_types = [key[0].upper() for key, value in parameters.get(
            'job_types', {}).items() if value]
        if job_types:
            url_parts.append(f"f_JT={','.join(job_types)}")
        date_mapping = {
            "all time": "",
            "month": "&f_TPR=r2592000",
            "week": "&f_TPR=r604800",
            "24 hours": "&f_TPR=r86400"
        }
        date_param = next((v for k, v in date_mapping.items()
                          if parameters.get('date', {}).get(k)), "")
        url_parts.append("f_LF=f_AL")  # Easy Apply
        base_url = "&".join(url_parts)
        full_url = f"?{base_url}{date_param}&sortBy=DD"
        logger.debug("Base search URL constructed: %s", full_url)
        return full_url

    def extract_job_information_from_tile(self, job_tile):
        job_title, company, job_location, apply_method, link = "", "", "", "", ""
        try:
            job_title = job_tile.find_element(
                By.CLASS_NAME, 'job-card-list__title').get_attribute('aria-label')
        except NoSuchElementException:
            pass
        try:
            link = job_tile.find_element(
                By.CLASS_NAME, 'job-card-list__title').get_attribute('href').split('?')[0]
        except NoSuchElementException:
            pass
        try:
            company = job_tile.find_element(
                By.CLASS_NAME, 'job-card-container__primary-description').text
        except NoSuchElementException:
            pass
        try:
            job_location = job_tile.find_element(
                By.CLASS_NAME, 'job-card-container__metadata-item').text
        except NoSuchElementException:
            pass
        try:
            apply_method = job_tile.find_element(
                By.CLASS_NAME, 'job-card-container__apply-method').text
        except NoSuchElementException:
            pass

        logger.debug("Job inofrmation: title %s, company %s, location %s, link %s, apply method %s",
                     job_title, company, job_location, link, apply_method)
        return job_title, company, job_location, link, apply_method

    def _scroll_page(self) -> None:
        logger.debug("Scrolling the page")
        scrollable_element = self.browser.find_element(By.TAG_NAME, 'html')
        utils.scroll(self.browser, scrollable_element, reverse=False)
        utils.scroll(self.browser, scrollable_element, reverse=True)
