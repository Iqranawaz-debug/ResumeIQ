"""Regression coverage for defects repaired across Phases 2, 3 and 4."""

import unittest

from pydantic import ValidationError

from ai.schemas import AIMatchResult
from evaluator.scorer import calculate_total_experience_years
from extractor.extractor import extract_candidate_info
from matcher.matcher import extract_required_years, match_resume_to_job, requires_degree


class KnownDefects(unittest.TestCase):
    def test_D01_employment_gaps_are_excluded(self):
        value = {"experience": [{"duration": "2010-2011"}, {"duration": "2024-2025"}]}
        self.assertEqual(calculate_total_experience_years(value), 2)

    def test_D02_react_alias_is_recognized(self):
        result = match_resume_to_job({"skills": ["React.js"]}, "React developer")
        self.assertEqual(result["missing_skills"], [])

    def test_D03_hyphenated_range_uses_minimum(self):
        self.assertEqual(extract_required_years("Requires 3-5 years"), 3)

    def test_D04_repeated_experience_sections_are_preserved(self):
        text = "Experience\nRole A\n2020-2021\nBuilt a service.\nExperience\nRole B\n2023-2024\nBuilt another service."
        self.assertEqual(len(extract_candidate_info(text)["experience"]), 2)

    def test_D05_ai_scores_reject_values_above_100(self):
        with self.assertRaises(ValidationError):
            AIMatchResult(requirements={}, overall_score=101, match_label="Strong Match",
                          skills_score=50, experience_score=50, education_score=50,
                          experience_note="Synthetic", education_note="Synthetic")

    def test_D06_ai_scores_reject_negative_values(self):
        with self.assertRaises(ValidationError):
            AIMatchResult(requirements={}, overall_score=-1, match_label="Weak Match",
                          skills_score=50, experience_score=50, education_score=50,
                          experience_note="Synthetic", education_note="Synthetic")

    def test_D07_negated_degree_is_not_required(self):
        self.assertFalse(requires_degree("No degree required."))
