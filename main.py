"""
Main entry pojnt for the LinkedIn job application bot.
"""

import os
import time
from pathlib import Path

import yaml
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager
from webdriver_manager.microsoft import EdgeChromiumDriverManager

from src.gpt import GPTAnswerer
from src.linkedin_authenticator import LinkedinAuthenticator
from src.linkedin_job_manager import LinkedinJobManager
from src.logging_config import logger
from src.models import JobApplicationProfile, Resume

load_dotenv(override=True)


def validate_data_folder(data_folder: Path) -> tuple:
    """
    Validates the existence of the data folder and required files within it.

    Args:
        data_folder (Path): The path to the data folder.

    Returns:
        tuple: Paths to the resume.docx, config.yaml, and resume.yaml files.

    Raises:
        FileNotFoundError: If the data folder or any required file is missing.
    """
    if not data_folder.exists() or not data_folder.is_dir():
        raise FileNotFoundError(f"Data folder not found: {data_folder}")

    required_files = ["resume.docx", "config.yaml", "resume.yaml"]
    missing_files = [
        file for file in required_files if not (data_folder / file).exists()
    ]
    if missing_files:
        raise FileNotFoundError(
            f"Missing files in the data folder: {
                                ', '.join(missing_files)}"
        )

    return (
        data_folder / "resume.docx",
        data_folder / "config.yaml",
        data_folder / "resume.yaml",
    )


def validate_yaml_file(yaml_path: Path) -> dict:
    """
    Validates and loads the content of a YAML file.

    Args:
        yaml_path (Path): The path to the YAML file.

    Returns:
        dict: The content of the YAML file as a dictionary.

    Raises:
        yaml.YAMLError: If there is an error in parsing the YAML file.
    """
    with open(yaml_path, "r", encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def validate_boolean_fields(
    fields: list, parameters: dict, category: str, config_yaml_path: Path
):
    """
    Validates that specified fields in a category of parameters are boolean.

    Args:
        fields (list): The list of fields to validate.
        parameters (dict): The parameters dictionary.
        category (str): The category to validate.
        config_yaml_path (Path): The path to the configuration YAML file.

    Raises:
        ValueError: If any field is not boolean or is invalid.
    """
    for key in parameters[category].keys():
        if key not in fields:
            raise ValueError(
                f"Invalid field '{key}' in {
                category} in config file {config_yaml_path}"
            )

    for field in fields:
        if not isinstance(parameters[category].get(field), bool):
            raise ValueError(
                f"{category.capitalize()} '{
                field}' must be a boolean in config file {config_yaml_path}"
            )


def validate_string_list(parameters: dict, category: str, config_yaml_path: Path):
    """
    Validates that all items in the specified category of parameters are strings.

    Args:
        parameters (dict): The parameters dictionary.
        category (str): The category to validate.
        config_yaml_path (Path): The path to the configuration YAML file.

    Raises:
        ValueError: If any item in the category is not a string.
    """
    if not all(isinstance(item, str) for item in parameters[category]):
        raise ValueError(
            f"'{category}' must be a list of strings in config file {
            config_yaml_path}"
        )


def validate_config(config_yaml_path: Path) -> dict:
    """
    Validates the configuration file and returns the parameters.

    Args:
        config_yaml_path (Path): The path to the configuration YAML file.

    Returns:
        dict: The validated parameters from the configuration file.

    Raises:
        ValueError: If any required key is missing or has an invalid type.
    """
    parameters = validate_yaml_file(config_yaml_path)

    required_keys = {
        "experience_level": dict,
        "job_types": dict,
        "date": dict,
        "positions": list,
        "locations": list,
        "companies_blacklist": list,
        "work_types": dict,
    }

    for key, expected_type in required_keys.items():
        if key not in parameters:
            raise ValueError(
                f"Missing or invalid key '{
                key}' in config file {config_yaml_path}"
            )
        elif not isinstance(parameters[key], expected_type):
            raise ValueError(
                f"Invalid type for key '{key}' in config file {
                config_yaml_path}. Expected {expected_type}, received {type(parameters[key])}."
            )

    experience_levels = [
        "internship",
        "entry",
        "associate",
        "mid-senior level",
        "director",
        "executive",
    ]
    validate_boolean_fields(
        experience_levels, parameters, "experience_level", config_yaml_path
    )

    job_types = [
        "full-time",
        "contract",
        "part-time",
        "temporary",
        "internship",
        "other",
        "volunteer",
    ]
    validate_boolean_fields(job_types, parameters, "job_types", config_yaml_path)

    date_filters = ["all time", "month", "week", "24 hours", "12 hours", "hour"]
    validate_boolean_fields(date_filters, parameters, "date", config_yaml_path)

    work_types = ["on-site", "hybrid", "remote"]
    validate_boolean_fields(work_types, parameters, "work_types", config_yaml_path)

    validate_string_list(parameters, "positions", config_yaml_path)

    validate_string_list(parameters, "locations", config_yaml_path)

    validate_string_list(parameters, "companies_blacklist", config_yaml_path)

    return parameters


def get_browser():
    """Sets up and returns a web browser instance based on the specified environment variable."""
    logger.debug("Initializing browser setup")

    browser_name = get_env_variable("BROWSER")
    browser_options = {
        "Chrome": webdriver.ChromeOptions(),
        "Edge": webdriver.EdgeOptions(),
        "Firefox": webdriver.FirefoxOptions(),
    }

    if browser_name not in browser_options:
        raise ValueError(f"Unknown browser value '{browser_name}'.")

    options = browser_options[browser_name]
    common_args = [
        "--start-maximized",
        "--hide-crash-restore-bubble",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--ignore-certificate-errors",
        "--disable-extensions",
        "--disable-gpu",
        "window-size=1200x800",
        "--disable-background-timer-throttling",
        "--disable-backgrounding-occluded-windows",
        "--disable-translate",
        "--disable-popup-blocking",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-logging",
        "--disable-autofill",
        "--disable-plugins",
        "--disable-animations",
        "--disable-cache",
    ]
    for arg in common_args:
        options.add_argument(arg)

    if browser_name in ["Chrome", "Edge"]:
        options.add_experimental_option(
            "excludeSwitches", ["enable-automation", "enable-logging"]
        )
        options.add_experimental_option(
            "prefs",
            {
                "profile.default_content_setting_values.images": 2,
                "profile.managed_default_content_settings.stylesheets": 2,
            },
        )

    profile_path = os.path.join(os.getcwd(), "browser", browser_name.lower())
    os.makedirs(profile_path, exist_ok=True)
    logger.debug("Using browser profile directory: %s", profile_path)

    options.add_argument(f"--user-data-dir={os.path.dirname(profile_path)}")
    options.add_argument(f"--profile-directory={os.path.basename(profile_path)}")

    browser_services = {
        "Chrome": ChromeService(ChromeDriverManager().install()),
        "Edge": EdgeService(EdgeChromiumDriverManager().install()),
        "Firefox": FirefoxService(GeckoDriverManager().install()),
    }

    try:
        browser = webdriver.__dict__[browser_name](
            service=browser_services[browser_name], options=options
        )
        browser.set_page_load_timeout(600)
        return browser
    except Exception as e:
        logger.error("Failed to initialize browser: %s", e)
        raise


def get_env_variable(var_name: str) -> str:
    """
    Retrieves the value of the specified environment variable.

    Args:
        var_name (str): The name of the environment variable.

    Returns:
        str: The value of the environment variable.

    Raises:
        ValueError: If the environment variable is not set or is empty.
    """
    value = os.getenv(var_name)
    if not value:
        raise ValueError(
            f"Environment variable '{
                         var_name}' is not set or is empty."
        )
    return value


def main():
    """
    Main function to run the LinkedIn job application bot.
    """
    email = get_env_variable("LINKEDIN_EMAIL")
    password = get_env_variable("LINKEDIN_PASSWORD")
    llm_api_key = get_env_variable("LLM_API_KEY")
    model_name = get_env_variable("LLM_MODEL_NAME")

    resume_docx_path, config_file, resume_yaml_path = validate_data_folder(Path("data"))

    parameters = validate_config(config_file)
    parameters["uploads"] = {
        "resume_yaml_path": resume_yaml_path,
        "resume_docx_path": resume_docx_path,
    }
    parameters["mode"] = get_env_variable("MODE")
    parameters["database_url"] = get_env_variable("DATABASE_URL")

    with open(parameters["uploads"]["resume_yaml_path"], "r", encoding="utf-8") as file:
        resume_yaml = file.read()

    gpt_answerer = GPTAnswerer(
        model_name=model_name,
        openai_api_key=llm_api_key,
        resume=Resume(resume_yaml),
        job_application_profile=JobApplicationProfile(resume_yaml),
    )

    browser = get_browser()
    authenticator = LinkedinAuthenticator(
        browser=browser, email=email, password=password
    )
    manager = LinkedinJobManager(
        browser=browser, parameters=parameters, gpt_answerer=gpt_answerer
    )
    logger.info("Starting apply process")
    while True:
        if authenticator.login() is True:
            manager.run()
            browser.quit()

            logger.info("All done, halting.")
            total_seconds = 24 * 60 * 60
            while total_seconds > 0:
                hours = int(total_seconds // 3600)
                minutes = int((total_seconds % 3600) // 60)
                seconds = int(total_seconds % 60)
                logger.info(
                    "Time left: %d hours, %d minutes, %d seconds",
                    hours,
                    minutes,
                    seconds,
                )
                time.sleep(3600)
                total_seconds -= 3600

            browser = get_browser()
            authenticator.set_browser(browser=browser)
            manager.set_browser(browser=browser)


if __name__ == "__main__":
    os.system("cls")
    main()
