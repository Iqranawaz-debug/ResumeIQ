import React from 'react'
import ExplainableResults from './ExplainableResults'
import { REVIEW_STATUSES } from './recruiterState'

export default function RecruiterComparison({ rows, busy, onReview }) {
  return <div className="recruiter-comparison" aria-label="Candidate comparison">
    {(rows || []).map((row) => <article className="candidate-card" key={row.id} aria-label={`Candidate ${row.name || 'Name not found'}`}>
      <h3>{row.name || 'Name not found'}</h3>
      <p>{row.filename}</p>
      <label>Review status for {row.name || row.filename}
        <select value={row.status} disabled={busy} onChange={(event) => onReview(row, event.target.value)}>
          {REVIEW_STATUSES.map((status) => <option key={status}>{status}</option>)}
        </select>
      </label>
      <p>Status changes are human decisions and do not change scores.</p>
      <p>Score source: {row.analysis?.job_fit_method || 'Not analyzed'}</p>
      {row.analysis ? <p>Overall: {row.analysis.overall_score} / 100 · Resume quality: {row.analysis.resume_quality_score} · Job fit: {row.analysis.job_fit_score ?? 'Unavailable'}</p> : <p>Analysis pending or outdated. Analyze against the current job description.</p>}
      <h4>Recognized skills</h4><p>{(row.candidate?.skills || []).join(', ') || 'Not evidenced in resume'}</p>
      <h4>Professional experience</h4>
      {(row.candidate?.experience || []).length ? <ul>{row.candidate.experience.map((entry, index) => <li key={index}>
        {[entry.title, entry.organization, entry.duration].filter(Boolean).join(' · ') || 'Unspecified entry'}
        <ul>{(entry.details || []).map((text, i) => <li key={i}>{text}</li>)}</ul>
      </li>)}</ul> : <p>Not evidenced in resume</p>}
      <h4>Projects (not employment)</h4>
      {(row.candidate?.projects || []).map((entry, index) => <p key={index}>{entry.title || 'Untitled'}: {(entry.details || []).join(' ')}</p>)}
      <h4>Education</h4><p>{(row.candidate?.education || []).join('; ') || 'Not evidenced in resume'}</p>
      <p>Education text does not verify graduation or qualifications.</p>
      <ExplainableResults explanation={row.analysis?.explanation} />
    </article>)}
  </div>
}
