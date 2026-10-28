import React from 'react'
import { RECOMMENDATION_CLASS, REQUIREMENT_STATUS, scoreSources, summaryHighlights } from './resultsModel.js'

function Highlight({ title, rows, empty }) {
  return (
    <div className="summary-highlight">
      <h3>{title}</h3>
      {rows.length ? (
        <ul>
          {rows.map((row, index) => (
            <li key={index}>
              <span className={`status-dot tone-${(REQUIREMENT_STATUS[row.status] || REQUIREMENT_STATUS.unclear).tone}`} aria-hidden="true" />
              <span><span className="visually-hidden">{(REQUIREMENT_STATUS[row.status] || REQUIREMENT_STATUS.unclear).label}: </span>{row.text}</span>
            </li>
          ))}
        </ul>
      ) : <p className="empty-state">{empty}</p>}
    </div>
  )
}

export default function ScoreSummary({ analysis }) {
  const sources = scoreSources(analysis)
  const highlights = summaryHighlights(analysis)
  return (
    <section className="results-summary" aria-label="Result summary">
      {sources.banner && <p className="banner banner-warning" role="status">{sources.banner}</p>}
      <div className="summary-top">
        <div className="summary-score">
          <div className="score-ring" style={{ '--score': analysis.overall_score }} role="img" aria-label={`Score ${analysis.overall_score} out of 100`}>
            <div className="score-ring-inner">
              <span className="score-number">{analysis.overall_score}</span>
              <span className="score-max">/ 100</span>
            </div>
          </div>
          <div>
            <p className="field-label">{sources.mainLabel}</p>
            <p className={`recommendation-badge ${RECOMMENDATION_CLASS[analysis.recommendation] || ''}`}>{analysis.recommendation}</p>
            <p className="experience-level">{analysis.experience_level} · {analysis.total_experience_years} years of dated employment</p>
          </div>
        </div>
        <dl className="summary-stats">
          <div><dt>Resume quality</dt><dd>{analysis.resume_quality_score}<small>/100</small></dd></div>
          {sources.hasJobFit && <div><dt>Job fit{analysis.job_fit_method === 'ai' ? ' (AI)' : ''}</dt><dd>{analysis.job_fit_score}<small>/100</small></dd><span>{analysis.job_fit_label}</span></div>}
          {sources.local && (
            <div className="summary-local">
              <dt>Local rules score</dt>
              <dd>{sources.local.overall}<small>/100</small></dd>
              <span>Job fit {sources.local.jobFit} · {sources.local.label}</span>
            </div>
          )}
          <div><dt>Skills found</dt><dd>{analysis.skills_count}</dd></div>
        </dl>
      </div>
      {sources.local && <p className="wizard-note">The AI score is the main score. The local rules score uses the transparent formula in Score breakdown; the two are not equally calibrated.</p>}
      <p className="wizard-note">Indicative document review, not an official ATS score or hiring probability. Verify all evidence before making decisions.</p>
      {highlights.counts && (
        <div className="summary-highlights">
          <Highlight title="Strongest matches" rows={highlights.matches} empty="No requirement was fully matched." />
          <Highlight title="Most important gaps" rows={highlights.gaps} empty="No unmatched required items." />
        </div>
      )}
    </section>
  )
}
