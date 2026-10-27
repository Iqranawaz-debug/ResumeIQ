import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { transformWithOxc } from 'vite'
import { initializeDraft, updateDraft, checklistCounts, improvementReport } from '../src/improvementState.js'

async function component(name) {
  const source = await readFile(new URL(`../src/${name}.jsx`, import.meta.url), 'utf8')
  const result = await transformWithOxc(source, `${name}.jsx`, { jsx: { runtime: 'classic' } })
  const code = result.code.replace(/(['"])react\1/g, JSON.stringify(import.meta.resolve('react')))
    .replace(/(['"])\.\/improvementState.js\1/g, JSON.stringify(new URL('../src/improvementState.js', import.meta.url).href))
  return (await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`)).default
}
const Workspace = await component('ImprovementWorkspace')
const Report = await component('ImprovementReport')
const data = { suggestions: [{ id: 'one', section: 'experience', entry_index: 0, detail_index: 0,
  original_text: 'Utilized SQL.', suggested_text: 'Used SQL.', reason: 'Reduce wording.', source: 'local' }],
checklist: [{ id: 'check', category: 'Clarity', text: 'Clarify your contribution.' }], limitations: ['Review all claims.'] }
const render = (props = {}) => renderToStaticMarkup(React.createElement(Workspace, { data, draft: initializeDraft(data), canGenerate: true, ...props }))
function nodes(element) {
  if (!element || typeof element !== 'object') return []
  return [element, ...React.Children.toArray(element.props?.children).flatMap(nodes)]
}

test('draft edits, acceptance, rejection and restoration remain reversible and immutable', () => {
  const original = initializeDraft(data)
  let state = updateDraft(data, original, { type: 'edit', id: 'one', text: 'My verified wording.' })
  assert.equal(state.suggestions.one.edited, true)
  state = updateDraft(data, state, { type: 'accept', id: 'one' })
  assert.equal(state.suggestions.one.status, 'accepted')
  state = updateDraft(data, state, { type: 'reject', id: 'one' })
  assert.equal(state.suggestions.one.status, 'rejected')
  state = updateDraft(data, state, { type: 'restore', id: 'one' })
  assert.equal(state.suggestions.one.text, 'Utilized SQL.')
  assert.equal(state.suggestions.one.status, 'restored')
  assert.equal(original.suggestions.one.text, 'Used SQL.')
  assert.equal(data.suggestions[0].original_text, 'Utilized SQL.')
})
test('blank acceptance, excessive edits and unknown actions are ignored', () => {
  const draft = initializeDraft(data)
  for (const action of [{ type: 'edit', id: 'one', text: 'a'.repeat(2001) }, { type: 'accept', id: 'missing' }, { type: 'delete', id: 'one' }]) assert.equal(updateDraft(data, draft, action), draft)
  const blank = updateDraft(data, draft, { type: 'edit', id: 'one', text: ' ' })
  assert.equal(updateDraft(data, blank, { type: 'accept', id: 'one' }), blank)
})
test('checklist counts follow complete, not applicable and pending without scoring', () => {
  let draft = initializeDraft(data)
  for (const status of ['complete', 'not_applicable', 'pending']) {
    draft = updateDraft(data, draft, { type: 'checklist', id: 'check', status })
    const counts = checklistCounts(draft)
    assert.equal(counts.total, 1)
    assert.equal(counts.completed, Number(status === 'complete'))
    assert.equal(counts.remaining, Number(status === 'pending'))
    assert.equal(counts.notApplicable, Number(status === 'not_applicable'))
  }
  assert.equal(updateDraft(data, draft, { type: 'checklist', id: 'check', status: 'invalid' }), draft)
})
test('same evaluation preserves decisions while fresh initialization resets them', () => {
  const accepted = updateDraft(data, initializeDraft(data), { type: 'accept', id: 'one' })
  assert.equal(initializeDraft(data, accepted).suggestions.one.status, 'accepted')
  assert.equal(initializeDraft(data).suggestions.one.status, 'pending')
  assert.deepEqual(initializeDraft({}).suggestions, {})
})
test('comparisons and keyboard controls expose source, labels and review requirement', () => {
  const html = render()
  for (const expected of ['Utilized SQL.', 'Used SQL.', 'Status: pending', 'Accept draft', 'Restore original', 'Review meaning', 'for="draft-one"', 'for="check-check"']) assert.ok(html.includes(expected))
})
test('actual component event handlers dispatch edits and decisions', () => {
  const actions = [], calls = []
  const tree = nodes(Workspace({ data, draft: initializeDraft(data), canGenerate: true, onAction: (action) => actions.push(action), onGenerate: (...args) => calls.push(args) }))
  tree.find((node) => node.type === 'textarea').props.onChange({ target: { value: 'Edited' } })
  tree.find((node) => node.type === 'select').props.onChange({ target: { value: 'complete' } })
  for (const label of ['Accept draft', 'Reject', 'Restore original', 'Generate suggestions']) tree.find((node) => node.type === 'button' && node.props.children === label).props.onClick()
  assert.deepEqual(actions.map((action) => action.type), ['edit', 'checklist', 'accept', 'reject', 'restore'])
  assert.deepEqual(calls, [[]])
  assert.equal(tree.some((node) => node.type === 'button' && /AI/.test(String(node.props.children))), false)
})
test('missing data, older analyses, loading and errors have visible states', () => {
  assert.match(render({ data: undefined, canGenerate: false }), /Older reports remain readable/)
  assert.match(render({ data: {} }), /No safe automatic wording changes/)
  assert.match(render({ busy: true, error: 'Try again' }), /role="alert">Try again/)
  assert.match(render({ busy: true }), /disabled=""/)
})
test('long untrusted text is escaped and user edits are marked unverified', () => {
  const draft = updateDraft(data, initializeDraft(data), { type: 'edit', id: 'one', text: '<script>bad()</script>' + 'x'.repeat(1500) })
  const html = render({ draft })
  assert.ok(!html.includes('<script>'))
  assert.match(html, /&lt;script&gt;/)
  assert.match(html, /not automatically verified/)
})
test('text and print reports include current decisions, original and proposed wording', () => {
  let draft = updateDraft(data, initializeDraft(data), { type: 'edit', id: 'one', text: 'Verified edit' })
  draft = updateDraft(data, draft, { type: 'accept', id: 'one' })
  draft = updateDraft(data, draft, { type: 'checklist', id: 'check', status: 'not_applicable' })
  const text = improvementReport(data, draft)
  for (const expected of ['accepted', 'Original: Utilized SQL.', 'Proposed: Used SQL.', 'Current draft: Verified edit', '[not_applicable]', 'not automatically verified']) assert.ok(text.includes(expected))
  assert.match(renderToStaticMarkup(React.createElement(Report, { data, draft })), /Verified edit/)
  assert.equal(renderToStaticMarkup(React.createElement(Report, {})), '')
})
test('download handler emits the current report and cleans up its object URL', () => {
  let blob, clicked = false, removed = false, revoked
  const oldDocument = globalThis.document, oldCreate = URL.createObjectURL, oldRevoke = URL.revokeObjectURL
  const anchor = { click() { clicked = true }, remove() { removed = true } }
  try {
    globalThis.document = { createElement: () => anchor, body: { appendChild() {} } }
    URL.createObjectURL = (value) => { blob = value; return 'blob:test' }
    URL.revokeObjectURL = (value) => { revoked = value }
    nodes(Workspace({ data, draft: initializeDraft(data) })).find((node) => node.type === 'button' && node.props.children === 'Download improvement report (.txt)').props.onClick()
    assert.equal(blob.type, 'text/plain;charset=utf-8')
    assert.equal(anchor.download, 'resume-improvement-report.txt')
    assert.ok(clicked && removed)
    assert.equal(revoked, 'blob:test')
  } finally { globalThis.document = oldDocument; URL.createObjectURL = oldCreate; URL.revokeObjectURL = oldRevoke }
})
