import json

from ai.openrouter_client import MODEL, get_client
from ai.schemas import AISkillCategorization

CATEGORIZE_PROMPT = (
    "Given this list of skills extracted from a resume, group them into clear, "
    "profession-appropriate category headings. Infer the likely profession from "
    "the skills themselves and choose headings that make sense for THAT "
    "profession specifically (e.g. a doctor's skills might group under "
    "'Clinical Skills' and 'Medical Procedures'; a chef's under 'Culinary "
    "Techniques' and 'Kitchen Management'; a developer's under 'Programming "
    "Languages' and 'Cloud Infrastructure') — do not force skills into generic "
    "categories that don't fit the profession. Every skill in the input list "
    "must appear in exactly one group, spelled exactly as given, with no "
    "additions, omissions, or edits. Return a JSON object with a 'groups' key: "
    "an array of objects each with 'category' (string) and 'skills' (array of "
    "exact skill strings from the input). Return ONLY the JSON object, no "
    "other text, no markdown code fences.\n\n"
    "Skills:\n{skills_json}"
)


def categorize_skills_ai(skills: list) -> dict:
    """Use an LLM to group a candidate's skills into profession-appropriate
    category headings inferred dynamically from the skills themselves,
    rather than picking from a fixed keyword list.

    Raises on any failure (missing API key, network error, invalid JSON, bad
    schema, or a skill list that doesn't round-trip exactly) so the caller
    can fall back to the rule-based categorizer.
    """
    if not skills:
        return {}

    client = get_client()
    completion = client.chat.completions.create(
        model=MODEL,
        max_tokens=1200,
        response_format={"type": "json_object"},
        messages=[
            {"role": "user", "content": CATEGORIZE_PROMPT.format(skills_json=json.dumps(skills))}
        ],
    )
    raw = completion.choices[0].message.content
    result = AISkillCategorization.model_validate(json.loads(raw))

    categorized = {group.category: group.skills for group in result.groups if group.skills}

    # Safety check: every input skill must appear exactly once in the output,
    # unchanged. If the model dropped, duplicated, or altered anything, don't
    # trust this result — fall back to the rule-based categorizer instead.
    input_set = {s.lower() for s in skills}
    output_list = [s for group_skills in categorized.values() for s in group_skills]
    output_set = {s.lower() for s in output_list}
    if len(output_list) != len(skills) or output_set != input_set:
        raise ValueError("AI categorization did not preserve the exact skill list.")

    return categorized
