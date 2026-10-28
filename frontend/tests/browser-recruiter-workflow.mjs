// Phase 6 browser journeys: notes/tags, CSV/PDF export and the pipeline board.
// Uses the same isolated servers and environment as browser-recruiter.mjs (see docs/phase6-recruiter-workflow.md).
import assert from 'node:assert/strict'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import { pathToFileURL } from 'node:url'
import { randomUUID } from 'node:crypto'
const { chromium } = await import(pathToFileURL(resolve(process.env.QA_PLAYWRIGHT, 'index.mjs')).href)
const out = resolve('../test-results/phase6-workflow'), fixtures = resolve('../test-results/phase51')
await mkdir(out, { recursive: true })
const browser = await chromium.launch({ executablePath: process.env.QA_BROWSER, headless: true })
const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, acceptDownloads: true })
const page = await context.newPage(); page.setDefaultTimeout(10000)
const base = 'http://127.0.0.1:5175', api = 'http://127.0.0.1:8003'
const results = [], errors = [], unexpected = []
await context.route('**/*', (route) => {
  const url = new URL(route.request().url())
  if ([base, api].includes(url.origin) || ['blob:', 'data:'].includes(url.protocol)) return route.continue()
  unexpected.push(url.origin); return route.abort()
})
page.on('pageerror', (error) => errors.push(error.message))
const button = (name) => page.getByRole('button', { name, exact: true })
const table = () => page.getByRole('region', { name: 'Candidate list, scroll horizontally if needed' })
const candidates = () => table().locator('tbody tr')
const panel = () => page.locator('.rw-annotations').first()
let groupId, token, ids = []
async function scenario(name, fn) {
  try { await fn(); results.push({ name, result: 'passed' }); console.log('PASS', name) }
  catch (error) { results.push({ name, result: 'failed', error: error.message.split('\n').slice(0, 4).join('\n') }); console.log('FAIL', name, error.message.split('\n')[0]); await page.screenshot({ path: resolve(out, `failure-${results.length}.png`), fullPage: true }).catch(() => {}) }
}
async function signup() {
  await button('Create an account').click()
  await page.getByLabel('Full name').fill('Fictional Recruiter')
  await page.getByLabel('Work email').fill(`qa-${randomUUID()}@example.invalid`)
  await page.getByLabel('Password').fill(randomUUID())
  const pending = page.waitForResponse(`${api}/api/signup`)
  await button('Create Account').click(); token = (await (await pending).json()).token
  await page.getByRole('heading', { name: 'Upload a resume', exact: true }).waitFor()
}
const authed = (method, path, data) => context.request.fetch(`${api}${path}`, { method, headers: { Authorization: `Bearer ${token}` }, ...(data ? { data } : {}) })
async function waitIdle() { await page.waitForFunction(() => { const b = [...document.querySelectorAll('button')].find((n) => n.textContent === 'Analyze group locally'); return b && !b.disabled }) }

try {
  await page.goto(base)
  await scenario('Set up a workspace with two analyzed fictional candidates', async () => {
    await signup(); await button('Recruitment').click()
    await page.getByLabel('Job title', { exact: true }).fill('Synthetic engineering role')
    await page.getByLabel('Shared job description').fill('Required skills: Python, React.js, SQL. Preferred skills: Docker.')
    const created = page.waitForResponse((r) => r.url() === `${api}/api/workspaces` && r.request().method() === 'POST')
    await button('Create workspace').click(); groupId = (await (await created).json()).id
    await page.getByLabel('Select resumes', { exact: true }).setInputFiles([resolve(fixtures, 'synthetic.pdf'), resolve(fixtures, 'synthetic.docx')])
    await button('Process selected files').click(); await button('Analyze group locally').waitFor()
    await button('Analyze group locally').click(); await page.getByText(/Analysis pass finished/).waitFor(); await waitIdle()
    ids = (await (await authed('GET', `/api/workspaces/${groupId}`)).json()).candidates.map((c) => c.id)
    assert.equal(await candidates().count(), 2)
  })

  // Notes and tags ------------------------------------------------------------
  await scenario('Tags: add, case-insensitive duplicate, invalid input and remove', async () => {
    await candidates().first().getByRole('button', { name: 'Review candidate', exact: true }).click()
    const tagInput = panel().getByLabel(/^Add tag for/)
    for (const tag of ['Phone screen', 'PHONE SCREEN', 'Payments']) { await tagInput.fill(tag); await panel().getByRole('button', { name: 'Add tag', exact: true }).click(); await waitIdle() }
    assert.deepEqual(await panel().locator('.rw-tag-chips li span').allInnerTexts(), ['Phone screen', 'Payments'])
    await tagInput.fill('=HYPERLINK(1)'); await panel().getByRole('button', { name: 'Add tag', exact: true }).click()
    await panel().getByRole('alert').waitFor()
    await panel().getByRole('button', { name: 'Remove tag Payments', exact: true }).click(); await waitIdle()
    assert.deepEqual(await panel().locator('.rw-tag-chips li span').allInnerTexts(), ['Phone screen'])
    assert.ok((await candidates().first().innerText()).includes('Phone screen'))
  })
  await scenario('Notes: add, edit, delete; HTML stays text; length counter', async () => {
    const note = panel().getByLabel(/^Add note for/)
    await note.fill('<b>Bold?</b> Strong payments background.')
    assert.ok((await panel().innerText()).includes('/2000'))
    await panel().getByRole('button', { name: 'Add note', exact: true }).click(); await waitIdle()
    assert.equal(await panel().locator('.rw-note-text b').count(), 0)
    assert.ok((await panel().locator('.rw-note-text').first().innerText()).includes('<b>Bold?</b>'))
    await panel().getByRole('button', { name: 'Edit note', exact: true }).click()
    await panel().getByLabel('Edit note').fill('Edited: ask about Kubernetes.')
    await panel().getByRole('button', { name: 'Save note', exact: true }).click(); await waitIdle()
    assert.ok((await panel().locator('.rw-note-text').first().innerText()).includes('Edited: ask about Kubernetes.'))
    await note.fill('Temporary note'); await panel().getByRole('button', { name: 'Add note', exact: true }).click(); await waitIdle()
    await panel().getByRole('button', { name: 'Delete note', exact: true }).nth(1).click(); await waitIdle()
    assert.equal(await panel().locator('.rw-note-text').count(), 1)
  })
  await scenario('Tag filter and note search narrow the list without reordering it', async () => {
    const before = await candidates().allInnerTexts()
    await page.getByLabel('Tag filter').selectOption('Phone screen'); assert.equal(await candidates().count(), 1)
    await page.getByLabel('Tag filter').selectOption(''); await page.getByLabel('Search candidates', { exact: true }).fill('kubernetes')
    assert.equal(await candidates().count(), 1)
    await page.getByLabel('Search candidates', { exact: true }).fill(''); assert.deepEqual(await candidates().allInnerTexts(), before)
  })
  await scenario('Another account gets 404 for notes and tags; signed-out gets 401', async () => {
    const own = token
    const other = await context.request.post(`${api}/api/signup`, { data: { email: `qa-${randomUUID()}@example.invalid`, password: randomUUID() } })
    token = (await other.json()).token
    for (const [method, path, data] of [['POST', `/api/workspaces/${groupId}/candidates/${ids[0]}/notes`, { text: 'x' }], ['POST', `/api/workspaces/${groupId}/candidates/${ids[0]}/tags`, { tag: 'x' }], ['DELETE', `/api/workspaces/${groupId}/candidates/${ids[0]}/tags/Phone%20screen`]]) {
      assert.equal((await authed(method, path, data)).status(), 404)
    }
    token = own
    assert.equal((await context.request.post(`${api}/api/workspaces/${groupId}/candidates/${ids[0]}/notes`, { data: { text: 'x' } })).status(), 401)
  })

  // Export ------------------------------------------------------------------
  await scenario('CSV export excludes notes by default and neutralizes formulas', async () => {
    await candidates().nth(1).getByRole('checkbox').check(); await candidates().nth(0).getByRole('checkbox').check()
    await button('Compare selected candidates').click(); await page.locator('.recruiter-comparison article').nth(1).waitFor()
    const download = page.waitForEvent('download'); await button('Export CSV').click()
    const file = resolve(out, 'comparison.csv'); await (await download).saveAs(file)
    const text = (await readFile(file, 'utf8')).replace(/^﻿/, '')
    assert.ok(text.startsWith('"Candidate","Review status","Tags","Matched skills","Missing skills","Years of experience","Score"'))
    assert.ok(!text.includes('Edited: ask about Kubernetes.'))
    assert.match(text, /\d+ \/ 100 \((Local|AI) score\)/)
    assert.ok(!/(^|,)"[=+\-@]/m.test(text))
  })
  await scenario('CSV export includes notes only when ticked', async () => {
    await page.getByLabel('Include private notes').check()
    const download = page.waitForEvent('download'); await button('Export CSV').click()
    const file = resolve(out, 'comparison-with-notes.csv'); await (await download).saveAs(file)
    assert.ok((await readFile(file, 'utf8')).includes('Edited: ask about Kubernetes.'))
    await page.getByLabel('Include private notes').uncheck()
  })
  await scenario('PDF export renders the print-only report with footer and cleans up', async () => {
    await page.evaluate(() => { window.__printed = 0; window.print = () => { window.__printed++ } })
    await button('Export PDF').click(); await page.locator('body > .comparison-print-report').waitFor({ state: 'attached' })
    assert.equal(await page.evaluate(() => window.__printed), 1)
    assert.equal(await page.evaluate(() => document.body.dataset.print), 'comparison')
    const report = await page.locator('.comparison-print-report').textContent()
    assert.ok(report.includes('Synthetic engineering role')); assert.ok(report.includes('Decision support only. Human review required.'))
    assert.ok(!report.includes('Edited: ask about Kubernetes.'))
    await page.emulateMedia({ media: 'print' }); await page.pdf({ path: resolve(out, 'comparison.pdf'), format: 'A4', printBackground: true }); await page.emulateMedia({ media: 'screen' })
    await page.evaluate(() => window.dispatchEvent(new Event('afterprint')))
    await page.locator('.comparison-print-report').waitFor({ state: 'detached' })
  })

  // Board -------------------------------------------------------------------
  await scenario('Board shows the four existing statuses with cards in upload order', async () => {
    await button('Board').click()
    const columns = page.locator('.rw-board-column h3')
    assert.deepEqual(await columns.allInnerTexts(), ['Not Reviewed', 'Under Review', 'Shortlisted', 'Not Selected'])
    assert.equal(await page.locator('.rw-board-column').first().locator('.rw-board-card').count(), 2)
  })
  await scenario('Move to menu persists through the review endpoint', async () => {
    await page.locator('.rw-board-card').first().locator('select').selectOption('Under Review')
    await page.getByText('Manual review status saved. Evaluation scores are unchanged.').waitFor()
    const server = (await (await authed('GET', `/api/workspaces/${groupId}`)).json()).candidates
    assert.deepEqual(server.map((c) => c.id), ids); assert.equal(server[0].status, 'Under Review')
  })
  await scenario('Drag and drop moves a card between columns', async () => {
    await page.locator('.rw-board-column').first().locator('.rw-board-card').first().dragTo(page.locator('.rw-board-column').nth(3))
    await page.locator('.rw-board-column').nth(3).locator('.rw-board-card').waitFor()
    assert.equal((await (await authed('GET', `/api/workspaces/${groupId}`)).json()).candidates[1].status, 'Not Selected')
  })
  await scenario('Board columns scroll inside the board on a phone, not the page', async () => {
    await page.setViewportSize({ width: 390, height: 844 })
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false)
    assert.ok(await page.evaluate(() => { const b = document.querySelector('.rw-board'); return b.scrollWidth > b.clientWidth }))
    await page.setViewportSize({ width: 1440, height: 900 })
  })
  await scenario('No runtime exceptions or third-party network origins', async () => { assert.deepEqual(errors, []); assert.deepEqual(unexpected, []) })
} finally {
  await writeFile(resolve(out, 'browser-results.json'), JSON.stringify({ browser: browser.version(), results, errors, unexpected }, null, 2))
  console.log(JSON.stringify({ passed: results.filter((r) => r.result === 'passed').length, failed: results.filter((r) => r.result === 'failed').length }))
  await browser.close()
}
if (results.some((r) => r.result === 'failed')) process.exitCode = 1
