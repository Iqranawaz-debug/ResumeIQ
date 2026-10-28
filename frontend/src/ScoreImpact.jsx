import React from 'react'
import { formatDelta } from './resultsModel.js'

const list = (value) => (Array.isArray(value) ? value : [])

export default function ScoreImpact({ impacts, weakFitCap = false }) {
  if (!impacts) return null
  const items = list(impacts.items)
  return (
    <section className="score-impact" aria-label="What would change this score">
      <h2>What would change this score</h2>
      <p className="wizard-note">{impacts.note}</p>
      {impacts.scope_note && <p className="wizard-note">{impacts.scope_note}</p>}
      {weakFitCap && <p className="wizard-note">The weak job-fit cap (49) is currently limiting the overall score, so resume-quality edits alone may not raise it.</p>}
      {items.length === 0 ? <p className="empty-state">No score-raising edits were identified by the current rules.</p> : (
        <ol className="impact-list">
          {items.map((item) => (
            <li className="impact-row" key={item.action}>
              <div>
                <p className="impact-action">{item.action}</p>
                <p className="impact-condition">{item.condition}</p>
              </div>
              <dl className="impact-deltas">
                <div className={item.overall_delta > 0 ? 'delta-up' : ''}><dt>Overall</dt><dd>{formatDelta(item.overall_delta)}</dd></div>
                <div><dt>Job fit</dt><dd>{formatDelta(item.job_fit_delta)}</dd></div>
                <div><dt>Quality</dt><dd>{formatDelta(item.quality_delta)}</dd></div>
              </dl>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}
