import os
import random
import re
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, List
from webbrowser import UnixBrowser

import psycopg2
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.pdfgen.canvas import Canvas
from selenium.common.exceptions import (
    MoveTargetOutOfBoundsException,
    NoSuchElementException,
    TimeoutException,
)
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

import src.utils as utils
from src.gpt import GPTAnswerer
from src.logging_config import logger
from src.models import Job


class LinkedinEasyApplier:
    def __init__(
        self,
        browser: UnixBrowser,
        resume_dir: Path,
        gpt_answerer: GPTAnswerer,
        parameters: dict,
    ):
        self.browser = browser
        self.resume_path = resume_dir
        self.gpt_answerer = gpt_answerer
        self.database_url = parameters["database_url"]
        self.questions = self._load_questions()

    def set_browser(self, browser: UnixBrowser):
        self.browser = browser
        self.questions = self._load_questions()

    def _load_questions(self) -> List[dict]:
        try:
            conn = psycopg2.connect(self.database_url)
            cursor = conn.cursor()
            query = """
            SELECT *
            FROM questions;
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
            logger.error("Error loading questions: %s", e)
            raise RuntimeError(f"Error loading questions: {e}") from e
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def _save_question(self, question_data: dict) -> None:
        question_data["question"] = self._sanitize_text(question_data["question"])

        for item in self.questions:
            if (
                question_data["question"] == item["question"]
                and question_data["type"] == item["type"]
            ):
                return

        self.questions.append(question_data)
        try:
            conn = psycopg2.connect(self.database_url)
            cursor = conn.cursor()

            insert_query = """
            INSERT INTO questions (type, question, answer)
            VALUES (%s, %s, %s);
            """
            cursor.execute(
                insert_query,
                (
                    question_data["type"],
                    question_data["question"],
                    question_data["answer"],
                ),
            )
            conn.commit()
        except Exception as e:
            logger.error("Error: %s", e)
            raise RuntimeError(f"Error saving question: {e}") from e
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def check_for_premium_redirect(self, job: Any, max_attempts=3):
        current_url = self.browser.current_url
        attempts = 0
        while "linkedin.com/premium" in current_url and attempts < max_attempts:
            logger.warning(
                "Redirected to LinkedIn Premium page. Attempting to return to job page."
            )
            attempts += 1

            self.browser.get(job.link)
            time.sleep(random.uniform(1, 15))
            current_url = self.browser.current_url

        if "linkedin.com/premium" in current_url:
            logger.error(
                "Failed to return to job page after %d attempts. Cannot apply for the job.",
                max_attempts,
            )
            raise RuntimeError(
                f"Redirected to LinkedIn Premium page and failed to return after {max_attempts} attempts. Job application aborted."
            )

    def job_apply(self, job: Job) -> bool:
        if self.browser.current_url != job.link:
            self.browser.get(job.link)
            time.sleep(random.uniform(1, 15))

        try:
            if self.browser.find_element(
                By.XPATH,
                '//div[contains(@class, "jobs-details-top-card__apply-error") and contains(., "No longer accepting applications")]',
            ):
                return True
        except NoSuchElementException:
            pass

        try:
            if self.browser.find_element(
                By.XPATH,
                '//span[contains(@class, "full-width") and contains(., "Application submitted")]',
            ):
                return True
        except NoSuchElementException:
            pass

        self._scroll_page()

        try:
            self.browser.execute_script("document.activeElement.blur();")

            job_description = self._get_job_description()
            job.set_job_description(job_description)

            recruiter = self._get_job_recruiter()
            job.set_recruiter(recruiter)

            easy_apply_button = self._find_easy_apply_button()
            actions = ActionChains(self.browser)
            actions.move_to_element(easy_apply_button).click().perform()
            time.sleep(random.uniform(1, 15))

            self.gpt_answerer.set_job(job)

            self._fill_application_form(job)

        except Exception as exc:
            self._discard_application()
            tb_str = traceback.format_exc()
            logger.error(
                "Failed to apply to job: %s at %s. Error traceback: %s",
                job.title,
                job.company,
                tb_str,
            )
            raise RuntimeError(
                "Failed to apply to job: %s at %s. Error traceback: %s"
                % (
                    job.title,
                    job.company,
                    tb_str,
                )
            ) from exc
        return True

    def _find_easy_apply_button(self) -> WebElement:
        logger.debug("Searching 'Easy Apply' button")

        buttons = self.browser.find_elements(
            By.XPATH,
            '//button[contains(@class, "jobs-apply-button") and contains(., "Easy Apply")]',
        )
        if buttons:
            for index, button in enumerate(buttons):
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
                    logger.debug(
                        "Found 'Easy Apply' button %d, attempting to click", index + 1
                    )
                    return button
                except Exception:
                    logger.warning(
                        "Button %d %s found but not clickable", index + 1, button.text
                    )
        raise RuntimeError("No clickable 'Easy Apply' button found")

    def _get_job_description(self) -> str:
        logger.debug("Getting job description")
        try:
            try:
                see_more_button = self.browser.find_element(
                    By.XPATH,
                    '//footer//button[@aria-label="Click to see more description"]',
                )
                # Scroll to the button
                self.browser.execute_script(
                    "arguments[0].scrollIntoView();", see_more_button
                )
                # Click the button using JavaScript
                self.browser.execute_script("arguments[0].click();", see_more_button)
                time.sleep(random.uniform(1, 15))
            except NoSuchElementException:
                logger.debug("See more button not found, skipping")
            except MoveTargetOutOfBoundsException:
                logger.debug("Move target out of bounds exception, skipping")

            description = self.browser.find_element(
                By.CLASS_NAME, "jobs-description-content"
            ).text
            logger.debug("Job description retrieved successfully")
            return description
        except Exception:
            tb_str = traceback.format_exc()
            logger.error("Error getting Job description: %s", tb_str)
            raise RuntimeError(f"Error getting Job description: \nTraceback:\n{tb_str}")

    def _get_job_recruiter(self):
        logger.debug("Getting job recruiter information")
        try:
            hiring_team_section = self.browser.find_element(
                By.XPATH, '//h2[text()="Meet the hiring team"]'
            )
        except NoSuchElementException:
            return ""

        recruiter_elements = hiring_team_section.find_elements(
            By.XPATH, './/following::a[contains(@href, "linkedin.com/in/")]'
        )
        if recruiter_elements:
            recruiter_element = recruiter_elements[0]
            recruiter = recruiter_element.get_attribute("href")
            logger.debug("Job recruiter link retrieved successfully: %s", recruiter)
            return recruiter
        return ""

    def _scroll_page(self) -> None:
        logger.debug("Scrolling the page")
        scrollable_element = self.browser.find_element(By.TAG_NAME, "html")
        utils.scroll(self.browser, scrollable_element, reverse=False)
        utils.scroll(self.browser, scrollable_element, reverse=True)

    def _fill_application_form(self, job):
        logger.debug("Filling out application form for job: %s", job)
        start_time = time.time()
        while time.time() - start_time < 600:
            self.fill_up(job)
            if self._application_submitted() == True:
                logger.debug("Application form submitted")
                break
        else:
            raise TimeoutError("Failed applying within 10 minutes")

    def _application_submitted(self) -> bool:
        logger.debug("Clicking 'Next' or 'Submit' button")
        next_button = self.browser.find_element(
            By.XPATH,
            "//button[contains(@class, 'artdeco-button--primary') and (span[text()='Next'] or span[text()='Review'] or span[text()='Submit application'] or span[text()='Continue applying'])]",
        )
        button_text = next_button.text.lower()
        if "submit application" in button_text:
            next_button.click()
            time.sleep(random.uniform(1, 15))
            return True
        elif "continue applying" in button_text:
            next_button.click()
            time.sleep(random.uniform(1, 15))
            return False
        else:
            progress_pre_click = self.browser.find_element(
                By.XPATH,
                '//div[contains(@aria-label, "Your job application progress")]',
            ).get_attribute("aria-label")
            next_button.click()
            time.sleep(random.uniform(1, 15))
            progress_post_click = self.browser.find_element(
                By.XPATH,
                '//div[contains(@aria-label, "Your job application progress")]',
            ).get_attribute("aria-label")
            if progress_pre_click == progress_post_click:
                raise RuntimeError("Failed answering or file upload.")
            else:
                return False

    def _unfollow_company(self) -> None:
        try:
            logger.debug("Unfollowing company")
            follow_checkbox = self.browser.find_element(
                By.XPATH, "//label[contains(.,'to stay up to date with their page.')]"
            )
            follow_checkbox.click()
            time.sleep(random.uniform(1, 15))
        except Exception:
            pass

    def _discard_application(self) -> None:
        logger.debug("Discarding application")
        try:
            self.browser.find_element(By.CLASS_NAME, "artdeco-modal__dismiss").click()
            time.sleep(random.uniform(1, 15))
            self.browser.find_elements(
                By.CLASS_NAME, "artdeco-modal__confirm-dialog-btn"
            )[0].click()
            time.sleep(random.uniform(1, 15))
        except Exception as e:
            logger.warning("Failed to discard application: %s", e)

    def fill_up(self, job) -> None:
        logger.debug("Filling up form sections for job: %s", job)
        try:
            easy_apply_content = WebDriverWait(
                self.browser, random.uniform(5, 10)
            ).until(
                EC.presence_of_element_located(
                    (
                        By.XPATH,
                        '//div[contains(@aria-label, "Your job application progress")]',
                    )
                )
            )
        except TimeoutException:
            return

        try:
            elements = easy_apply_content.find_elements(By.XPATH, '//div[@class="ph5"]')
            if len(elements) == 0:
                elements = easy_apply_content.find_elements(
                    By.XPATH, "//div[contains(@class, 'ph4')]"
                )
            for element in elements:
                self._process_form_element(element, job)
        except Exception as e:
            logger.error("Failed to find form elements: %s", e)

    def _process_form_element(self, element: WebElement, job) -> None:
        logger.debug("Processing form element")
        self._fill_additional_questions(element)
        if self._is_upload_field(element):
            self._handle_upload_fields(job)

    def _is_upload_field(self, element: WebElement) -> bool:
        is_upload = bool(element.find_elements(By.XPATH, ".//input[@type='file']"))
        logger.debug("Element is upload field: %s", is_upload)
        return is_upload

    def _handle_upload_fields(self, job: Job) -> None:
        file_upload_elements = self.browser.find_elements(
            By.XPATH, "//input[@type='file']"
        )
        for element in file_upload_elements:
            parent = element.find_element(By.XPATH, "..")
            self.browser.execute_script(
                "arguments[0].classList.remove('hidden')", element
            )
            if "resume" in parent.text.lower():
                element.send_keys(str(self.resume_path.resolve()))
                time.sleep(random.uniform(1, 15))
            elif "cover" in parent.text.lower():
                self._create_and_upload_cover_letter(element, job)
                time.sleep(random.uniform(1, 15))

    def _create_and_upload_cover_letter(self, element: WebElement, job: Job) -> None:
        folder_path = "cover_letters"
        if not os.path.exists(folder_path):
            os.makedirs(folder_path, exist_ok=True)
        file_path_pdf = os.path.join(
            folder_path, f"{job.title} - {job.company} Cover Letter.pdf"
        )
        try:
            cover_letter_text = (
                "Dear Sir or Madam,\n\n"
                + self.gpt_answerer.answer_question_textual_wide_range(
                    "Write a cover letter"
                )
                + "\n\nThank you for your consideration."
            )
            c = canvas.Canvas(file_path_pdf, pagesize=A4)
            page_width, page_height = A4
            text_object = c.beginText(50, page_height - 50)
            text_object.setFont("Helvetica", 12)
            max_width = round(page_width - 100)
            bottom_margin = 50

            lines = self._split_text_by_width(
                cover_letter_text, "Helvetica", 12, max_width
            )

            for line in lines:
                text_height = text_object.getY()
                if text_height > bottom_margin:
                    text_object.textLine(line)
                else:
                    c.drawText(text_object)
                    c.showPage()
                    text_object = c.beginText(50, page_height - 50)
                    text_object.setFont("Helvetica", 12)
                    text_object.textLine(line)
            c.drawText(text_object)
            c.save()
        except Exception as e:
            logger.error("Failed to generate cover letter: %s", e)
            tb_str = traceback.format_exc()
            logger.error("Traceback: %s", tb_str)
            raise

        file_size = os.path.getsize(file_path_pdf)
        max_file_size = 2 * 1024 * 1024  # 2 MB
        logger.debug("Cover letter file size: %d bytes", file_size)
        if file_size > max_file_size:
            logger.error("Cover letter file size exceeds 2 MB: %d bytes", file_size)
            raise ValueError(
                "Cover letter file size exceeds the maximum limit of 2 MB."
            )

        try:
            logger.debug("Uploading cover letter from path: %s", file_path_pdf)
            element.send_keys(os.path.abspath(file_path_pdf))
        except Exception as e:
            tb_str = traceback.format_exc()
            logger.error("Cover letter upload failed: %s", tb_str)
            raise RuntimeError(f"Upload failed: \nTraceback:\n{tb_str}") from e

    def _fill_additional_questions(self, element: WebElement) -> None:
        logger.debug("Filling additional questions")
        form_sections = element.find_elements(By.XPATH, '//div[@class="ph5"]/div/div')
        if len(form_sections) == 0:
            form_sections = element.find_elements(
                By.XPATH, "//div[contains(@class, 'ph4')]/div/div"
            )
        for section in form_sections:
            if self._handle_terms_of_service(section):
                logger.debug("Handled terms of service")
            elif self._find_and_handle_date_question(section):
                logger.debug("Handled textbox question")
            elif self._find_and_handle_radio_question(section):
                logger.debug("Handled radio question")
            elif self._find_and_handle_dropdown_question(section):
                logger.debug("Handled dropdown question")
            elif self._find_and_handle_textbox_question(section):
                logger.debug("Handled textbox question")

    def _handle_terms_of_service(self, element: WebElement) -> bool:
        try:
            checkbox = element.find_element(By.TAG_NAME, "label")
        except NoSuchElementException:
            return False

        if any(
            term in checkbox.text.lower()
            for term in [
                "confirmed",
                "terms of service",
                "privacy policy",
                "terms of use",
                "i consent",
            ]
        ):
            checkbox.click()
            time.sleep(random.uniform(1, 15))
            logger.debug("Clicked terms of service checkbox")
            return True
        return False

    def _find_and_handle_radio_question(self, section: WebElement) -> bool:
        try:
            question = section.find_element(By.CLASS_NAME, "fb-dash-form-element")
        except NoSuchElementException:
            return False

        radios = question.find_elements(By.CLASS_NAME, "fb-form-element__checkbox")
        if radios:
            question_text = section.text.lower()
            options = [
                radio.get_attribute("data-test-text-selectable-option__input").lower()
                for radio in radios
            ]

            for item in self.questions:
                if (
                    self._sanitize_text(question_text) == item["question"]
                    and item["type"] == "radio"
                    and item["answer"] in options
                ):
                    self._select_radio(radios, item["answer"])
                    return True

            answer = self.gpt_answerer.answer_question_from_options(
                question_text, options
            )
            self._save_question(
                {"type": "radio", "question": question_text, "answer": answer}
            )
            self._select_radio(radios, answer)
            return True
        return False

    def _find_and_handle_date_question(self, section: WebElement) -> bool:
        try:
            date_field = section.find_element(
                By.CLASS_NAME, "artdeco-datepicker__input"
            )
        except NoSuchElementException:
            return False

        date_input = date_field.find_element(By.XPATH, "//input[@name='artdeco-date']")
        question_text = section.text.lower()
        if "today" in question_text:
            answer_text = datetime.now().strftime("%m/%d/%Y")
            date_input.send_keys(answer_text)
            time.sleep(random.uniform(1, 15))
            return True
        if "earliest start date" in question_text:
            two_months_from_today = datetime.now() + timedelta(days=60)
            first_day_of_month = two_months_from_today.replace(day=1).strftime(
                "%m/%d/%Y"
            )
            date_input.send_keys(first_day_of_month)
            time.sleep(random.uniform(1, 15))
            return True
        return False

    def _find_and_handle_textbox_question(self, section: WebElement) -> bool:
        text_fields = section.find_elements(
            By.TAG_NAME, "input"
        ) + section.find_elements(By.TAG_NAME, "textarea")
        if text_fields:
            text_field = text_fields[0]
            try:
                question_text = (
                    section.find_element(By.TAG_NAME, "label").text.lower().strip()
                )
            except NoSuchElementException:
                return False

            if any(
                substring in question_text
                for substring in ["deselect resume", "upload cover letter"]
            ):
                return False

            is_numeric = self._is_numeric_field(text_field)
            question_type = "numeric" if is_numeric else "textbox"

            if self._sanitize_text(question_text) not in ["cover letter"]:
                for item in self.questions:
                    if (
                        self._sanitize_text(question_text) == item["question"]
                        and item.get("type") == question_type
                    ):
                        self._enter_text(text_field, item["answer"])
                        return True

            answer = (
                self.gpt_answerer.answer_question_numeric(question_text)
                if is_numeric
                else self.gpt_answerer.answer_question_textual_wide_range(question_text)
            )
            self._save_question(
                {"type": question_type, "question": question_text, "answer": answer}
            )
            self._enter_text(text_field, answer)
            return True
        return False

    def _find_and_handle_dropdown_question(self, section: WebElement) -> bool:
        try:
            form_element = section.find_element(By.CLASS_NAME, "fb-dash-form-element")
        except NoSuchElementException:
            return False

        try:
            select = form_element.find_element(By.TAG_NAME, "select")
        except NoSuchElementException:
            try:
                select = section.find_element(
                    By.CSS_SELECTOR, "[data-test-text-entity-list-form-select]"
                )
            except NoSuchElementException:
                return False

        try:
            question_text = form_element.find_element(By.TAG_NAME, "label").text.lower()
        except NoSuchElementException:
            question_text = form_element.find_element(
                By.TAG_NAME, "select"
            ).text.lower()

        select = Select(select)
        options = [option.text for option in select.options]
        current_selection = select.first_selected_option.text
        for item in self.questions:
            if (
                self._sanitize_text(question_text) == item["question"]
                and item["type"] == "dropdown"
                and item["answer"] in options
            ):
                if current_selection != item["answer"]:
                    self._select_dropdown_option(select, item["answer"])
                return True

        answer = self.gpt_answerer.answer_question_from_options(question_text, options)
        self._save_question(
            {"type": "dropdown", "question": question_text, "answer": answer}
        )
        if current_selection != answer:
            self._select_dropdown_option(select, answer)
        return True

    def _is_numeric_field(self, field: WebElement) -> bool:
        field_type = field.get_attribute("type").lower()
        field_id = field.get_attribute("id").lower()
        is_numeric = (
            "numeric" in field_id
            or field_type == "number"
            or ("text" == field_type and "numeric" in field_id)
        )
        return is_numeric

    def _enter_text(self, text_field: WebElement, text: str) -> None:
        text_field.clear()
        text_field.send_keys(text)
        time.sleep(random.uniform(1, 15))

        text_field.send_keys(Keys.ARROW_DOWN)
        text_field.send_keys(Keys.ENTER)
        time.sleep(random.uniform(1, 15))

    def _select_radio(self, radios: List[WebElement], answer: str) -> None:
        for radio in radios:
            if (
                answer
                == radio.get_attribute(
                    "data-test-text-selectable-option__input"
                ).lower()
            ):
                label_element = self.browser.find_element(
                    By.XPATH, f'//label[@for="{radio.get_attribute("id")}"]'
                )
                label_element.click()
                time.sleep(random.uniform(1, 15))
                return
        radios[-1].click()
        time.sleep(random.uniform(1, 15))

    def _select_dropdown_option(self, select: Select, text: str) -> None:
        select.select_by_visible_text(text)
        time.sleep(random.uniform(1, 15))

    def _sanitize_text(self, text: str) -> str:
        sanitized_text = text.lower().strip().replace('"', "").replace("\\", "")
        sanitized_text = (
            re.sub(r"[\x00-\x1F\x7F]", "", sanitized_text)
            .replace("\n", " ")
            .replace("\r", "")
            .rstrip(",")
        )
        return sanitized_text

    def _split_text_by_width(
        self, text: str, font_name: str, font_size: int, max_width
    ):
        wrapped_lines = []
        for line in text.splitlines():
            if self._string_width(line, font_name, font_size) > max_width:
                words = line.split()
                new_line = ""
                for word in words:
                    if (
                        self._string_width(new_line + word + " ", font_name, font_size)
                        <= max_width
                    ):
                        new_line += word + " "
                    else:
                        wrapped_lines.append(new_line.strip())
                        new_line = word + " "
            else:
                wrapped_lines.append(line)
        return wrapped_lines

    def _string_width(self, text: str, font_name: str, font_size: int):
        if not pdfmetrics.getFont(font_name):
            pdfmetrics.registerFont(TTFont(font_name, f"{font_name}.ttf"))

        c = Canvas("dummy.pdf", pagesize=A4)
        c.setFont(font_name, font_size)
        bbox = c.stringWidth(text, font_name, font_size)
        return bbox
