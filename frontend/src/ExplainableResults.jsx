import React from 'react'

const list = (value) => Array.isArray(value) ? value : []
const number = (value) => Number.isFinite(value)

export default function ExplainableResults({ explanation, expandLimitations = false }) {
  if (!explanation) return <p className="field-label">Detailed explanation is unavailable for this older analysis.</p>
  const requirements = list(explanation.requirements)
  const matched = requirements.filter((item) => item.status === 'matched')
  const missing = requirements.filter((item) => item.status === 'not_evidenced')
  const blend = explanation.blend

  return (
    <section className="match-explanation" aria-label="Score explanation">
      <h2>Why this score?</h2>
      <p>{explanation.summary}</p>
      <p className="wizard-note">{explanation.advisory}</p>
      {number(explanation.overall_score) && <p><strong>Overall: {explanation.overall_score} / {explanation.scale || 100}</strong></p>}
      {blend && <p>
        Resume quality contributes {number(blend.resume_quality_points) ? blend.resume_quality_points.toFixed(2) : '—'} points;
        job fit contributes {number(blend.job_fit_points) ? blend.job_fit_points.toFixed(2) : '—'} points.
        Rounded total: {blend.rounded_before_cap}.
        {number(blend.weak_fit_cap) && ` Weak-fit cap: ${blend.weak_fit_cap}.`} Final score: {blend.final_score}.
      </p>}

      <h3>Resume completeness components</h3>
      <ul className="explanation-components">
        {list(explanation.quality_components).map((item) => <li key={item.component}>
          <strong>{item.component}: {item.points} / {item.maximum} points</strong>
          <p>{item.rule}</p>
        </li>)}
      </ul>
      {explanation.job_rule && <><h3>Job-fit calculation</h3><p>{explanation.job_rule}</p></>}
      {list(explanation.job_components).map((item) => number(item.score) && <div className="breakdown-row" key={item.component}>
        <span className="breakdown-label">{item.component}</span>
        <progress max="100" value={item.score} aria-label={`${item.component} job-fit score`} />
        <span>{item.score} / 100{number(item.weight) ? ` × ${Math.round(item.weight * 100)}%` : ''}
          {number(item.weighted_points) ? ` = ${item.weighted_points.toFixed(2)} points` : ''}</span>
      </div>)}

      <div className="requirements-grid">
        <div><h3>Matched skills</h3>
          {matched.length ? <ul className="skill-list">{matched.map((item) => <li key={item.skill}>{item.skill}</li>)}</ul> : <p>No explicit skill matches evidenced.</p>}
        </div>
        <div><h3>Requirements not evidenced</h3>
          {missing.length ? <ul className="skill-list skill-list-missing">{missing.map((item) => <li key={item.skill}>{item.skill}</li>)}</ul> : <p>{requirements.length ? 'No additional recognized skill requirements remain unevidenced.' : 'No recognized job skill requirements to compare.'}</p>}
        </div>
      </div>
      <h3>Supporting evidence</h3>
      {requirements.length ? <ul className="evidence-list">{requirements.map((item) => <li key={item.skill}>
        <strong>{item.skill}</strong> — {item.status === 'matched' ? item.basis : 'Not evidenced in resume'}
        <p className="field-label">JD context: {list(item.contexts).join(', ') || 'unspecified'}{typeof item.weight === 'number' ? ` (${item.weight < 1 ? 'half' : 'full'} skills weight)` : ''}</p>
        {list(item.evidence).length ? list(item.evidence).map((record, index) => <figure key={index}>
          <blockquote>{record.excerpt}</blockquote>
          <figcaption>{record.section}{Number.isInteger(record.entry_index) ? ` entry ${record.entry_index + 1}` : ''}</figcaption>
        </figure>) : <p>{item.evidence_note || 'Source quotation unavailable'}</p>}
      </li>)}</ul> : <p>No requirement evidence available for this analysis.</p>}
      {list(explanation.unverified_provider_matches).length > 0 && <p>Provider matches not locally verified: {explanation.unverified_provider_matches.join(', ')}.</p>}

      <h3>Experience and education</h3>
      <p>{explanation.experience?.rule}</p>
      {number(explanation.experience?.years) && <p>Documented tenure: {explanation.experience.years} years. Entries with uncertain or invalid duration: {explanation.experience.uncertain_entries || 0}.</p>}
      <p>{explanation.experience?.note}</p>
      <p>{explanation.education?.rule}</p>
      <p>{explanation.education?.note}</p>
      <h3>Recommended improvements</h3>
      {list(explanation.recommendations).length ? <ul>{explanation.recommendations.map((item, index) => <li key={index}>{item}</li>)}</ul> : <p>No specific improvements identified from the available evidence.</p>}
      <details open={expandLimitations}><summary>Limitations</summary><ul>{list(explanation.limitations).map((item, index) => <li key={index}>{item}</li>)}</ul></details>
    </section>
  )
}
