import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { transformWithOxc } from 'vite'

// Use the existing Vite JSX compiler and React server renderer, with no server.
const source = await readFile(new URL('../src/ExplainableResults.jsx', import.meta.url), 'utf8')
const transformed = await transformWithOxc(source, 'ExplainableResults.jsx', { jsx: { runtime: 'classic' } })
const code = transformed.code.replaceAll('"react"', JSON.stringify(import.meta.resolve('react'))).replaceAll("'react'", JSON.stringify(import.meta.resolve('react')))
const { default: Results } = await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`)
const render = (explanation) => renderToStaticMarkup(React.createElement(Results, { explanation }))
test('print explanations expand limitations rather than silently omitting them', () => {
  const html = renderToStaticMarkup(React.createElement(Results, { explanation: { limitations: ['Verify source facts'] }, expandLimitations: true }))
  assert.match(html, /<details open="">/)
  assert.match(html, /Verify source facts/)
  assert.ok(!render({}).includes('<details open'))
})
const example = {
  overall_score: 69, scale: 100, summary: 'Actual arithmetic', advisory: 'Human review required',
  quality_components: [{ component: 'skills', points: 10, maximum: 25, rule: 'Existing rule' }],
  job_components: [{ component: 'skills', score: 50, weight: .6, weighted_points: 30 }],
  requirements: [{ skill: 'Python', status: 'matched', basis: 'Canonical extracted skill list', contexts: ['required'], weight: 1, evidence: [{ section: 'experience', entry_index: 1, excerpt: 'Built Python services.' }] }, { skill: 'Docker', status: 'not_evidenced', contexts: ['preferred'], weight: 0.5, evidence: [] }],
  recommendations: ['If you have used Docker, describe that work.'], limitations: ['Vocabulary is limited'],
}

test('overall and genuine component values render with accessible labels', () => {
  const html = render(example)
  assert.match(html, /69 \/ 100/)
  assert.match(html, /10 \/ 25 points/)
  assert.match(html, /aria-label="skills job-fit score"/)
  assert.match(html, /value="50"/)
})

test('matched, not-evidenced and source entry are distinct', () => {
  const html = render(example)
  assert.match(html, /Matched skills/)
  assert.match(html, /Requirements not evidenced/)
  assert.match(html, /Built Python services\./)
  assert.match(html, /experience entry 2/)
  assert.match(html, /preferred \(half skills weight\)/)
  assert.match(html, /required \(full skills weight\)/)
})

test('old analyses and missing optional fields render safely', () => {
  assert.match(render(undefined), /older analysis/)
  assert.match(render({}), /No recognized job skill requirements/)
  assert.match(render({ requirements: null, recommendations: null }), /No specific improvements/)
})

test('empty skills and missing quote have informative states', () => {
  assert.match(render({ requirements: [] }), /No requirement evidence available/)
  assert.match(render({ requirements: [{ skill: 'Python', status: 'matched' }] }), /Source quotation unavailable/)
})

test('untrusted excerpts and long skill names remain escaped text', () => {
  const content = '<script>alert("x")</script>'
  const html = render({ requirements: [{ skill: 'LongSkill'.repeat(80), status: 'matched', evidence: [{ section: 'projects', excerpt: content }] }] })
  assert.ok(!html.includes('<script>'))
  assert.match(html, /&lt;script&gt;/)
  assert.ok(html.includes('LongSkill'.repeat(80)))
})

test('AI provenance does not fabricate progress bars or confidence', () => {
  const html = render({ summary: 'Provider judgment; not verifiable', job_components: [], unverified_provider_matches: ['Terraform'] })
  assert.ok(!html.includes('<progress'))
  assert.match(html, /not locally verified: Terraform/)
})

test('blend explanation includes actual cap and rounded score', () => {
  assert.match(render({ blend: { resume_quality_points: 30, job_fit_points: 28, rounded_before_cap: 58, weak_fit_cap: 49, final_score: 49 } }), /Rounded total: 58\. Weak-fit cap: 49\. Final score: 49/)
})

test('layout has responsive wrapping and keeps the existing wizard integration', async () => {
  const css = await readFile(new URL('../src/App.css', import.meta.url), 'utf8')
  const app = await readFile(new URL('../src/App.jsx', import.meta.url), 'utf8')
  assert.match(css, /grid-template-columns: repeat\(auto-fit, minmax\(min\(100%, 260px\), 1fr\)\)/)
  assert.match(css, /overflow-wrap: anywhere/)
  assert.match(app, /currentStep === 4 && analysis/)
  assert.match(app, /<ExplainableResults explanation=\{analysis.explanation\}/)
  assert.ok(!source.includes('dangerouslySetInnerHTML'))
})
