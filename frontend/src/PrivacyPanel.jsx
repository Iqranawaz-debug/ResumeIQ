import React, { useEffect, useState } from 'react'
import { API_BASE_URL, apiRequest } from './api.js'
import { retentionText } from './resultsModel.js'

const DATA_URL = `${API_BASE_URL}/api/me/data`

export default function PrivacyPanel({ token, onDeleted, initialSummary = null }) {
  const [summary, setSummary] = useState(initialSummary)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    apiRequest(DATA_URL, { signal: controller.signal, headers: { Authorization: `Bearer ${token}` } })
      .then((data) => { if (!controller.signal.aborted) setSummary(data) })
      .catch((err) => { if (!controller.signal.aborted) setError(err.message) })
    return () => controller.abort()
  }, [token])

  async function erase() {
    if (!window.confirm('Delete your resume data, analyses, history and recruiter workspaces? Your account stays.')) return
    setBusy(true); setError(''); setMessage('')
    try {
      const data = await apiRequest(DATA_URL, { method: 'DELETE', headers: { Authorization: `Bearer ${token}` } })
      setMessage(data.message)
      onDeleted?.()
      setSummary(await apiRequest(DATA_URL, { headers: { Authorization: `Bearer ${token}` } }))
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="privacy-panel" aria-label="Privacy and data">
      <h2>What ResumeIQ stores</h2>
      {summary ? (
        <ul className="privacy-facts">
          <li>Uploaded files are parsed and discarded; the file itself is never kept.</li>
          <li>Extracted resume details: {summary.resume_stored ? 'stored' : 'none stored'}{summary.analysis_stored ? ', with an analysis' : ''}.</li>
          <li>Evaluation history: {summary.history_entries} entr{summary.history_entries === 1 ? 'y' : 'ies'}.</li>
          <li>Resume version snapshots (scores, skills and requirement statuses only): {summary.versions ?? 0}.</li>
          <li>Recruiter workspaces: {summary.workspaces} ({summary.candidates} candidate{summary.candidates === 1 ? '' : 's'}).</li>
          <li>{summary.storage === 'database'
            ? `Everything above is saved in this server's database so it survives restarts, and is erased after ${retentionText(summary.retention_seconds)} without changes.`
            : `Everything above is held in server memory only and is erased after ${retentionText(summary.retention_seconds)} of inactivity or when the server restarts.`}</li>
        </ul>
      ) : !error && <p role="status">Loading…</p>}
      <h2>When AI is used</h2>
      <ul className="privacy-facts">
        <li>AI is used only when you tick an AI option{summary && !summary.ai_provider_configured ? ' — no AI provider is configured on this server, so nothing is sent' : ''}{summary?.ai_provider_configured && summary.ai_provider ? `. When you do, data is sent to ${summary.ai_provider}` : ''}.</li>
        <li>AI job matching sends extracted skills, education, and employment titles, dates and descriptions (contact details redacted on a best-effort basis), plus the job description.</li>
        <li>AI wording suggestions send only flagged employment bullets that contain no names, organizations, contact details or sensitive attributes.</li>
        <li>Projects, evidence quotations and your uploaded file are never sent.</li>
      </ul>
      {error && <p className="status error" role="alert">{error}</p>}
      {message && <p className="status success" role="status">{message}</p>}
      <button type="button" className="evaluate-button danger-button" disabled={busy} onClick={erase}>
        {busy ? 'Deleting…' : 'Delete my data now'}
      </button>
    </section>
  )
}
