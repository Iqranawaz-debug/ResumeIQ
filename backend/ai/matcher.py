import json

from ai.openrouter_client import MODEL, get_client
from ai.schemas import AIMatchResult

MATCH_PROMPT = (
    "You are screening a candidate against a job description. Return a JSON "
    "object with exactly these keys:\n"
    "- requirements: object with required_skills (array of strings), "
    "min_years_experience (integer or null), degree_required (boolean) — "
    "extracted from the job description.\n"
    "- overall_score (integer 0-100): weighted judgment, skills matter most, "
    "then experience, then education.\n"
    "- match_label: exactly one of 'Strong Match', 'Partial Match', 'Weak Match'.\n"
    "- skills_score, experience_score, education_score (integers 0-100 each).\n"
    "- matched_skills, missing_skills (arrays of strings) — recognize "
    "equivalent or implied skills, not just exact keyword matches (e.g. "
    "'infrastructure as code' experience can reasonably satisfy a 'Terraform' "
    "requirement).\n"
    "- experience_note, education_note (short strings explaining the score).\n"
    "Return ONLY the JSON object, no other text, no markdown code fences.\n\n"
    "Candidate:\n{candidate_json}\n\n"
    "Job description:\n{job_description}"
)


def match_resume_to_job_ai(candidate: dict, job_description: str) -> dict:
    """Use an LLM (via OpenRouter) to extract the job's requirements and
    semantically score the candidate's fit against them.

    Raises on any failure so the caller can fall back to the rule-based
    matcher.
    """
    client = get_client()
    completion = client.chat.completions.create(
        model=MODEL,
        max_tokens=1200,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "user",
                "content": MATCH_PROMPT.format(
                    candidate_json=json.dumps(candidate),
                    job_description=job_description,
                ),
            }
        ],
    )
    raw = completion.choices[0].message.content
    result = AIMatchResult.model_validate(json.loads(raw))

    return {
        "overall_score": result.overall_score,
        "match_label": result.match_label,
        "skills_score": result.skills_score,
        "matched_skills": result.matched_skills,
        "missing_skills": result.missing_skills,
        "experience_score": result.experience_score,
        "experience_note": result.experience_note,
        "education_score": result.education_score,
        "education_note": result.education_note,
        "extracted_requirements": result.requirements.model_dump(),
    }
