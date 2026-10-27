"""Shared local resume pipeline for individual and recruiter uploads."""
from fastapi import HTTPException
from parser.resume_parser import parse_resume
from extractor.extractor import extract_candidate_info
from evaluator.document_checks import document_checks
from utils.resume_checker import looks_like_resume
from utils.skills import categorize_skills
from utils import limits

SCANNED_PDF = ('This PDF appears to be scanned or image-only, so no text could be read. '
               'Export a text-based PDF from your editor, or run OCR on it before uploading.')


def process_resume(filename, content, parser=parse_resume, checker=looks_like_resume,
                   extractor=extract_candidate_info):
    stats = {}
    try:
        text = parser(filename, content, stats=stats)
    except limits.DocumentLimitError as exc:
        raise HTTPException(413, str(exc)) from exc
    except limits.UnreadableDocument as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(422, 'Could not read this file. It may be corrupted; try re-saving or re-exporting it.') from exc
    if not (text or '').strip() and stats.get('image_only_pages'):
        raise HTTPException(400, SCANNED_PDF)
    valid, error = checker(text)
    if not valid:
        raise HTTPException(400, error)
    candidate = extractor(text)
    candidate['skills_by_category'] = categorize_skills(candidate.get('skills') or [])
    candidate['document_checks'] = document_checks(stats, text, candidate)
    return candidate
