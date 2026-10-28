# Phase 4: explainable matching

## Pipeline map (before implementation)

Authenticated upload -> bounded PDF/DOCX parsing -> deterministic candidate
and skill extraction -> local skill categories -> per-user in-memory candidate.
Analyze uses that candidate and optional parsed JD. Resume quality is contact
10 + skills 25 + education 20 + experience/details 45. Projects affect the
radar's presence indicator, not employment tenure or a separate scoring term.

With a JD, analyzer tries the existing provider matcher first. Its score and
component judgments are NOT governed by a verifiable weighted formula. On
failure local matching uses 60% skills, 25% experience, 15% education, rounded;
no detected skills returns 35. Overall blends 30% quality and 70% job fit,
rounded, capped at 49 for Weak Match. Without a JD, quality is the score.
Recommendation bands are 85/70/50; match bands 80/50. Phase 3 interval union
supplies tenure. Education is only a presence check, not degree verification.
History stores five summary records, not full candidate/explanation objects.

## Root causes and preservation strategy

The matcher canonicalizes JD vocabulary but only lowercases resume skills.
Its second substring matcher can bypass punctuation/ambiguous-word safeguards.
Hyphenated year ranges use the upper bound; degree negation is ignored.
No source evidence or arithmetic provenance reaches the results UI.

Keep existing formulas, constants, rounding, provider selection and schemas.
Fix demonstrated matching defects only. Explanations consume actual scorer
outputs and matcher inputs, never calculate a replacement score. Required vs
preferred is display metadata, with equal treatment under existing scoring.
Preserve the AI path under the specification's explicit compatibility fallback:
label its judgments as unverifiable, do not claim local component weights
explain them, and verify skill evidence locally without changing their score.
No new provider requests or expansion of the provider privacy allowlist.

## Implementation

`analyze_resume_for_job` adds an optional `explanation` object after its existing
evaluation. It contains the overall score/scale/source, real quality points,
local job components where available, the actual blend before and after the
weak-fit cap, requirement rows, evidence, tenure/education rules, limitations
and conditional recommendations. The quality explanation calls the existing
`calculate_score_components`; job components are exposed by the existing
matcher. The analyzer captures the actual rounded result before its cap.
There is no second scoring engine and no explanation-driven score assignment.

Canonical skill normalization applies NFKC, harmless whitespace/soft-hyphen
cleanup and the shared alias table on both sides. Bounded vocabulary matching
preserves C++, C#, .NET and Node.js and rejects Java inside JavaScript. Ordinary
uses such as “react to incidents” and “go beyond expectations” are suppressed.
Go/golang is added as a spelling alias with ordinary-word guards. Candidate-only
unknown skills remain supported through bounded exact matching. Unknown prose
does not become a new requirement. Context headings include required skills,
technical requirements, minimum qualifications, preferred qualifications,
responsibilities, nice to have, experience required and education requirements.
Wrapped headings and vocabulary phrases are supported. Context is metadata,
not a different weight; a skill occurring in multiple contexts lists them.

### Exact preservation and narrow exceptions

- **Weights unchanged:** quality 10/25/20/45; local fit 60/25/15; overall 30/70.
- **Thresholds unchanged:** recommendation 85/70/50; fit 80/50; weak-fit cap 49.
- **Formulas and rounding unchanged:** same Python `round`, 0–100 scales and
  no-skill fallback of 35. Constants name the existing literal weights.
- Phase 3 elapsed-month interval union and uncertainty rules are untouched.
- Education still earns presence credit even for incomplete education text.
  Explanations explicitly say this does not verify completion or equivalence.
- Existing AI-first selection and provider scores remain authoritative on that
  path. Their score arithmetic is unknowable, so no component attribution is
  fabricated. Local requirement evidence is clearly separate from that score.
- Intentional score changes are limited to corrected inputs: canonical aliases,
  bounded/ambiguous-word matching, minimum of hyphenated integer year ranges,
  and explicit “no degree required”/“degree not required” negation. Bounded degree
  terms also avoid accidental substring requirements such as “mastery”.
- Legacy response keys/types remain; recognized skill strings are now canonical
  lowercase in local matching. Display spelling/case can therefore differ.

### Before and after examples

| Synthetic input | Before | After |
|---|---|---|
| Resume React.js; JD React | Skill missed, local skill component 0 | Canonical match, skill component 100 |
| Resume sklearn; JD Scikit-learn | Alias could be missed | Canonical match |
| Resume C; JD C++ | Candidate-only substring path could match C | C is not C++ |
| Resume React; JD “react to incidents” | Could match the verb | No technical React requirement inferred |
| JD “3-5 years” | Minimum extracted as 5 | Minimum extracted as 3 |
| JD “No degree required” | Degree requirement detected | Explicit negation respected |

Changing a recognized skill or requirement can change the fit and overall score;
this is a corrected match input, not a change to weights or thresholds.

## Evidence and privacy

Candidate extraction adds optional `skill_evidence`. Only short excerpts that
are **exact substrings of the parsed resume text** are retained, with section
and zero-based employment/project entry index. Skills-section lines can also
support listed-skill evidence. At most two excerpts per canonical skill are
stored, each at most 240 characters. Longer sentences, transformed wrapped
text that is no longer an exact substring, contact-bearing passages and
explicit sensitive-attribute passages are omitted rather than rewritten.
The complete parsed document is not retained for explanations.

At analysis time skill presence, privacy checks and employment/project entry
ownership are rechecked. Old candidates without quotations report “Source
quotation unavailable”; a listed-skill match is distinguished from proof of
proficiency. For example:

```text
JD: FastAPI
Resume experience entry 1: Built services using Python and FastAPI.
Result: matched by canonical extracted skill list
Evidence: "Built services using Python and FastAPI."
Source: experience entry 1
```

For Docker without supporting extracted skill information, the result is
“Not evidenced in resume” with no fabricated quote. Its recommendation starts
“If you have used docker, describe that work…” rather than instructing the
candidate to claim it. Empty project/employment descriptions and uncertain
dates receive factual clarification suggestions. Formatting/achievement
claims are not inferred. Local narrative was changed to describe observable
document content rather than assert relevance, proficiency or graduation.

No new external calls were added. The existing provider allowlist is unchanged:
skills, education, and employment title/duration/details only. Organizations,
projects and `skill_evidence` are excluded. Explanations are per-candidate,
computed inside the existing authenticated, resume-ID-checked workflow.
History remains summary-only. Tests isolate account storage before importing
the API and use synthetic data and mocked providers only. React text rendering
escapes document/provider content; no unsafe HTML or instruction execution is
introduced. Filtering is best effort, not guaranteed de-identification.

## API and interface compatibility

No routes, authentication handlers, upload validation, history schema, or error
responses were changed. `/api/analyze` still returns `analysis` and `history`.
`analysis.explanation` is additive; `/api/upload` gains only the additive
candidate `skill_evidence` field. The internal matcher adds `match_inputs` and
`score_components`. The existing `extracted_requirements` field is preserved.
Old analyses without explanations show an unavailable state and retain their
legacy presentation. No migration or dependency installation is required.

The new React results component uses the current theme, typography and classes.
It shows completeness points, actual local weighted components, the blend and
cap, matched/not-evidenced requirements, JD context, quotations, conditional
recommendations and limitations. Its responsive grid and wrapping avoid fixed
content widths. Progress bars represent actual component values only.
Provider narrative and unverifiable matches are labelled; advisory score bands
retain their existing values. The same component is included in print output,
and text downloads include explanation/evidence. The four-step flow is intact.

## Files changed in Phase 4

| File | Purpose |
|---|---|
| `backend/utils/skills.py` | Shared canonicalization and bounded contextual matcher |
| `backend/utils/constants.py` | Go/golang spelling alias |
| `backend/matcher/requirements.py` (new) | Deduplicated JD skills and heading context |
| `backend/matcher/matcher.py` | Matching defects; expose actual inputs/components |
| `backend/extractor/evidence.py` (new) | Bounded source-verified local quotations |
| `backend/extractor/extractor.py` | Attach optional evidence during extraction |
| `backend/evaluator/explanation.py` (new) | Read-only explanations and grounded recommendations |
| `backend/evaluator/analyzer.py` | Attach explanations, capture real pre-cap blend |
| `backend/evaluator/recommendation.py` | Remove unsupported local narrative assertions |
| `backend/tests/test_phase4.py` (new) | 32 offline matching/scoring/evidence/API/privacy tests |
| `backend/tests/test_known_defects.py` | Graduate D02, D03 and D07 to normal regressions |
| `backend/tests/test_skills.py` | Accept additive evidence key; preserve skill assertions |
| `frontend/src/ExplainableResults.jsx` (new) | Reusable results explanation component |
| `frontend/src/App.jsx` | Results integration, advisory labels and text export |
| `frontend/src/App.css` | Responsive evidence layout using existing theme |
| `frontend/src/PrintableReport.jsx` | Include explanations in print output |
| `frontend/tests/explanation.test.js` (new) | 8 rendering/compatibility/security/layout checks |
| `README.md` | Current processing/privacy description and report link |
| `docs/phase4-explainable-matching.md` (new) | This report |

All other modified/untracked files shown by Git predate this phase and were
preserved. No AI adapter/privacy/schema, auth, main API or parser code was
changed in Phase 4.

## Verification

| Check | Result |
|---|---|
| New Phase 4 backend tests | **32 passed** |
| Targeted Phase 4 + skills + Phase 3 + baseline + known defects | **118 passed; 149 passing subtests; 0 xfailed** |
| Full backend unittest discovery | **135 total: 121 passed, 14 failed, 0 expected failures** |
| Frontend Node tests | **15 passed** (8 new, 7 existing) |
| Frontend lint | Passed |
| Production build | Passed, no build warnings |
| Git whitespace check | Passed; existing LF/CRLF conversion notices only |

Compared with Phase 3's 86 passes / 14 failures / 3 expected failures, the 32
new tests pass and all three expected failures now pass as repaired regressions.
The same 14 async security tests fail before their bodies during Windows asyncio
socketpair initialization: their existing `socket.socket.connect` mock raises
`AssertionError: External effects forbidden`. They were not edited, suppressed
or skipped. There are no detected new test regressions, but these failures
prevent a fully green backend suite and do not verify their test bodies.

Existing Phase 3 in-memory upload/analysis/history tests and new direct endpoint
tests cover response contracts, per-user isolation, invalid resume IDs, legacy
history, unauthenticated rejection, valid session authentication and logout.
Their asynchronous operations run in memory with the thread-pool boundary
inline; these are not HTTP transport or browser end-to-end tests.
Frontend tests compile the real JSX with the already installed Vite compiler
and render it with React's server renderer. They test actual output, escaping,
empty/legacy states and source-level responsive/navigation wiring. No browser
viewport or visual inspection is claimed.

Commands (backend/frontend working directory respectively):

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_phase4.py -q
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
node --test tests/*.test.js
npm run lint
npm run build
```

Targeted pytest used the existing global pytest package from
`C:/Users/iqran/AppData/Roaming/Python/Python314/site-packages` on the venv's
import path, as in Phase 3. No packages, frameworks or lockfiles changed.

## Remaining limitations

The requirement to make deterministic scoring primary conflicts with preserving
the existing successful-AI scoring behavior. Under the user's explicit fallback
instruction, the latter was preserved and documented. Making local scores
authoritative on every request is a separate scoring-policy change. AI prose
may still contain unsupported judgments despite being labelled unverified.

Education presence is not a qualification verifier. Role relevance, skill
proficiency, and complete JD semantics cannot be established by bounded keyword
rules. Unusual negations, unknown headings, ambiguous ordinary words, fractional
years and unstated requirements are not robustly understood. Only recognized
heading contexts are classified; required and preferred skills retain the same
existing weights. Wrapped source text sometimes cannot supply a verbatim quote.
Short exact quotations and redaction checks reduce exposure but cannot guarantee
removal of all identifying details. Existing in-memory retention limitations
remain; no deletion or persistence policy was added. Phase 3 layout/OCR and
date-precision limitations also remain.

All work stays local and unstaged on `feature/resumeiq-redesign`. No commits,
pushes, merges, pull requests, branch changes, dependency upgrades or real
candidate documents were used.
