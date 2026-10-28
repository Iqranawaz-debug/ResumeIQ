import { test, afterEach } from 'node:test'
import assert from 'node:assert/strict'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { loadComponent } from './load-component.mjs'
import { EXPORT_FOOTER, scoreLabel } from '../src/recruiterState.js'
import { exportComparisonCsv } from '../src/api.js'

const { default: Report } = await loadComponent('ComparisonReport')
const rows = [
  { id: 'b', name: 'Amy Able', filename: 'amy.docx', status: 'Shortlisted', tags: ['Phone screen'], notes: [{ id: 'n1', text: 'PRIVATE <b>note</b>' }],
    matched_skill_names: ['Python', 'AWS'], missing_skill_names: ['Go'],
    analysis: { overall_score: 88, job_fit_method: 'rule-based', total_experience_years: 9, matched_skills: ['python', 'aws'], missing_skills: ['golang'] } },
  { id: 'a', name: '<script>Zoe</script>', filename: 'zoe.pdf', status: 'Not Reviewed', tags: [], notes: [],
    analysis: { overall_score: 75, job_fit_method: 'ai', total_experience_years: 3, matched_skills: ['python'], missing_skills: [] } },
]
const render = (props = {}) => renderToStaticMarkup(React.createElement(Report, { title: 'Senior Backend Engineer', version: 2, generatedAt: '2026-10-28T10:00:00Z', rows, notice: 'Human review only.', ...props }))

test('score wording matches the table and the CSV export', () => {
  assert.equal(scoreLabel({ overall_score: 80, job_fit_method: 'rule-based' }), '80 / 100 (Local score)')
  assert.equal(scoreLabel({ overall_score: 75, job_fit_method: 'ai' }), '75 / 100 (AI score)')
  assert.equal(scoreLabel({ overall_score: 0 }), '0 / 100 (Local score)')
  assert.equal(scoreLabel(null), 'Not scored yet')
  assert.equal(EXPORT_FOOTER, 'Decision support only. Human review required.')
})

test('PDF report has job title, date, candidates in selected order, explanations and the footer', () => {
  const html = render()
  assert.match(html, /Senior Backend Engineer · job version 2 · 2 candidates in the order selected/)
  assert.match(html, /Generated /)
  assert.ok(html.indexOf('Amy Able') < html.indexOf('Zoe'))
  assert.match(html, /88 \/ 100 \(Local score\)/); assert.match(html, /75 \/ 100 \(AI score\)/)
  assert.match(html, /Python, AWS/); assert.match(html, /<td>Go<\/td>/)
  assert.match(html, /Phone screen/)
  assert.match(html, /older analysis/) // ExplainableResults renders for every candidate.
  assert.match(html, /Decision support only\. Human review required\./)
})

test('PDF report excludes private notes unless requested and escapes all text', () => {
  const without = render()
  assert.ok(!without.includes('PRIVATE'))
  assert.ok(!without.includes('Private notes'))
  const withNotes = render({ includeNotes: true })
  assert.match(withNotes, /Private notes/)
  assert.match(withNotes, /PRIVATE &lt;b&gt;note&lt;\/b&gt;/)
  assert.match(withNotes, /No notes\./)
  assert.ok(!withNotes.includes('<script>'))
  assert.match(withNotes, /&lt;script&gt;Zoe&lt;\/script&gt;/)
})

const originalFetch = globalThis.fetch
afterEach(() => { globalThis.fetch = originalFetch })

test('CSV export request sends the chosen order and excludes notes by default', async () => {
  const calls = []
  globalThis.fetch = async (url, options) => { calls.push({ url, options }); return new Response(JSON.stringify({ filename: 'x.csv', content: 'a', include_notes: false }), { status: 200 }) }
  const result = await exportComparisonCsv('tok', 'g 1', { candidateIds: ['b', 'a'], version: 3 })
  await exportComparisonCsv('tok', 'g', { candidateIds: ['a'], version: 1, includeNotes: true })
  assert.equal(result.filename, 'x.csv')
  assert.ok(calls[0].url.endsWith('/api/workspaces/g%201/comparison/csv'))
  assert.equal(calls[0].options.method, 'POST')
  assert.deepEqual(JSON.parse(calls[0].options.body), { candidate_ids: ['b', 'a'], version: 3, include_notes: false })
  assert.equal(JSON.parse(calls[1].options.body).include_notes, true)
})

test('CSV export surfaces server errors such as stale job versions', async () => {
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: 'Job description changed. Refresh and analyze the current version.' }), { status: 409 })
  await assert.rejects(exportComparisonCsv('tok', 'g', { candidateIds: ['a'], version: 1 }), /Job description changed/)
})
