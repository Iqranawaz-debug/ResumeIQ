export const API_BASE_URL = (import.meta.env?.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '')

// Public deployments set VITE_DEMO_MODE=true to steer visitors to the fictional sample.
export const DEMO_MODE = import.meta.env?.VITE_DEMO_MODE === 'true'
export const DEMO_NOTICE = 'Public demo: please use the fictional sample rather than a real resume. Demo accounts and data are temporary and may be erased when the server restarts. The first request can take up to a minute while the server wakes up.'

export async function apiRequest(url, { signal, timeoutMs = 45000, ...options } = {}) {
  const controller = new AbortController()
  let timedOut = false
  const cancel = () => controller.abort()
  if (signal?.aborted) cancel()
  signal?.addEventListener('abort', cancel, { once: true })
  const timer = setTimeout(() => { timedOut = true; controller.abort() }, timeoutMs)
  try {
    const response = await fetch(url, { ...options, signal: controller.signal })
    let data
    try { data = await response.json() } catch { data = null }
    if (!response.ok) {
      if (response.status === 401 && options.headers?.Authorization) {
        window.dispatchEvent(new CustomEvent('resumeiq-session-expired', { detail: options.headers.Authorization }))
      }
      throw new Error(typeof data?.detail === 'string' ? data.detail : `Request failed (${response.status}). Please retry.`)
    }
    if (!data) throw new Error('Server returned an unreadable response. Please retry.')
    return data
  } catch (error) {
    if (timedOut) throw new Error('Request timed out. Please retry.')
    if (error.name === 'AbortError') throw error
    if (error instanceof TypeError) throw new Error('Could not reach the server. Please retry.')
    throw error
  } finally {
    clearTimeout(timer)
    signal?.removeEventListener('abort', cancel)
  }
}

export function analysisForm(mode, text, file, resumeId, useAI = false) {
  const data = new FormData()
  data.append('resume_id', resumeId || '')
  data.append('use_ai', String(Boolean(useAI)))
  if (mode === 'file') {
    if (file) data.append('file', file)
  } else data.append('job_description', text)
  return data
}
