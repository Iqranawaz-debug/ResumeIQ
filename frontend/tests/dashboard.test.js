import { test } from 'node:test'
import assert from 'node:assert/strict'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { loadComponent } from './load-component.mjs'
import { formatDelta, hasPlaceholder, retentionText, scoreSources, summaryHighlights, groupRequirements } from '../src/resultsModel.js'

const { default: ResultsDashboard } = await loadComponent('ResultsDashboard')
const { default: ScoreSummary } = await loadComponent('ScoreSummary')
const { default: RequirementMatrix } = await loadComponent('RequirementMatrix')
const { default: ScoreImpact } = await loadComponent('ScoreImpact')
const { default: DocumentChecks } = await loadComponent('DocumentChecks')
const { default: PrivacyPanel } = await loadComponent('PrivacyPanel')
const html = (Component, props) => renderToStaticMarkup(React.createElement(Component, props))

const lines = {
  note: 'Requirement statuses do not change the score.', bounded: false,
  counts: { matched: 1, partial: 1, not_evidenced: 1, unclear: 1 },
  rows: [
    { text: '5+ years of Python', context: 'required', type: 'experience', status: 'matched', basis: 'explicit', reason: '7 years documented.', evidence: [{ section: 'experience', entry_index: 0, excerpt: 'Built Python APIs.' }] },
    { text: 'Experience with AWS', context: 'required', type: 'skill', status: 'partial', basis: 'inference', reason: 'Related: Azure.', evidence: [] },
    { text: 'AWS certification', context: 'required', type: 'certification', status: 'not_evidenced', basis: 'none', reason: 'None found.', evidence: [] },
    { text: 'Experience with Go', context: 'preferred', type: 'skill', status: 'unclear', basis: 'none', reason: 'Review manually.', evidence: [] },
  ],
}
const analysis = {
  analysis_id: 'a', overall_score: 75, recommendation: 'Recommended', experience_level: 'Senior', total_experience_years: 7,
  resume_quality_score: 80, job_fit_score: 72, job_fit_label: 'Partial Match', job_fit_method: 'ai', job_fit_model: 'model-x',
  ai_status: 'used', local_overall_score: 49, local_job_fit_score: 40, local_job_fit_label: 'Weak Match', skills_count: 6,
  ai_match_evidence: { Python: 'explicit', Terraform: 'inferred' }, strengths: ['AI strength'], weaknesses: [], suggestions: [],
  interview_questions: ['Q1?'], missing_sections: [],
  explanation: { requirement_lines: lines, blend: { weak_fit_cap: null }, local_comparison: { overall_score: 49, job_fit_score: 40, job_fit_label: 'Weak Match', rule: 'Local rules.', job_components: [] } },
  impacts: { note: 'Only if true.', scope_note: 'AI held constant.', items: [{ action: 'Add an email', condition: 'Real details only.', kind: 'quality', quality_delta: 3, job_fit_delta: 0, overall_delta: 1 }] },
}

test('view-model helpers', () => {
  assert.equal(formatDelta(3), '+3'); assert.equal(formatDelta(0), '0'); assert.equal(formatDelta(-2), '-2')
  assert.equal(hasPlaceholder('Built [result]'), true); assert.equal(hasPlaceholder('Built APIs'), false)
  assert.equal(retentionText(7200), '2 hours'); assert.equal(retentionText(1800), '30 minutes')
  assert.deepEqual(groupRequirements(lines.rows).map((g) => g.context), ['required', 'preferred'])
  const { matches, gaps } = summaryHighlights(analysis)
  assert.deepEqual(matches.map((r) => r.text), ['5+ years of Python'])
  assert.deepEqual(gaps.map((r) => r.text), ['AWS certification', 'Experience with AWS'])
})

test('AI score stays main with the local score beside it', () => {
  const sources = scoreSources(analysis)
  assert.equal(sources.mainLabel, 'AI-assisted score')
  assert.deepEqual(sources.local, { overall: 49, jobFit: 40, label: 'Weak Match' })
  const out = html(ScoreSummary, { analysis })
  assert.match(out, /AI-assisted score/)
  assert.match(out, /Local rules score/)
  assert.match(out, />49<small>/)
  assert.match(out, /not equally calibrated/)
  assert.equal(scoreSources({ ...analysis, job_fit_method: 'rule-based' }).local, null)
})

test('AI fallback shows a visible banner', () => {
  const out = html(ScoreSummary, { analysis: { ...analysis, job_fit_method: 'rule-based', ai_status: 'fallback', processing_note: 'The AI provider was unavailable; local matching was used.' } })
  assert.match(out, /banner-warning/)
  assert.match(out, /provider was unavailable/)
})

test('requirement matrix shows status, reason, basis, quotes and AI evidence labels', () => {
  const out = html(RequirementMatrix, { lines, aiEvidence: analysis.ai_match_evidence })
  for (const text of ['Matched', 'Partial', 'Not evidenced', "Can&#x27;t assess", 'Inference — verify', 'Resume evidence', 'Built Python APIs.', 'experience entry 1', 'Preferred / nice to have', 'Inferred by AI', 'Found in resume'])
    assert.ok(out.includes(text), text)
  assert.match(html(RequirementMatrix, { lines: null }), /Add a job description/)
})

test('score impact lists deltas and the scope note', () => {
  const out = html(ScoreImpact, { impacts: analysis.impacts, weakFitCap: true })
  assert.match(out, /Add an email/); assert.match(out, /\+1/); assert.match(out, /\+3/)
  assert.match(out, /AI held constant/); assert.match(out, /weak job-fit cap/)
  assert.match(html(ScoreImpact, { impacts: { note: 'n', items: [] } }), /No score-raising edits/)
})

test('document checks show findings, fixes and passed checks', () => {
  const checks = { format: 'docx', pages: null, characters: 1200, note: 'Not a guarantee.', passed: ['Email and phone number were found.'],
    findings: [{ id: 'text_boxes', severity: 'warning', title: '1 text box(es) found', detail: 'Not read.', fix: 'Move it.' }, { id: 'tables', severity: 'info', title: '1 table(s) used', detail: 'd', fix: 'f' }] }
  const full = html(DocumentChecks, { checks })
  assert.match(full, /1 possible issue/); assert.match(full, /Move it\./); assert.match(full, /table\(s\) used/); assert.match(full, /Email and phone/)
  const compact = html(DocumentChecks, { checks, compact: true })
  assert.ok(!compact.includes('table(s) used'))
  assert.match(html(DocumentChecks, { checks: null }), /unavailable/)
})

test('dashboard renders a summary and accessible tabs; panels switch by tab', () => {
  const props = { analysis, candidate: { document_checks: null }, improvements: null, improvementDraft: null, canGenerate: true, onGenerate() {}, onAction() {}, onDownload() {} }
  const out = html(ResultsDashboard, props)
  assert.match(out, /role="tablist"/)
  assert.equal((out.match(/role="tab"/g) || []).length, 5)
  assert.match(out, /aria-selected="true"[^>]*>Requirements/)
  assert.match(out, /5\+ years of Python/)
  assert.match(html(ResultsDashboard, { ...props, initialTab: 'improve' }), /What would change this score/)
  const interview = html(ResultsDashboard, { ...props, initialTab: 'interview' })
  assert.match(interview, /AI-generated and unverified/); assert.match(interview, /Q1\?/)
  assert.match(html(ResultsDashboard, { ...props, initialTab: 'score' }), /Local rules result/)
  assert.match(html(ResultsDashboard, { ...props, initialTab: 'document' }), /Readability checks are unavailable/)
  assert.ok(!out.includes('Candidate Strength Radar'))
})

test('privacy panel explains handling and offers deletion', () => {
  const out = html(PrivacyPanel, { token: 't', initialSummary: { resume_stored: true, analysis_stored: false, history_entries: 2, workspaces: 0, candidates: 0, retention_seconds: 7200, ai_provider_configured: false } })
  assert.match(out, /never kept/); assert.match(out, /2 entries/); assert.match(out, /2 hours of inactivity/)
  assert.match(out, /no AI provider is configured/); assert.match(out, /Delete my data now/)
})
