import React from 'react'
import { checklistCounts, improvementReport } from './improvementState.js'

export default function ImprovementWorkspace({ data, draft, busy, error, canGenerate, onGenerate, onAction }) {
  const counts = checklistCounts(draft)
  function download() {
    const blob = new Blob([improvementReport(data, draft)], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'resume-improvement-report.txt'
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  }
  return <section className="improvement-workspace" aria-label="Resume improvement workspace">
    <h2>Improve your resume wording</h2>
    <p>Review drafts without changing the original resume or its score. Changes are kept only in this active session; download your report before leaving.</p>
    <div className="improvement-actions">
      <button type="button" className="evaluate-button" disabled={busy || !canGenerate} onClick={() => onGenerate()}>Generate suggestions</button>
    </div>
    <p className="wizard-note">Suggestions are generated locally; no resume content is sent to an AI provider.</p>
    {!canGenerate && <p>Analyze the current resume to enable improvement suggestions. Older reports remain readable.</p>}
    {busy && <p role="status">Preparing suggestions…</p>}
    {error && <p className="status error" role="alert">{error}</p>}
    {!data ? <p>No improvements generated yet.</p> : <>
      <p role="status">{data.note}</p>
      {data.bounded && <p>Showing a bounded selection of improvements. Review the rest of your resume manually.</p>}
      {(data.suggestions || []).length === 0 && <p>No safe automatic wording changes identified. Review the checklist for clarification opportunities.</p>}
      {(data.suggestions || []).map((item) => {
        const state = draft?.suggestions?.[item.id] || { text: item.suggested_text || '', status: 'pending' }
        return <article key={item.id} className="improvement-card" aria-label={`${item.section} entry ${item.entry_index + 1}`}>
          <h3>{item.section} entry {item.entry_index + 1}, description {item.detail_index + 1}</h3>
          <p>{item.feedback} · {item.source} · <strong>Status: {state.status}</strong></p>
          <div className="requirements-grid">
            <div><h4>Original content</h4><blockquote>{item.original_text}</blockquote></div>
            <div><label htmlFor={`draft-${item.id}`}>Suggested improvement — edit draft</label>
              <textarea id={`draft-${item.id}`} value={state.text} maxLength={2000} rows={4}
                placeholder="Clarify using facts you can verify; no automatic rewrite was generated."
                onChange={(event) => onAction({ type: 'edit', id: item.id, text: event.target.value })} />
            </div>
          </div>
          <p>{item.reason}</p>
          <p className="wizard-note">{state.edited ? 'User-edited text is not automatically verified. Confirm all claims before accepting.' : 'Review meaning and factual accuracy before accepting.'}</p>
          <div className="improvement-actions">
            <button type="button" className="link-button" disabled={!state.text.trim()} onClick={() => onAction({ type: 'accept', id: item.id })}>Accept draft</button>
            <button type="button" className="link-button" onClick={() => onAction({ type: 'reject', id: item.id })}>Reject</button>
            <button type="button" className="link-button" onClick={() => onAction({ type: 'restore', id: item.id })}>Restore original</button>
          </div>
        </article>
      })}
      <h3>Improvement checklist</h3>
      <p role="status">{counts.completed} completed · {counts.remaining} pending · {counts.notApplicable} not applicable · {counts.total} total</p>
      <ul className="improvement-checklist">{(data.checklist || []).map((item) => <li key={item.id}>
        <label htmlFor={`check-${item.id}`}>{item.category}: {item.text}</label>
        <select id={`check-${item.id}`} value={draft?.checklist?.[item.id] || 'pending'} onChange={(event) => onAction({ type: 'checklist', id: item.id, status: event.target.value })}>
          <option value="pending">Pending</option><option value="complete">Complete</option><option value="not_applicable">Not applicable</option>
        </select>
      </li>)}</ul>
      <p>Checklist completion is not a score or a hiring recommendation.</p>
      {(data.feedback || []).map((item, index) => <p key={index}>{item.section} entry {item.entry_index + 1}: {item.label}. {item.note}</p>)}
      <button type="button" className="link-button" onClick={download}>Download improvement report (.txt)</button>
      <p>Use “Generate Full Report (PDF)” below to open the browser print/save-as-PDF dialog, including current drafts.</p>
      <details><summary>Improvement limits</summary><ul>{(data.limitations || []).map((item, index) => <li key={index}>{item}</li>)}</ul></details>
    </>}
  </section>
}
