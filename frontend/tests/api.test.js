import { test, afterEach } from 'node:test'
import assert from 'node:assert/strict'
import { apiRequest, analysisForm, DEMO_MODE, DEMO_NOTICE } from '../src/api.js'

test('public demo notice is off unless VITE_DEMO_MODE=true at build time', () => {
  assert.equal(DEMO_MODE, false)
  assert.match(DEMO_NOTICE, /fictional sample/)
})

const originalFetch = globalThis.fetch
const originalWindow = globalThis.window
afterEach(() => { globalThis.fetch = originalFetch; globalThis.window = originalWindow })

test('file mode never submits hidden text, including when no file is selected', () => {
  const form = analysisForm('file', 'hidden text', null, 'resume-id')
  assert.equal(form.get('job_description'), null)
  assert.equal(form.get('resume_id'), 'resume-id')
})

test('text mode never submits a hidden file', () => {
  const form = analysisForm('text', 'Python', new Blob(['hidden']), 'id')
  assert.equal(form.get('file'), null)
  assert.equal(form.get('job_description'), 'Python')
})

test('AI job matching is opt-in and defaults to local', () => {
  assert.equal(analysisForm('text', 'Python', null, 'id').get('use_ai'), 'false')
  assert.equal(analysisForm('text', 'Python', null, 'id', true).get('use_ai'), 'true')
})

test('HTTP errors normalize non-string validation responses', async () => {
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: [{ input: 'sensitive' }] }), { status: 422 })
  await assert.rejects(apiRequest('/test'), { message: 'Request failed (422). Please retry.' })
})

test('authenticated 401 emits an expiry event for the relevant token only', async () => {
  let event
  globalThis.window = { dispatchEvent: (value) => { event = value } }
  globalThis.fetch = async () => new Response('{"detail":"Not authenticated."}', { status: 401 })
  await assert.rejects(apiRequest('/test', { headers: { Authorization: 'Bearer synthetic' } }))
  assert.equal(event.type, 'resumeiq-session-expired')
  assert.equal(event.detail, 'Bearer synthetic')
})

test('timeouts cancel the transport with a useful message', async () => {
  globalThis.fetch = (_, { signal }) => new Promise((resolve, reject) => {
    signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))
  })
  await assert.rejects(apiRequest('/test', { timeoutMs: 5 }), /timed out/)
})

test('caller cancellation remains distinguishable from failure', async () => {
  const controller = new AbortController()
  globalThis.fetch = (_, { signal }) => new Promise((resolve, reject) => {
    signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))
  })
  const pending = apiRequest('/test', { signal: controller.signal })
  controller.abort()
  await assert.rejects(pending, { name: 'AbortError' })
})

test('unreadable success responses are rejected', async () => {
  globalThis.fetch = async () => new Response('not json')
  await assert.rejects(apiRequest('/test'), /unreadable response/)
})
