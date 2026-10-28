from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator
from matcher.matcher import determine_match_label


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


class AISkillCategoryGroup(BaseModel):
    category: str
    skills: list[str] = []


class AISkillCategorization(BaseModel):
    groups: list[AISkillCategoryGroup] = []


class AIMatchResult(BaseModel):
    requirements: AIRequirements
    overall_score: int = Field(ge=0, le=100, strict=True)
    match_label: Literal["Strong Match", "Partial Match", "Weak Match"]
    skills_score: int = Field(ge=0, le=100, strict=True)
    matched_skills: list[str] = []
    missing_skills: list[str] = []
    experience_score: int = Field(ge=0, le=100, strict=True)
    experience_note: str
    education_score: int = Field(ge=0, le=100, strict=True)
    education_note: str
    strengths: list[str] = []
    suggestions: list[str] = []
    weaknesses: list[str] = []
    interview_questions: list[str] = []

    @model_validator(mode="after")
    def consistent_match(self):
        if self.match_label != determine_match_label(self.overall_score):
            raise ValueError("Match label contradicts score")
        matched = {s.casefold() for s in self.matched_skills}
        missing = {s.casefold() for s in self.missing_skills}
        required = {s.casefold() for s in self.requirements.required_skills}
        if matched & missing or not (matched | missing).issubset(required):
            raise ValueError("Inconsistent skill evidence")
        return self
