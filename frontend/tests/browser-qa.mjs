// Real Chromium QA. Uses an existing external Playwright installation; no install.
// Start backend/tests/browser_server.py and Vite on the documented QA ports first.
import assert from 'node:assert/strict'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import { pathToFileURL } from 'node:url'
import { randomUUID } from 'node:crypto'

const { chromium } = await import(pathToFileURL(resolve(process.env.QA_PLAYWRIGHT, 'index.mjs')).href)
const out = resolve('../test-results/phase51')
await mkdir(out, { recursive: true })
const browser = await chromium.launch({ executablePath: process.env.QA_BROWSER, headless: true })
const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, acceptDownloads: true })
const page = await context.newPage()
page.setDefaultTimeout(8000)
const results = [], errors = [], failures = [], unexpected = []
const base = 'http://127.0.0.1:5175', api = 'http://127.0.0.1:8003'
await context.route('**/*', (route) => {
  const url = new URL(route.request().url())
  if (url.origin === base || url.origin === api || ['blob:', 'data:'].includes(url.protocol)) return route.continue()
  unexpected.push(url.origin); return route.abort()
})
page.on('pageerror', (error) => errors.push(error.message))
page.on('requestfailed', (request) => failures.push({ path: new URL(request.url()).pathname, error: request.failure()?.errorText }))
const consoleErrors = []
page.on('console', (message) => { if (message.type() === 'error') consoleErrors.push(message.text()) })
const email = `qa-${randomUUID()}@example.invalid`, password = randomUUID()
let uploaded, analysis
const button = (name) => page.getByRole('button', { name, exact: true })
const visibleText = async () => page.locator('body').innerText()
async function scenario(name, fn) {
  const start = Date.now()
  try { await fn(); results.push({ name, result: 'passed', ms: Date.now() - start }); console.log('PASS', name) }
  catch (error) {
    results.push({ name, result: 'failed', error: error.message.split('\n').slice(0, 4).join('\n') })
    console.log('FAIL', name, error.message.split('\n')[0])
    await page.screenshot({ path: resolve(out, `failure-${results.length}.png`), fullPage: true }).catch(() => {})
  }
}
async function heading(name) { await page.getByRole('heading', { name, exact: true }).waitFor() }
async function upload(filename) {
  const response = page.waitForResponse((r) => r.url() === `${api}/api/upload` && r.request().method() === 'POST')
  await page.locator('input[type=file]').setInputFiles(resolve(out, filename))
  const r = await response; assert.equal(r.status(), 200)
  uploaded = await r.json()
  await button('Continue').waitFor()
  await button('Continue').click()
  await heading('Resume Information')
}
async function analyze(jd = '') {
  await button('Continue').click(); await heading('Add a job description')
  await page.locator('.job-description-input').fill(jd)
  const response = page.waitForResponse((r) => r.url() === `${api}/api/analyze` && r.request().method() === 'POST')
  await button(jd ? 'Analyze Against Job Description' : 'Evaluate Resume Only').click()
  const r = await response; assert.equal(r.status(), 200); analysis = (await r.json()).analysis
  await heading('Analysis Result')
  // Results are tabbed; improvement scenarios work in the Improve tab.
  await page.getByRole('tab', { name: 'Improve' }).click()
}
const workspace = () => page.getByRole('region', { name: 'Resume improvement workspace' })
try {
  await page.goto(base)
  await scenario('Authentication required fields and malformed email', async () => {
    await button('Sign In').click()
    assert.equal(await page.locator('input:invalid').count(), 2)
    await page.getByLabel('Work email').fill('invalid')
    assert.equal(await page.getByLabel('Work email').evaluate((node) => node.validity.typeMismatch), true)
  })
  await scenario('Signup connects to isolated API and opens step 1', async () => {
    await button('Create an account').click()
    await page.getByLabel('Full name').fill('Synthetic QA')
    await page.getByLabel('Work email').fill(email)
    await page.getByLabel('Password').fill(password)
    const response = page.waitForResponse(`${api}/api/signup`)
    await button('Create Account').click(); assert.equal((await response).status(), 200)
    await heading('Upload a resume'); assert.equal(await button('Continue').isDisabled(), true)
  })
  await scenario('Dark theme remains selectable and persistent',async()=>{
    await button('Switch to dark theme').click(); await page.reload()
    await button('Switch to light theme').waitFor()
  })
  await scenario('Refresh retains authentication without candidate state', async () => { await page.reload(); await heading('Upload a resume') })
  await scenario('Resume upload is keyboard reachable', async () => {
    const dropzone = page.locator('.dropzone-hero')
    assert.ok(await dropzone.evaluate((node) => node.tabIndex >= 0), 'Upload dropzone cannot receive keyboard focus')
    await dropzone.focus()
    const chooser = page.waitForEvent('filechooser')
    await page.keyboard.press('Enter'); await chooser
  })
  await scenario('PDF upload and candidate extraction', async () => {
    await upload('synthetic.pdf')
    assert.equal(uploaded.candidate.name, 'Alex Example')
    assert.equal(uploaded.candidate.experience.length, 2)
    assert.equal(uploaded.candidate.projects.length, 2)
    for (const skill of ['Python', 'SQL', 'React', 'Node.js', 'C++', 'C#']) assert.ok(uploaded.candidate.skills.includes(skill), skill)
    const text = await visibleText()
    for (const textPart of ['Alex Example', 'Example Labs', 'Fictional Systems', 'Portfolio Dashboard']) assert.ok(text.includes(textPart), textPart)
  })
  await scenario('Back and continue preserve extracted candidate', async () => {
    await button('Back').click(); await heading('Upload a resume')
    await button('Continue').click(); await heading('Resume Information')
    assert.ok((await visibleText()).includes('Example Labs'))
  })
  await scenario('Resume-only evaluation displays server score and no JD fit', async () => {
    await analyze()
    assert.equal(analysis.job_fit_score, null)
    assert.ok((await page.locator('.score-number').first().innerText()).includes(String(analysis.overall_score)))
  })
  await scenario('Generate local suggestions preserves source and score', async () => {
    await button('Generate suggestions').click()
    await workspace().locator('textarea').first().waitFor()
    assert.ok((await workspace().innerText()).includes('Utilized Python in order to prepare reports.'))
    assert.equal(await workspace().locator('textarea').first().inputValue(), 'Used Python to prepare reports.')
  })
  await scenario('Accept reject edit and restore are reversible', async () => {
    const card = workspace().locator('article').first()
    await card.getByRole('button', { name: 'Accept draft', exact: true }).click()
    assert.ok((await card.innerText()).includes('Status: accepted'))
    await card.getByRole('button', { name: 'Reject', exact: true }).click()
    assert.ok((await card.innerText()).includes('Status: rejected'))
    await card.locator('textarea').fill('User verified résumé edit — <script>no execution</script>')
    assert.ok((await card.innerText()).includes('not automatically verified'))
    await card.getByRole('button', { name: 'Accept draft', exact: true }).click()
    assert.ok((await card.innerText()).includes('Status: accepted'))
    await card.getByRole('button', { name: 'Restore original', exact: true }).click()
    assert.equal(await card.locator('textarea').inputValue(), 'Utilized Python in order to prepare reports.')
    assert.ok((await card.innerText()).includes('Status: restored'))
  })
  await scenario('Checklist complete not-applicable pending and duplicate actions', async () => {
    const select = workspace().locator('select').first()
    for (const value of ['complete', 'complete', 'not_applicable', 'pending']) {
      await select.selectOption(value)
      assert.equal(await select.inputValue(), value)
      assert.ok((await workspace().innerText()).includes(value === 'complete' ? '1 completed' : value === 'not_applicable' ? '1 not applicable' : '0 completed'))
    }
  })
  await scenario('AI wording suggestions are an explicit, separate action', async () => {
    assert.equal(await workspace().getByRole('button', { name: 'Suggest stronger wording with AI' }).count(), 1)
  })
  await scenario('Improvement TXT contains original current edits and decisions', async () => {
    const card = workspace().locator('article').first()
    await card.locator('textarea').fill('Verified résumé wording — SQL')
    await card.getByRole('button', { name: 'Accept draft', exact: true }).click()
    const event = page.waitForEvent('download'); await button('Download improvement report (.txt)').click()
    const download = await event; assert.equal(download.suggestedFilename(), 'resume-improvement-report.txt')
    const file = resolve(out, download.suggestedFilename()); await download.saveAs(file)
    const text = await readFile(file, 'utf8')
    for (const part of ['Verified résumé wording — SQL', 'accepted', 'Original: Utilized Python', 'User edited: yes']) assert.ok(text.includes(part), part)
  })
  await scenario('Analysis TXT downloads current candidate and server score', async () => {
    const event = page.waitForEvent('download'); await button('Download summary (.txt)').click()
    const download = await event; const file = resolve(out, 'analysis.txt'); await download.saveAs(file)
    const text = await readFile(file, 'utf8'); assert.ok(text.includes('Alex Example')); assert.ok(text.includes(`Overall Score: ${analysis.overall_score}`))
  })
  for (const [width, height] of [[1440,900],[1366,768],[768,1024],[390,844],[360,800]]) {
    await scenario(`Results and improvements viewport ${width}x${height}`, async () => {
      await page.setViewportSize({ width, height })
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)
      assert.equal(overflow, false, 'Horizontal overflow')
      assert.ok(await workspace().locator('textarea').first().isVisible())
      await page.screenshot({ path: resolve(out, `results-${width}.png`), fullPage: true })
    })
  }
  await scenario('Browser print renders analysis and edited improvement report', async () => {
    await page.emulateMedia({ media: 'print' })
    assert.equal(await page.locator('.print-report').isVisible(), true)
    assert.ok((await page.locator('.print-report').innerText()).includes('Verified résumé wording — SQL'))
    assert.ok((await page.locator('.print-report').innerText()).includes('Vocabulary matching cannot establish proficiency'))
    assert.equal(await page.locator('.print-report .match-explanation h2').evaluate(node=>getComputedStyle(node).color),'rgb(17, 24, 39)')
    assert.equal(await page.locator('body').evaluate(node=>getComputedStyle(node).backgroundColor),'rgb(255, 255, 255)')
    await page.pdf({ path: resolve(out, 'browser-print.pdf'), format: 'A4', printBackground: true })
    await page.emulateMedia({ media: 'screen' })
  })
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.emulateMedia({ media: 'screen' })
  await scenario('Refresh drops session-only drafts but keeps login', async () => {
    await page.reload(); await heading('Upload a resume'); assert.equal(await page.locator('.improvement-workspace').count(), 0)
  })
  await scenario('DOCX upload and alias JD explanation agree with backend', async () => {
    await upload('synthetic.docx')
    await analyze('Required: Python, React.js, sklearn, NLP, NodeJS, REST APIs, dotnet. Preferred: Docker. 2 years experience. BSc Computer Science.')
    for (const row of analysis.explanation.requirements) assert.ok((await page.locator('.match-explanation').first().innerText()).includes(row.skill), row.skill)
    assert.equal(analysis.explanation.requirements.find((r) => r.skill.toLowerCase() === 'docker').status, 'not_evidenced')
    // Existing policy uses month endpoints, not inclusive end months: (23 + 11) / 12.
    assert.equal(analysis.total_experience_years, 2.83)
  })
  await scenario('Old analysis without explanation remains readable',async()=>{
    await button('Back').click()
    await page.route('**/api/analyze',async(route)=>{
      const response=await route.fetch(); const data=await response.json(); delete data.analysis.explanation
      await route.fulfill({response,json:data})
    })
    await button('Analyze Against Job Description').click(); await heading('Analysis Result')
    assert.ok((await visibleText()).includes('older analysis'))
    await page.unroute('**/api/analyze')
  })
  await scenario('Improvement endpoint failure recovers without losing analysis', async () => {
    await page.route('**/api/improvements', (route) => route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Temporary QA failure' }) }))
    await button('Generate suggestions').click(); await workspace().getByRole('alert').waitFor()
    assert.equal(await button('Generate suggestions').isDisabled(), false)
    await page.unroute('**/api/improvements')
    await button('Generate suggestions').click(); await workspace().locator('textarea').first().waitFor()
  })
  await scenario('Logout removes candidate and drafts; back cannot reveal them', async () => {
    await button('Log out').click(); await heading('Welcome back')
    await page.goBack(); if (page.url() !== base + '/') await page.goto(base)
    await heading('Welcome back'); assert.equal(await page.locator('.improvement-workspace').count(), 0)
  })
  await scenario('Wrong password and unknown account return safe errors', async () => {
    for (const account of [email, 'unknown@example.invalid']) {
      await page.getByLabel('Work email').fill(account); await page.getByLabel('Password').fill('incorrect-synthetic')
      await button('Sign In').click(); await page.locator('.status.error').waitFor()
      assert.ok((await page.locator('.status.error').innerText()).includes('Invalid'))
    }
  })
  await scenario('Login restores authenticated navigation and history', async () => {
    await page.getByLabel('Work email').fill(email); await page.getByLabel('Password').fill(password)
    await button('Sign In').click(); await heading('Upload a resume')
    await button('History').click(); assert.ok((await visibleText()).includes('Alex Example'))
  })
  await button('Upload').click()
  await scenario('Rejected replacement upload preserves valid candidate', async () => {
    await upload('synthetic.docx'); await button('Back').click()
    await page.locator('input[type=file]').setInputFiles({ name: 'unsupported.txt', mimeType: 'text/plain', buffer: Buffer.from('Harmless text') })
    await page.locator('.status.error').waitFor()
    assert.equal(await button('Continue').isDisabled(), false, 'Rejected upload erased the valid candidate')
    await button('Continue').click(); assert.ok((await visibleText()).includes('Alex Example'))
  })
  // Recover to a known step without changing storage or bypassing authentication.
  await page.reload(); await heading('Upload a resume')
  for (const [name, mimeType, buffer] of [
    ['empty.pdf','application/pdf',Buffer.alloc(0)],
    ['corrupt.pdf','application/pdf',Buffer.from('%PDF-1.7\ninvalid')],
    ['corrupt.docx','application/vnd.openxmlformats-officedocument.wordprocessingml.document',Buffer.from('invalid')],
    ['misleading.pdf','text/plain',Buffer.from('Harmless plain text')],
    ['large.pdf','application/pdf',Buffer.alloc(10*1024*1024+1)],
  ]) await scenario(`Rejected upload: ${name}`, async () => {
    await page.locator('input[type=file]').setInputFiles({ name, mimeType, buffer })
    await page.locator('.status.error').waitFor(); assert.equal(await button('Continue').isDisabled(), true)
  })
  await scenario('Valid PDF with unexpected MIME is parsed by content', async () => {
    const response = page.waitForResponse(`${api}/api/upload`)
    await page.locator('input[type=file]').setInputFiles({ name: 'mime.pdf', mimeType: 'application/octet-stream', buffer: await readFile(resolve(out,'synthetic.pdf')) })
    assert.equal((await response).status(),200); await button('Continue').click(); await heading('Resume Information')
  })
  await scenario('JD file picker supports keyboard and actual text upload', async () => {
    await button('Continue').click(); await button('Upload File').click()
    const picker = page.getByRole('button', { name: 'Upload job description file' })
    await picker.focus(); const chooser = page.waitForEvent('filechooser'); await page.keyboard.press('Space'); await chooser
    await page.locator('input[type=file]').setInputFiles({ name: 'job.txt', mimeType: 'text/plain', buffer: Buffer.from('Required skills: Python, Docker') })
    const response = page.waitForResponse(`${api}/api/analyze`)
    await button('Analyze Against Job Description').click(); assert.equal((await response).status(),200); await heading('Analysis Result')
  })
  await scenario('Invalid JSON and network failure recover generation controls', async () => {
    for (const failure of ['invalid-json','offline']) {
      await page.route('**/api/improvements', (route) => failure === 'offline' ? route.abort('connectionrefused') : route.fulfill({ status:200, contentType:'application/json',body:'not json' }))
      await button('Generate suggestions').click(); await workspace().getByRole('alert').waitFor()
      assert.equal(await button('Generate suggestions').isDisabled(),false)
      await page.unroute('**/api/improvements')
    }
    await button('Generate suggestions').click(); await workspace().locator('textarea').first().waitFor()
  })
  await scenario('Server 401 clears session and private drafts', async () => {
    await page.route('**/api/improvements', (route) => route.fulfill({status:401,contentType:'application/json',body:'{"detail":"Not authenticated."}'}))
    await button('Generate suggestions').click(); await heading('Welcome back')
    assert.equal(await page.locator('.improvement-workspace').count(),0)
    await page.unroute('**/api/improvements')
  })
  for (const [width,height] of [[1440,900],[1366,768],[768,1024],[390,844],[360,800]]) await scenario(`Authentication viewport ${width}x${height}`,async()=>{
    await page.setViewportSize({width,height})
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false)
    await page.getByLabel('Work email').focus(); await page.keyboard.press('Tab')
    assert.equal(await page.getByLabel('Password').evaluate(node=>node===document.activeElement),true)
    await page.screenshot({path:resolve(out,`login-${width}.png`),fullPage:true})
  })
  await scenario('Second UI account cannot access first account improvements', async () => {
    await button('Create an account').click(); await page.getByLabel('Full name').fill('Second Synthetic QA')
    await page.getByLabel('Work email').fill(`qa-${randomUUID()}@example.invalid`); await page.getByLabel('Password').fill(randomUUID())
    const response = page.waitForResponse(`${api}/api/signup`); await button('Create Account').click()
    const second = await (await response).json(); await heading('Upload a resume')
    const denied = await context.request.post(`${api}/api/improvements`, {headers:{Authorization:`Bearer ${second.token}`},form:{resume_id:uploaded.resume_id,analysis_id:analysis.analysis_id}})
    assert.equal(denied.status(),409)
    await button('History').click(); assert.ok(!(await visibleText()).includes('Alex Example'))
  })
  await button('Upload').click(); await upload('synthetic.docx'); await button('Continue').click()
  await scenario('Empty analysis response displays an error and allows retry',async()=>{
    await page.route('**/api/analyze',route=>route.fulfill({status:200,contentType:'application/json',body:'{"analysis":{}}'}))
    await button('Evaluate Resume Only').click()
    await page.locator('.status.error').waitFor()
    await heading('Add a job description')
    await page.unroute('**/api/analyze')
    await button('Evaluate Resume Only').click(); await heading('Analysis Result')
  })
} finally {
  const summary = { browser: browser.version(), mode: 'headless', platform: process.platform, results, errors, consoleErrors, failures, unexpected }
  await writeFile(resolve(out, 'browser-results.json'), JSON.stringify(summary, null, 2))
  console.log(JSON.stringify({ browser: summary.browser, passed: results.filter((r) => r.result === 'passed').length, failed: results.filter((r) => r.result === 'failed').length, runtimeErrors: errors.length, unexpectedOrigins: unexpected.length }))
  await browser.close()
}
if (results.some((r) => r.result === 'failed')) process.exitCode = 1
