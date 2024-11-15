import os
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from src.models import Resume
from src.gpt import GPTAnswerer
from src.linkedIn_authenticator import LinkedInAuthenticator
from src.linkedIn_job_manager import LinkedInJobManager
from src.models import JobApplicationProfile
import yaml
from src.logging_config import logger
import time
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.firefox import GeckoDriverManager
from dotenv import load_dotenv
load_dotenv(override=True)


def validate_data_folder(data_folder: Path) -> tuple:
    if not data_folder.exists() or not data_folder.is_dir():
        raise FileNotFoundError(
            f"Data folder not found: {data_folder}")

    required_files = ['resume.docx', 'config.yaml', 'resume.yaml']
    missing_files = [file for file in required_files if not (
        data_folder / file).exists()]
    if missing_files:
        raise FileNotFoundError(f"Missing files in the data folder: {
                                ', '.join(missing_files)}")

    return (data_folder / 'resume.docx', data_folder / 'config.yaml', data_folder / 'resume.yaml')


def validate_yaml_file(yaml_path: Path) -> dict:
    with open(yaml_path, 'r') as stream:
        return yaml.safe_load(stream)


def validate_boolean_fields(fields: list, parameters: dict, category: str, config_yaml_path: Path):
    for key in parameters[category].keys():
        if key not in fields:
            raise ValueError(f"Invalid field '{key}' in {
                category} in config file {config_yaml_path}")

    for field in fields:
        if not isinstance(parameters[category].get(field), bool):
            raise ValueError(f"{category.capitalize()} '{
                field}' must be a boolean in config file {config_yaml_path}")


def validate_string_list(parameters: dict, category: str, config_yaml_path: Path):
    if not all(isinstance(item, str) for item in parameters[category]):
        raise ValueError(f"'{category}' must be a list of strings in config file {
            config_yaml_path}")


def validate_config(config_yaml_path: Path) -> dict:
    parameters = validate_yaml_file(config_yaml_path)

    required_keys = {
        'experience_level': dict,
        'job_types': dict,
        'date': dict,
        'positions': list,
        'locations': list,
        'companies_blacklist': list,
        'work_types': dict
    }

    for key, expected_type in required_keys.items():
        if key not in parameters:
            raise ValueError(f"Missing or invalid key '{
                key}' in config file {config_yaml_path}")
        elif not isinstance(parameters[key], expected_type):
            raise ValueError(f"Invalid type for key '{key}' in config file {
                config_yaml_path}. Expected {expected_type}, received {type(parameters[key])}.")

    experience_levels = ['internship', 'entry', 'associate',
                         'mid-senior level', 'director', 'executive']
    validate_boolean_fields(
        experience_levels, parameters, 'experience_level', config_yaml_path)

    job_types = ['full-time', 'contract', 'part-time',
                 'temporary', 'internship', 'other', 'volunteer']
    validate_boolean_fields(
        job_types, parameters, 'job_types', config_yaml_path)

    date_filters = ['all time', 'month', 'week', '24 hours']
    validate_boolean_fields(
        date_filters, parameters, 'date', config_yaml_path)

    work_types = ['on-site', 'hybrid', 'remote']
    validate_boolean_fields(
        work_types, parameters, 'work_types', config_yaml_path)

    validate_string_list(
        parameters, 'positions', config_yaml_path)

    validate_string_list(
        parameters, 'locations', config_yaml_path)

    validate_string_list(
        parameters, 'companies_blacklist', config_yaml_path)

    return parameters


def get_browser():
    logger.debug("Setting browser options")
    browser_name = get_env_variable('BROWSER')
    if browser_name == 'Chrome':
        options = webdriver.ChromeOptions()
    elif browser_name == 'Edge':
        options = webdriver.EdgeOptions()
    elif browser_name == 'Firefox':
        options = webdriver.FirefoxOptions()
    else:
        raise ValueError(f"Unknown browser value '{browser_name}'.")

    options.add_argument("--start-maximized")
    options.add_argument("--hide-crash-restore-bubble")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-gpu")
    options.add_argument("window-size=1200x800")
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-backgrounding-occluded-windows")
    options.add_argument("--disable-translate")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--disable-logging")
    options.add_argument("--disable-autofill")
    options.add_argument("--disable-plugins")
    options.add_argument("--disable-animations")
    options.add_argument("--disable-cache")

    if browser_name in ['Chrome', 'Edge']:
        options.add_experimental_option(
            "excludeSwitches", ["enable-automation", "enable-logging"])
        options.add_experimental_option("prefs", {
            "profile.default_content_setting_values.images": 2,
            "profile.managed_default_content_settings.stylesheets": 2,
        })

    profile_path = os.path.join(
        os.getcwd(), "browser", "linkedin")
    if not os.path.exists(profile_path):
        os.makedirs(profile_path)
    logger.debug("Using browser profile directory: %s", profile_path)
    initial_path = os.path.dirname(profile_path)
    profile_dir = os.path.basename(profile_path)
    options.add_argument('--user-data-dir=' + initial_path)
    options.add_argument("--profile-directory=" + profile_dir)

    if browser_name == 'Chrome':
        browser = webdriver.Chrome(service=ChromeService(
            ChromeDriverManager().install()), options=options)
    elif browser_name == 'Edge':
        browser = webdriver.Edge(service=EdgeService(
            EdgeChromiumDriverManager().install()), options=options)
    elif browser_name == 'Firefox':
        browser = webdriver.Firefox(service=FirefoxService(
            GeckoDriverManager().install()), options=options)

    return browser


def get_env_variable(var_name: str) -> str:
    value = os.getenv(var_name)
    if not value:
        raise ValueError(f"Environment variable '{
                         var_name}' is not set or is empty.")
    return value


def main():
    email = get_env_variable('LINKEDIN_EMAIL')
    password = get_env_variable('LINKEDIN_PASSWORD')
    llm_api_key = get_env_variable('LLM_API_KEY')
    model_name = get_env_variable('LLM_MODEL_NAME')

    resume_docx_path, config_file, resume_yaml_path = validate_data_folder(
        Path("data"))

    parameters = validate_config(config_file)
    parameters['uploads'] = {
        'resume_yaml_path': resume_yaml_path,
        'resume_docx_path': resume_docx_path
    }
    parameters['mode'] = get_env_variable('MODE')
    parameters['database_url'] = get_env_variable('DATABASE_URL')

    with open(parameters['uploads']['resume_yaml_path'], "r", encoding='utf-8') as file:
        resume_yaml = file.read()

    gpt_answerer = GPTAnswerer(model_name=model_name, openai_api_key=llm_api_key,
                               resume=Resume(resume_yaml), job_application_profile=JobApplicationProfile(resume_yaml))

    browser = get_browser()
    authenticator = LinkedInAuthenticator(
        browser=browser, email=email, password=password)
    manager = LinkedInJobManager(browser=browser, parameters=parameters,
                                 gpt_answerer=gpt_answerer)
    logger.info("Starting apply process")
    while True:
        if authenticator.login() == True:
            manager.run()
            browser.quit()

            logger.info("All done, halting.")
            total_seconds = 4 * 60 * 60
            while (total_seconds > 0):
                hours = int(total_seconds // 3600)
                minutes = int((total_seconds % 3600) // 60)
                seconds = int(total_seconds % 60)
                logger.info(f"Time left: {hours} hours, {
                            minutes} minutes, {seconds} seconds")
                time.sleep(3600)
                total_seconds -= 3600

            browser = get_browser()
            authenticator.set_browser(browser=browser)
            manager.set_browser(browser=browser)


if __name__ == "__main__":
    os.system('cls')
    main()
