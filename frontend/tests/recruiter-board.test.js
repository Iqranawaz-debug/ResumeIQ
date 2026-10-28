import { test } from 'node:test'
import assert from 'node:assert/strict'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { loadComponent } from './load-component.mjs'
import { REVIEW_STATUSES, evidenceSummary, groupByStatus, topTags } from '../src/recruiterState.js'

const { default: Board, BoardView } = await loadComponent('PipelineBoard')
// Upload order: low score first, so any score-based sorting would be visible.
const rows = [
  { id: 'c1', name: 'Low Score', filename: 'a.pdf', status: 'Not Reviewed', overall_score: 40, analysis_state: 'completed', matched_skill_names: ['Python'], missing_skill_names: ['Go', 'AWS'], tags: ['a', 'b', 'c', 'd'] },
  { id: 'c2', name: '<img src=x onerror=alert(1)>', filename: 'b.pdf', status: 'Shortlisted', overall_score: 95, analysis_state: 'pending', tags: [] },
  { id: 'c3', name: 'High Score', filename: 'c.pdf', status: 'Not Reviewed', overall_score: 99, analysis_state: 'completed', matched_skill_names: ['Python', 'Docker', 'AWS', 'Go'], missing_skill_names: [] },
  { id: 'c4', name: 'Outdated', filename: 'd.pdf', status: 'Under Review', analysis_state: 'outdated' },
]

test('columns are exactly the existing review statuses, in order', () => {
  assert.deepEqual(groupByStatus(rows).map((column) => column.status), REVIEW_STATUSES)
  assert.deepEqual(REVIEW_STATUSES, ['Not Reviewed', 'Under Review', 'Shortlisted', 'Not Selected'])
  assert.deepEqual(groupByStatus([{ id: 'x', status: 'Auto Rejected' }]).flatMap((column) => column.rows), [])
})

test('cards keep upload order within a column regardless of score', () => {
  const notReviewed = groupByStatus(rows)[0].rows.map((row) => row.id)
  assert.deepEqual(notReviewed, ['c1', 'c3'])
  const html = renderToStaticMarkup(React.createElement(Board, { rows, onMove() {} }))
  assert.ok(html.indexOf('Low Score') < html.indexOf('High Score'))
  assert.ok(!/\b(40|95|99)\b/.test(html.replace(/\d+ matched|\d+ not evidenced/g, ''))) // No scores on cards.
})

test('card helpers: top tags and a neutral evidence summary', () => {
  assert.deepEqual(topTags(rows[0]), { shown: ['a', 'b', 'c'], hidden: 1 })
  assert.deepEqual(topTags({}), { shown: [], hidden: 0 })
  assert.equal(evidenceSummary(rows[0]), '1 matched · 2 not evidenced · Python')
  assert.equal(evidenceSummary(rows[2]), '4 matched · 0 not evidenced · Python, Docker, AWS')
  assert.equal(evidenceSummary(rows[1]), 'Not analyzed yet')
  assert.match(evidenceSummary(rows[3]), /outdated/)
  assert.equal(evidenceSummary({ analysis_state: 'completed', matched_skills: ['python'], missing_skills: [] }), '1 matched · 0 not evidenced · python')
})

test('board renders columns, counts, escaped text and an accessible Move to menu', () => {
  const html = renderToStaticMarkup(React.createElement(Board, { rows, onMove() {} }))
  for (const status of REVIEW_STATUSES) assert.ok(html.includes(`>${status}</h3>`), status)
  assert.match(html, /aria-label="2 candidates"/)
  assert.match(html, /Drop candidates here/) // Empty "Not Selected" column.
  assert.ok(!html.includes('<img src=x'))
  assert.match(html, /&lt;img src=x onerror=alert\(1\)&gt;/)
  assert.match(html, /Move Low Score to/)
  assert.match(html, />\+1</)
  assert.match(html, /draggable="true"/)
})

function walk(element) {
  if (!element || typeof element !== 'object') return []
  const children = typeof element.type === 'function' ? walk(element.type(element.props)) : React.Children.toArray(element.props?.children).flatMap(walk)
  return [element, ...children]
}
// The stateless view can be called directly, so its event handlers can be invoked without a DOM.
async function boardTree(props) {
  return walk(BoardView(props))
}

test('Move to menu calls onMove only for a different status', async () => {
  const moves = []
  const tree = await boardTree({ rows, onMove: (row, status) => moves.push([row.id, status]) })
  const select = tree.find((node) => node.type === 'select' && node.props.value === 'Not Reviewed')
  select.props.onChange({ target: { value: 'Not Reviewed' } })
  select.props.onChange({ target: { value: 'Shortlisted' } })
  assert.deepEqual(moves, [['c1', 'Shortlisted']])
})

test('drag and drop moves a card to another column, not to its own', async () => {
  const moves = []
  const tree = await boardTree({ rows, onMove: (row, status) => moves.push([row.id, status]) })
  const store = {}
  const dataTransfer = { setData: (type, value) => { store[type] = value }, getData: (type) => store[type], effectAllowed: '', dropEffect: '' }
  const card = tree.find((node) => node.type === 'li' && node.props.draggable)
  card.props.onDragStart({ dataTransfer })
  const columns = tree.filter((node) => node.type === 'section')
  const event = { dataTransfer, preventDefault() {} }
  columns[0].props.onDrop(event) // Same column: no move.
  columns[2].props.onDrop(event) // Shortlisted.
  assert.deepEqual(moves, [['c1', 'Shortlisted']])
  columns[1].props.onDrop({ dataTransfer: { getData: () => 'unknown-id' }, preventDefault() {} })
  assert.equal(moves.length, 1)
})

test('dragging over a column highlights it through the callback', async () => {
  const targets = []
  const tree = await boardTree({ rows, onMove() {}, onDropTarget: (status) => targets.push(status), dropTarget: 'Under Review' })
  const columns = tree.filter((node) => node.type === 'section')
  assert.match(columns[1].props.className, /drop-target/)
  columns[3].props.onDragOver({ preventDefault() {}, dataTransfer: {} })
  assert.deepEqual(targets, ['Not Selected'])
})

test('busy board disables moves', async () => {
  const moves = []
  const tree = await boardTree({ rows, busy: true, onMove: (row, status) => moves.push([row.id, status]) })
  assert.ok(tree.filter((node) => node.type === 'select').every((node) => node.props.disabled))
  assert.ok(tree.filter((node) => node.type === 'li' && 'draggable' in node.props).every((node) => node.props.draggable === false))
})
