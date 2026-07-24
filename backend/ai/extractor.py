import json

from ai.openrouter_client import MODEL, get_client
from ai.schemas import AICandidate

EXTRACTION_PROMPT = (
    "Extract structured candidate info from this resume as a JSON object with "
    "exactly these keys: name (string or null), email (string or null), phone "
    "(string or null), skills (array of strings), education (array of strings, "
    "one per entry: degree, institution, year), experience (array of objects "
    "with title, duration [string or null], details [array of strings]), "
    "detected_sections (array of section names found, e.g. skills, education, "
    "experience, projects, certifications). Return ONLY the JSON object, no "
    "other text, no markdown code fences.\n\n"
    "Resume:\n{resume_text}"
)


def extract_candidate_info_ai(resume_text: str) -> dict:
    """Use an LLM (via OpenRouter) to extract structured candidate info from
    resume text.

    Raises on any failure (missing API key, network error, invalid JSON, bad
    schema) so the caller can fall back to the rule-based extractor.
    """
    client = get_client()
    completion = client.chat.completions.create(
        model=MODEL,
        max_tokens=2048,
        response_format={"type": "json_object"},
        messages=[
            {"role": "user", "content": EXTRACTION_PROMPT.format(resume_text=resume_text)}
        ],
    )
    raw = completion.choices[0].message.content
    candidate = AICandidate.model_validate(json.loads(raw))

    return {
        "name": candidate.name,
        "email": candidate.email,
        "phone": candidate.phone,
        "skills": candidate.skills,
        "education": candidate.education,
        "experience": [entry.model_dump() for entry in candidate.experience],
        "detected_sections": candidate.detected_sections,
    }
