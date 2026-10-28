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

// Recruiter workspace endpoints. Every path segment is URL-encoded (tags may contain spaces, # or +).
export function workspaceUrl(...segments) {
  return [`${API_BASE_URL}/api/workspaces`, ...segments.map((part) => encodeURIComponent(part))].join('/')
}

function jsonRequest(token, method, body, options = {}) {
  return {
    ...options,
    method,
    headers: { Authorization: `Bearer ${token}`, ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  }
}

export function addCandidateNote(token, groupId, candidateId, text, options) {
  return apiRequest(workspaceUrl(groupId, 'candidates', candidateId, 'notes'), jsonRequest(token, 'POST', { text }, options))
}

export function editCandidateNote(token, groupId, candidateId, noteId, text, options) {
  return apiRequest(workspaceUrl(groupId, 'candidates', candidateId, 'notes', noteId), jsonRequest(token, 'PATCH', { text }, options))
}

export function deleteCandidateNote(token, groupId, candidateId, noteId, options) {
  return apiRequest(workspaceUrl(groupId, 'candidates', candidateId, 'notes', noteId), jsonRequest(token, 'DELETE', undefined, options))
}

export function addCandidateTag(token, groupId, candidateId, tag, options) {
  return apiRequest(workspaceUrl(groupId, 'candidates', candidateId, 'tags'), jsonRequest(token, 'POST', { tag }, options))
}

export function removeCandidateTag(token, groupId, candidateId, tag, options) {
  return apiRequest(workspaceUrl(groupId, 'candidates', candidateId, 'tags', tag), jsonRequest(token, 'DELETE', undefined, options))
}

// Returns {filename, content, include_notes}; the caller saves content as a .csv file.
export function exportComparisonCsv(token, groupId, { candidateIds, version, includeNotes = false }, options) {
  return apiRequest(workspaceUrl(groupId, 'comparison', 'csv'),
    jsonRequest(token, 'POST', { candidate_ids: candidateIds, version, include_notes: Boolean(includeNotes) }, options))
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
