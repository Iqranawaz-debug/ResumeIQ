# Skill extraction and categorization — 21 October 2026

## Scope and root cause

The original Skills-section path split text on delimiters and accepted every
fragment. Unrecognized headings let project prose bleed into that section. It
also skipped whole-resume recognition whenever the Skills section was nonempty.
Slash splitting broke compound technical terms. Category substring matching could
select a short term before a more specific one, and upload-time AI categorization
could override the local category taxonomy.

This fix keeps the existing API object shape, frontend, parsers, identity logic,
education/experience extraction, scoring weights, and matching business rules.
Existing uncommitted Phase 1/2 changes were preserved. No dependencies were
installed/upgraded and no commits, pushes, merges, or PRs were made.

## Implementation

- Extract only recognized vocabulary terms, prioritizing all recognized Skills
  sections, then supplementing with technologies elsewhere in the resume.
- Canonical aliases include sklearn, NLP, REST APIs, React.js, NodeJS, and dotnet.
- Preserve C++, C#, .NET, Node.js, CI/CD, IDS/IPS, and hyphenated names.
- Match bounded phrases, prefer the longest overlapping term, and deduplicate.
- Normalize Unicode, soft hyphens, and wrapped phrases without fuzzy OCR guesses.
  Bullet boundaries cannot accidentally join two separate list items into a skill.
- Keep the JD helper's lowercase output contract while recognizing the same aliases.
- Expand technical vocabulary and separate programming, databases, AI, data
  engineering, cloud/DevOps, testing/automation, and development tools. Preserve
  existing nontechnical domain categories.
- Upload extraction and categorization now run locally even when AI is configured.
  Job-description AI matching remains unchanged. Existing AI categorizer code is
  retained but no longer called by upload. Method metadata correctly says rule-based.
- Category consumers use Object.entries, so category-label changes need no frontend
  modifications. Skills remain string arrays and categories remain maps of arrays.

## Files changed for this task

- `backend/extractor/extractor.py`: skills-only extraction path.
- `backend/utils/skills.py`: recognition, normalization, categorization.
- `backend/utils/constants.py`: vocabulary, aliases, display names, taxonomy.
- `backend/main.py`: local upload categorization and accurate method metadata.
- `backend/tests/test_skills.py`: 22 new synthetic tests, pytest/unittest compatible.
- `backend/tests/test_security.py`: two provider mock targets updated to the retained
  AI module because upload no longer imports/calls that provider function.
- This report.

## Examples

Previously, the Skills-section path could return each complete fragment below.

| Input | Corrected skills |
| --- | --- |
| with local SQLite user accounts. | SQLite |
| FEATURED PROJECTS (CURRENT WORK) | None |
| Automation that renames screenshots from their OCR content | OCR |
| safe dry-run mode and a pytest suite. | Pytest |
| sklearn, NLP, REST APIs | Scikit-learn, Natural Language Processing, REST API |
| SQL Server, Python Automation, Tesseract OCR | Same three compound names |

## Verification

- New tests: **22 passed**.
- Targeted pytest run (new tests + baseline + known defects): **52 passed,
  5 expected failures**, plus 69 passing subtests.
- Full unittest discovery: **74 tests; 55 passed, 14 failed, 5 expected failures**.
  All 14 failures also occurred before this task: `test_security` patches
  `socket.socket.connect`, blocking Windows asyncio's internal socketpair setup.
  Those unrelated test-harness failures were not suppressed or fixed.
- Frontend `npm run lint`: passed without warnings.
- Frontend `npm run build`: passed without warnings.
- No real resumes, account records, credentials, or external AI calls were used.

Standard backend command from `backend/`:

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -v
.venv/Scripts/python.exe -m unittest discover -s tests -p test_skills.py -v
```

Pytest 9.1.1 already existed in this machine's user Python installation, but not
inside the backend virtual environment. Running system Python alone could not
import python-docx. The successful pytest run used the virtual-environment Python
and appended the existing user site-packages path (after its own packages), with
no installation or changes to dependencies:

```powershell
.venv/Scripts/python.exe -c "import sys; sys.path.append('C:/Users/iqran/AppData/Roaming/Python/Python314/site-packages'); import pytest; raise SystemExit(pytest.main(['tests/test_skills.py', 'tests/test_baseline.py', 'tests/test_known_defects.py', '-q']))"
```

That runner path is machine-specific. In an environment with pytest and the backend
requirements installed together, use `python -m pytest` with the same test paths.

## Limitations

This is a conservative vocabulary recognizer, not a proof of proficiency. Unknown
skills are omitted rather than accepting arbitrary prose; extend the curated
vocabulary for additional specialties. Ambiguous lowercase words such as react,
rust, and excel need a structured Skills section, while capitalized technical names
are recognized in prose. Semantic negation, ambiguous capitalized words, and severe
OCR corruption remain limitations. Scanned images still require OCR upstream.

Improved evidence can change skill counts and resulting scores; scoring weights
and thresholds were not modified. Direct matcher callers supplying unnormalized
legacy skills can still hit the existing React.js expected failure. Experience gaps,
year ranges, repeated experience sections, and degree negation remain existing
expected failures. This focused fix does not certify the unfinished Phase 2 work.
