from dataclasses import dataclass
from typing import List, Dict, Optional, Union
import yaml
from pydantic import EmailStr, HttpUrl


@dataclass
class PersonalInformation:
    name: Optional[str]
    surname: Optional[str]
    date_of_birth: Optional[str]
    country: Optional[str]
    city: Optional[str]
    address: Optional[str]
    zip_code: Optional[int]
    phone_prefix: Optional[str]
    phone: Optional[str]
    email: Optional[EmailStr]
    github: Optional[HttpUrl] = None
    linkedin: Optional[HttpUrl] = None


@dataclass
class EducationDetails:
    education_level: Optional[str]
    institution: Optional[str]
    field_of_study: Optional[str]
    final_evaluation_grade: Optional[str]
    education_period: Optional[str]
    city: Optional[str]


@dataclass
class ExperienceDetails:
    position: Optional[str]
    company: Optional[str]
    employment_period: Optional[str]
    location: Optional[str]
    industry: Optional[str]
    key_responsibilities: Optional[List[Dict[str, str]]] = None
    skills_acquired: Optional[List[str]] = None


@dataclass
class Project:
    name: Optional[str]
    description: Optional[str]
    link: Optional[HttpUrl] = None


@dataclass
class Achievement:
    name: Optional[str]
    description: Optional[str]


@dataclass
class Certifications:
    name: Optional[str]
    description: Optional[str]


@dataclass
class Language:
    language: Optional[str]
    proficiency: Optional[str]


@dataclass
class Availability:
    notice_period: Optional[str]


@dataclass
class SalaryExpectations:
    salary_range_usd: Optional[str]


@dataclass
class SelfIdentification:
    gender: Optional[str]
    pronouns: Optional[str]
    veteran: Optional[bool]
    disability: Optional[bool]
    ethnicity: Optional[str]


@dataclass
class LegalAuthorization:
    eu_work_authorization: Optional[bool]
    us_work_authorization: Optional[bool]
    requires_us_visa: Optional[bool]
    requires_us_sponsorship: Optional[bool]
    requires_eu_visa: Optional[bool]
    legally_allowed_to_work_in_eu: Optional[bool]
    legally_allowed_to_work_in_us: Optional[bool]
    requires_eu_sponsorship: Optional[bool]


@dataclass
class WorkPreferences:
    remote_work: Optional[bool]
    in_person_work: Optional[bool]
    open_to_relocation: Optional[bool]
    willing_to_complete_assessments: Optional[bool]
    willing_to_undergo_drug_tests: Optional[bool]
    willing_to_undergo_background_checks: Optional[bool]


@dataclass
class Resume:
    personal_information: Optional[PersonalInformation] = None
    education_details: Optional[List[EducationDetails]] = None
    experience_details: Optional[List[ExperienceDetails]] = None
    projects: Optional[List[Project]] = None
    achievements: Optional[List[Achievement]] = None
    certifications: Optional[List[Certifications]] = None
    languages: Optional[List[Language]] = None
    interests: Optional[List[str]] = None
    self_identification: Optional[SelfIdentification] = None
    legal_authorization: Optional[LegalAuthorization] = None

    def __init__(self, yaml_str: str):
        data = yaml.safe_load(yaml_str)
        self.personal_information = PersonalInformation(
            **data.get("personal_information", {}))
        self.education_details = [EducationDetails(
            **edu) for edu in data.get("education_details", [])]
        self.experience_details = [ExperienceDetails(
            **exp) for exp in data.get("experience_details", [])]
        self.projects = [Project(**proj) for proj in data.get("projects", [])]
        self.achievements = [Achievement(**ach)
                             for ach in data.get("achievements", [])]
        self.certifications = [Certifications(
            **cert) for cert in data.get("certifications", [])]
        self.languages = [Language(**lang)
                          for lang in data.get("languages", [])]
        self.interests = data.get("interests", [])
        self.self_identification = SelfIdentification(
            **data.get("self_identification", {}))
        self.legal_authorization = LegalAuthorization(
            **data.get("legal_authorization"))


@dataclass
class Job:
    title: str
    company: str
    location: str
    link: str
    apply_method: str = ""
    recruiter: str = ""
    id: str = ""
    description: str = ""
    applied: bool = False
    connected: str = False

    def set_job_description(self, description):
        self.description = description

    def set_recruiter(self, recruiter):
        self.recruiter = recruiter


@dataclass
class JobApplicationProfile:
    self_identification: SelfIdentification
    legal_authorization: LegalAuthorization
    work_preferences: WorkPreferences
    availability: Availability
    salary_expectations: SalaryExpectations

    def __init__(self, yaml_str: str):
        data = yaml.safe_load(yaml_str)
        self.self_identification = SelfIdentification(
            **data['self_identification'])
        self.legal_authorization = LegalAuthorization(
            **data['legal_authorization'])
        self.work_preferences = WorkPreferences(**data['work_preferences'])
        self.availability = Availability(**data['availability'])
        self.salary_expectations = SalaryExpectations(
            **data['salary_expectations'])
