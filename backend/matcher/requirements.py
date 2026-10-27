"""JD context is descriptive metadata, not a new weighting policy."""
import re
from utils.skills import matching_skills

HEADINGS = {
    'required skills': 'required', 'technical requirements': 'required',
    'minimum qualifications': 'required', 'experience required': 'required',
    'education requirements': 'required', 'requirements': 'required',
    'preferred qualifications': 'preferred', 'preferred skills': 'preferred',
    'nice to have': 'preferred', 'nice-to-have': 'preferred',
    'responsibilities': 'responsibilities',
}


def skill_requirements(text, extra_skills=()):
    context, result = 'unspecified', {}
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index].strip().strip('•*- ')
        heading, separator, remainder = line.partition(':')
        normalized = heading.casefold().strip()
        if normalized in HEADINGS:
            context = HEADINGS[normalized]
            line = remainder if separator else ''
        elif index + 1 < len(lines) and (line + ' ' + lines[index + 1].strip()).casefold().rstrip(':') in HEADINGS:
            context = HEADINGS[(line + ' ' + lines[index + 1].strip()).casefold().rstrip(':')]
            index += 1
            line = ''
        elif line.endswith(':'):
            context = 'unspecified'
        # Preserve wrapped vocabulary phrases, without crossing a heading/bullet.
        if line and index + 1 < len(lines):
            following = lines[index + 1].strip()
            if following and not re.match(r'^[•*-]', following) and following.split(':')[0].casefold().strip() not in HEADINGS and not following.endswith(':'):
                combined = matching_skills(line + '\n' + following, extra_skills)
            else:
                combined = []
        else:
            combined = []
        for skill in matching_skills(line, extra_skills) + combined:
            contexts = result.setdefault(skill, [])
            if context not in contexts:
                contexts.append(context)
        index += 1
    return [{'skill': skill, 'contexts': contexts} for skill, contexts in result.items()]
