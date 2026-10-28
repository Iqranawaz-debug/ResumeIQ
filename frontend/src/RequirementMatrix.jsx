import React from 'react'
import { EVIDENCE_BASIS, REQUIREMENT_STATUS, groupRequirements } from './resultsModel.js'

const list = (value) => (Array.isArray(value) ? value : [])

function StatusChip({ status }) {
  const meta = REQUIREMENT_STATUS[status] || REQUIREMENT_STATUS.unclear
  return <span className={`status-chip tone-${meta.tone}`}>{meta.label}</span>
}

export default function RequirementMatrix({ lines, aiEvidence }) {
  if (!lines) return <p className="empty-state">Add a job description to compare the resume requirement by requirement.</p>
  const groups = groupRequirements(lines.rows)
  const counts = lines.counts || {}
  const aiSkills = Object.entries(aiEvidence || {})

  return (
    <section className="requirement-matrix" aria-label="Requirement-by-requirement review">
      <div className="requirement-counts" role="list" aria-label="Requirement status counts">
        {Object.entries(REQUIREMENT_STATUS).map(([status, meta]) => (
          <span role="listitem" key={status} className={`count-pill tone-${meta.tone}`}>
            <strong>{counts[status] || 0}</strong> {meta.label}
          </span>
        ))}
      </div>
      <p className="wizard-note">{lines.note}</p>
      {!groups.length && <p className="empty-state">No requirement statements were recognized in this job description.</p>}
      {groups.map((group) => (
        <div className="requirement-group" key={group.context}>
          <h3>{group.label}</h3>
          <ul className="requirement-list">
            {group.rows.map((row, index) => (
              <li className="requirement-row" key={`${group.context}-${index}`}>
                <StatusChip status={row.status} />
                <div className="requirement-body">
                  <p className="requirement-text">{row.text}</p>
                  <p className="requirement-reason">{row.reason}</p>
                  <p className={`requirement-basis basis-${row.basis}`}>{EVIDENCE_BASIS[row.basis] || EVIDENCE_BASIS.none} · {row.type}</p>
                  {list(row.evidence).map((record, i) => (
                    <blockquote className="evidence-quote" key={i}>
                      {record.excerpt}
                      <cite>{record.section}{Number.isInteger(record.entry_index) ? ` entry ${record.entry_index + 1}` : ''}</cite>
                    </blockquote>
                  ))}
                </div>
              </li>
            ))}
          </ul>
        </div>
      ))}
      {lines.bounded && <p className="wizard-note">Showing the first 40 requirement statements.</p>}
      {aiSkills.length > 0 && (
        <div className="requirement-group">
          <h3>AI-reported skill matches</h3>
          <p className="wizard-note">The AI provider judged these skills as matched. "Inferred" means the skill name does not appear in the resume data it received.</p>
          <ul className="ai-evidence-list">
            {aiSkills.map(([skill, basis]) => (
              <li key={skill}>
                <span>{skill}</span>
                <span className={`status-chip tone-${basis === 'explicit' ? 'success' : 'warning'}`}>
                  {basis === 'explicit' ? 'Found in resume' : 'Inferred by AI'}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}
