from typing import Literal, Optional

from pydantic import BaseModel


class AIExperienceEntry(BaseModel):
    title: str
    duration: Optional[str] = None
    details: list[str] = []


class AICandidate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    skills: list[str] = []
    education: list[str] = []
    experience: list[AIExperienceEntry] = []
    detected_sections: list[str] = []


class AIRequirements(BaseModel):
    required_skills: list[str] = []
    min_years_experience: Optional[int] = None
    degree_required: bool = False


class AIMatchResult(BaseModel):
    requirements: AIRequirements
    overall_score: int
    match_label: Literal["Strong Match", "Partial Match", "Weak Match"]
    skills_score: int
    matched_skills: list[str] = []
    missing_skills: list[str] = []
    experience_score: int
    experience_note: str
    education_score: int
    education_note: str
