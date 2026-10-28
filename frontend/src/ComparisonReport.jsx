import React from 'react'
import ExplainableResults from './ExplainableResults'
import { EXPORT_FOOTER, scoreLabel } from './recruiterState.js'

const list = (value) => (Array.isArray(value) ? value : [])

// Print-only comparison report, following the PrintableReport pattern (browser print / save as PDF).
// Rows keep the order the reviewer selected. Notes appear only when includeNotes is true.
export default function ComparisonReport({ title, version, generatedAt, rows, includeNotes = false, notice }) {
  return (
    <div className="print-report comparison-print-report">
      <div className="print-header">
        <div className="print-brand">ResumeIQ</div>
        <span className="print-date">Generated {new Date(generatedAt || Date.now()).toLocaleString()}</span>
      </div>
      <div className="print-profile">
        <h1>Candidate comparison</h1>
        <p className="print-contact">{title} · job version {version} · {list(rows).length} candidate{list(rows).length === 1 ? '' : 's'} in the order selected</p>
      </div>
      {notice && <p className="print-section">{notice}</p>}
      {list(rows).map((row) => {
        const analysis = row.analysis || {}
        return (
          <section className="print-section comparison-print-candidate" key={row.id}>
            <h2>{row.name || 'Name not found'}</h2>
            <p className="print-contact">{row.filename}</p>
            <table className="comparison-print-facts">
              <tbody>
                <tr><th scope="row">Review status</th><td>{row.status}</td></tr>
                <tr><th scope="row">Score</th><td>{scoreLabel(analysis)}</td></tr>
                <tr><th scope="row">Years of experience</th><td>{analysis.total_experience_years ?? '—'}</td></tr>
                <tr><th scope="row">Tags</th><td>{list(row.tags).join(', ') || '—'}</td></tr>
                <tr><th scope="row">Matched skills</th><td>{list(row.matched_skill_names || analysis.matched_skills).join(', ') || '—'}</td></tr>
                <tr><th scope="row">Missing skills</th><td>{list(row.missing_skill_names || analysis.missing_skills).join(', ') || '—'}</td></tr>
              </tbody>
            </table>
            {includeNotes && <>
              <h3>Private notes</h3>
              {list(row.notes).length ? <ul>{row.notes.map((note) => <li key={note.id} className="comparison-print-note">{note.text}</li>)}</ul> : <p>No notes.</p>}
            </>}
            <ExplainableResults explanation={analysis.explanation} expandLimitations />
          </section>
        )
      })}
      <p className="print-footer">{EXPORT_FOOTER}</p>
    </div>
  )
}
