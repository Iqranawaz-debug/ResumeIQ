import React from 'react'
import { REQUIREMENT_STATUS, formatDelta } from './resultsModel.js'

const list = (value) => (Array.isArray(value) ? value : [])
const label = (status) => (REQUIREMENT_STATUS[status] || REQUIREMENT_STATUS.unclear).label

export default function VersionComparison({ versions }) {
  const items = list(versions?.list)
  const comparison = versions?.comparison
  if (items.length < 2 || !comparison) {
    return <section className="version-comparison" aria-label="Resume version comparison">
      <h2>Compare resume versions</h2>
      <p className="empty-state">Revise the resume, choose “Evaluate Another Resume”, upload the new version and analyze it against the same job description. Your two most recent analyses are compared here.</p>
    </section>
  }
  const [newer, older] = items
  const rows = [
    ['Overall score', 'overall_score'], ['Resume quality', 'resume_quality_score'],
    ['Job fit', 'job_fit_score'], ['Years of dated employment', 'experience_years'],
  ]
  return (
    <section className="version-comparison" aria-label="Resume version comparison">
      <h2>Compare resume versions</h2>
      {list(comparison.notes).map((note) => <p key={note} className={/not (directly|equally)/.test(note) ? 'banner banner-warning' : 'wizard-note'}>{note}</p>)}
      <div className="table-scroll">
        <table className="history-table version-table">
          <thead><tr><th scope="col">Measure</th><th scope="col">Previous<br /><small>{older.filename}</small></th><th scope="col">Latest<br /><small>{newer.filename}</small></th><th scope="col">Change</th></tr></thead>
          <tbody>
            {rows.map(([name, key]) => (
              <tr key={key}>
                <th scope="row">{name}</th>
                <td>{older[key] ?? '—'}</td>
                <td>{newer[key] ?? '—'}</td>
                <td className={comparison.deltas[key] > 0 ? 'delta-up' : comparison.deltas[key] < 0 ? 'delta-down' : ''}>
                  {comparison.deltas[key] === null ? '—' : formatDelta(Math.round(comparison.deltas[key] * 100) / 100)}
                </td>
              </tr>
            ))}
            <tr><th scope="row">Recommendation band</th><td>{older.recommendation}</td><td>{newer.recommendation}</td><td /></tr>
          </tbody>
        </table>
      </div>
      <div className="version-columns">
        <div>
          <h3>Skills added</h3>
          {list(comparison.skills_added).length ? <ul className="skill-list">{comparison.skills_added.map((s) => <li key={s}>{s}</li>)}</ul> : <p className="empty-state">None</p>}
        </div>
        <div>
          <h3>Skills removed</h3>
          {list(comparison.skills_removed).length ? <ul className="skill-list skill-list-missing">{comparison.skills_removed.map((s) => <li key={s}>{s}</li>)}</ul> : <p className="empty-state">None</p>}
        </div>
      </div>
      <h3>Requirement changes</h3>
      {list(comparison.requirement_changes).length ? (
        <ul className="requirement-list">
          {comparison.requirement_changes.map((row) => (
            <li className="requirement-row" key={row.text}>
              <span className="field-label">{label(row.from)} → {label(row.to)}</span>
              <p className="requirement-text">{row.text}</p>
            </li>
          ))}
        </ul>
      ) : <p className="empty-state">{comparison.same_job ? 'No requirement changed status.' : 'Requirement statuses are only compared for the same job description.'}</p>}
    </section>
  )
}
