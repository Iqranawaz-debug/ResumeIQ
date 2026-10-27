"""Shared local resume pipeline for individual and recruiter uploads."""
from fastapi import HTTPException
from parser.resume_parser import parse_resume
from extractor.extractor import extract_candidate_info
from utils.resume_checker import looks_like_resume
from utils.skills import categorize_skills
from utils import limits


def process_resume(filename, content, parser=parse_resume, checker=looks_like_resume,
                   extractor=extract_candidate_info):
    try:
        text = parser(filename, content)
    except limits.DocumentLimitError as exc:
        raise HTTPException(413, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(422, 'Could not read this file. It may be corrupted.') from exc
    valid, error = checker(text)
    if not valid:
        raise HTTPException(400, error)
    candidate = extractor(text)
    candidate['skills_by_category'] = categorize_skills(candidate.get('skills') or [])
    return candidate
