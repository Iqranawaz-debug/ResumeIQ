import { test, afterEach } from 'node:test'
import assert from 'node:assert/strict'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { loadComponent } from './load-component.mjs'
import { ANNOTATION_LIMITS, EMPTY_FILTERS, allTags, filterCandidates, normalizeTag, noteError, tagError, updateCandidate, withNote, withTags, withoutNote } from '../src/recruiterState.js'
import { addCandidateNote, addCandidateTag, deleteCandidateNote, editCandidateNote, removeCandidateTag, workspaceUrl } from '../src/api.js'

const { default: Annotations } = await loadComponent('CandidateAnnotations')
const { default: Comparison } = await loadComponent('RecruiterComparison')
const rows = [
  { id: 'a', name: 'Zoe', status: 'Not Reviewed', tags: ['Phone screen'], notes: [{ id: 'n1', text: 'Strong payments background' }] },
  { id: 'b', name: 'Amy', status: 'Shortlisted', tags: ['phone SCREEN', 'C++'], notes: [] },
  { id: 'c', name: 'Max', status: 'Under Review' },
]
const ids = (list) => list.map((row) => row.id)

test('tag normalization and validation mirror the backend rules', () => {
  assert.equal(normalizeTag('  Team   lead '), 'Team lead')
  assert.equal(tagError('C++', []), '')
  assert.equal(tagError("O'Brien referral", []), '')
  for (const bad of ['', '   ', '=SUM(A1)', '+cmd', '-1', '@user', 'a/b', '<b>', 'x'.repeat(31)]) assert.ok(tagError(bad, []), bad)
  const ten = Array.from({ length: 10 }, (_, i) => `t${i}`)
  assert.match(tagError('new', ten), /up to 10/)
  assert.equal(tagError('T0', ten), '') // Duplicate (any case) is a no-op, not a limit error.
  assert.equal(tagError('x'.repeat(30), []), '')
})

test('note validation trims and checks the configured length', () => {
  assert.match(noteError('   '), /Write a note/)
  assert.equal(noteError('x'.repeat(ANNOTATION_LIMITS.note_chars)), '')
  assert.match(noteError('x'.repeat(ANNOTATION_LIMITS.note_chars + 1)), /2000/)
  assert.match(noteError('abcdef', { ...ANNOTATION_LIMITS, note_chars: 5 }), /5 characters/)
})

test('tag filter and search over notes and tags never reorder candidates', () => {
  const filter = (value) => ids(filterCandidates(rows, { ...EMPTY_FILTERS, ...value }))
  assert.deepEqual(filter({}), ['a', 'b', 'c'])
  assert.deepEqual(filter({ tag: 'PHONE screen' }), ['a', 'b'])
  assert.deepEqual(filter({ tag: 'c++' }), ['b'])
  assert.deepEqual(filter({ search: 'payments' }), ['a'])
  assert.deepEqual(filter({ search: 'c++' }), ['b'])
  assert.deepEqual(filter({ tag: 'missing' }), [])
  assert.deepEqual(filter({ search: '[.*' }), [])
})

test('tag options are distinct and alphabetical without touching candidate order', () => {
  const before = JSON.stringify(rows)
  assert.deepEqual(allTags(rows), ['C++', 'Phone screen'])
  assert.deepEqual(allTags(null), [])
  assert.equal(JSON.stringify(rows), before)
})

test('candidate updates are immutable and keep note order', () => {
  const updated = updateCandidate(rows, 'a', (row) => withNote(row, { id: 'n2', text: 'Second' }))
  assert.deepEqual(updated[0].notes.map((n) => n.id), ['n1', 'n2'])
  assert.equal(rows[0].notes.length, 1)
  assert.strictEqual(updated[1], rows[1])
  const edited = withNote(updated[0], { id: 'n1', text: 'Edited' })
  assert.deepEqual(edited.notes.map((n) => n.text), ['Edited', 'Second'])
  assert.deepEqual(withoutNote(edited, 'n1').notes.map((n) => n.id), ['n2'])
  assert.deepEqual(withTags(rows[2], ['x']).tags, ['x'])
  assert.equal(rows[2].tags, undefined)
})

const originalFetch = globalThis.fetch
afterEach(() => { globalThis.fetch = originalFetch })
function captureFetch(response = { ok: true }) {
  const calls = []
  globalThis.fetch = async (url, options) => { calls.push({ url, options }); return new Response(JSON.stringify(response), { status: 200 }) }
  return calls
}

test('api functions build encoded URLs, methods and JSON bodies', async () => {
  const calls = captureFetch({ tags: [] })
  await addCandidateNote('tok', 'g/1', 'c 1', 'Hello')
  await editCandidateNote('tok', 'g', 'c', 'n1', 'Edited')
  await deleteCandidateNote('tok', 'g', 'c', 'n1')
  await addCandidateTag('tok', 'g', 'c', 'C++')
  await removeCandidateTag('tok', 'g', 'c', 'C++ #1')
  assert.deepEqual(calls.map((c) => c.options.method), ['POST', 'PATCH', 'DELETE', 'POST', 'DELETE'])
  assert.ok(calls[0].url.endsWith('/api/workspaces/g%2F1/candidates/c%201/notes'))
  assert.ok(calls[4].url.endsWith('/tags/C%2B%2B%20%231'))
  assert.equal(calls[0].options.body, JSON.stringify({ text: 'Hello' }))
  assert.equal(calls[3].options.body, JSON.stringify({ tag: 'C++' }))
  assert.equal(calls[2].options.body, undefined)
  assert.equal(calls[0].options.headers.Authorization, 'Bearer tok')
  assert.equal(calls[0].options.headers['Content-Type'], 'application/json')
  assert.equal(calls[2].options.headers['Content-Type'], undefined)
  assert.ok(workspaceUrl('a b').endsWith('/api/workspaces/a%20b'))
})

test('api functions surface server validation messages', async () => {
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: 'Tag limit reached (10). Remove a tag first.' }), { status: 409 })
  await assert.rejects(addCandidateTag('tok', 'g', 'c', 'x'), /Tag limit reached/)
})

const handlers = { onAddNote: async () => true, onEditNote: async () => true, onDeleteNote: async () => true, onAddTag: async () => true, onRemoveTag: async () => true }
const renderAnnotations = (row, extra = {}) => renderToStaticMarkup(React.createElement(Annotations, { row, busy: false, ...handlers, ...extra }))

test('notes panel escapes text, shows chips, counts and privacy hint', () => {
  const html = renderAnnotations({ id: 'a', name: '<b>Zoe</b>', tags: ['C++'], notes: [{ id: 'n1', text: '<img src=x onerror=alert(1)>\nline two', created_at: '2026-01-01T00:00:00Z' }] })
  assert.ok(!html.includes('<img src=x'))
  assert.match(html, /&lt;img src=x onerror=alert\(1\)&gt;/)
  assert.match(html, /&lt;b&gt;Zoe&lt;\/b&gt;/)
  assert.match(html, /Remove tag C\+\+/)
  assert.match(html, /1 of 10 tags/)
  assert.match(html, /Never sent to AI/)
  assert.match(html, /Edit note/); assert.match(html, /Delete note/)
})

test('notes panel hides add forms at the limits', () => {
  const html = renderAnnotations({ id: 'a', name: 'Zoe', tags: ['a', 'b'], notes: [{ id: 'n1', text: 'x' }] }, { limits: { ...ANNOTATION_LIMITS, tags: 2, notes: 1 } })
  assert.ok(!html.includes('Add tag for'))
  assert.match(html, /Note limit reached \(1\)/)
})

test('comparison shows tag chips and the annotations slot only when provided', () => {
  const row = { id: 'a', name: 'Zoe', filename: 'z.pdf', status: 'Not Reviewed', tags: ['Phone screen'], candidate: {} }
  const withSlot = renderToStaticMarkup(React.createElement(Comparison, { rows: [row], onReview() {}, renderAnnotations: () => React.createElement('p', null, 'ANNOTATIONS') }))
  assert.match(withSlot, /Tags for Zoe/); assert.match(withSlot, /Phone screen/); assert.match(withSlot, /ANNOTATIONS/)
  const without = renderToStaticMarkup(React.createElement(Comparison, { rows: [row], onReview() {} }))
  assert.ok(!without.includes('ANNOTATIONS'))
})
