import React, { useRef, useState } from 'react'
import ScoreSummary from './ScoreSummary'
import RequirementMatrix from './RequirementMatrix'
import ExplainableResults from './ExplainableResults'
import ScoreImpact from './ScoreImpact'
import ImprovementWorkspace from './ImprovementWorkspace'
import DocumentChecks from './DocumentChecks'
import { RESULT_TABS, weakFitCapApplies } from './resultsModel.js'

const list = (value) => (Array.isArray(value) ? value : [])

function ItemList({ title, items, ordered = false, empty = 'None identified' }) {
  const Tag = ordered ? 'ol' : 'ul'
  return (
    <div className="interview-block">
      <h3>{title}</h3>
      {list(items).length ? <Tag>{items.map((item, i) => <li key={i}>{item}</li>)}</Tag> : <p className="empty-state">{empty}</p>}
    </div>
  )
}

function LocalComparison({ comparison }) {
  if (!comparison) return null
  return (
    <section className="local-comparison" aria-label="Local rules comparison">
      <h2>Local rules result</h2>
      <p>Overall {comparison.overall_score} / 100 · Job fit {comparison.job_fit_score} / 100 ({comparison.job_fit_label})</p>
      <p className="wizard-note">{comparison.rule}</p>
      {list(comparison.job_components).map((item) => (
        <div className="breakdown-row" key={item.component}>
          <span className="breakdown-label">{item.component}</span>
          <progress max="100" value={item.score} aria-label={`${item.component} local job-fit score`} />
          <span>{item.score} / 100 × {Math.round(item.weight * 100)}%</span>
        </div>
      ))}
    </section>
  )
}

export default function ResultsDashboard({ analysis, candidate, improvements, improvementDraft, improvementBusy,
  improvementError, canGenerate, onGenerate, onAction, onDownload, initialTab = 'requirements' }) {
  const [tab, setTab] = useState(initialTab)
  const tabRefs = useRef({})
  const explanation = analysis.explanation || {}

  function onKeyDown(event) {
    const index = RESULT_TABS.findIndex((item) => item.id === tab)
    const step = { ArrowRight: 1, ArrowLeft: -1 }[event.key]
    let next = null
    if (step) next = RESULT_TABS[(index + step + RESULT_TABS.length) % RESULT_TABS.length]
    if (event.key === 'Home') next = RESULT_TABS[0]
    if (event.key === 'End') next = RESULT_TABS[RESULT_TABS.length - 1]
    if (next) {
      event.preventDefault()
      setTab(next.id)
      tabRefs.current[next.id]?.focus()
    }
  }

  return (
    <div className="results-dashboard">
      <div className="results-toolbar">
        <p className="field-label" role="status">{analysis.job_fit_method === 'ai' ? `AI-assisted job matching (${analysis.job_fit_model})` : 'Local analysis'}. {analysis.ai_status === 'fallback' ? '' : analysis.processing_note || ''}</p>
        <div className="toolbar-actions">
          <button type="button" className="link-button" onClick={onDownload}>Download summary (.txt)</button>
          <button type="button" className="link-button" onClick={() => window.print()}>Print / save as PDF</button>
        </div>
      </div>

      <ScoreSummary analysis={analysis} />

      <div className="results-tabs" role="tablist" aria-label="Result details" onKeyDown={onKeyDown}>
        {RESULT_TABS.map((item) => (
          <button key={item.id} type="button" role="tab" id={`tab-${item.id}`} aria-controls={`panel-${item.id}`}
            aria-selected={tab === item.id} tabIndex={tab === item.id ? 0 : -1}
            ref={(node) => { tabRefs.current[item.id] = node }}
            className={`results-tab ${tab === item.id ? 'active' : ''}`} onClick={() => setTab(item.id)}>
            {item.label}
          </button>
        ))}
      </div>

      <div className="results-panel" role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`} tabIndex={0}>
        {tab === 'requirements' && <RequirementMatrix lines={explanation.requirement_lines} aiEvidence={analysis.ai_match_evidence} />}
        {tab === 'score' && <>
          <ExplainableResults explanation={analysis.explanation} />
          <LocalComparison comparison={explanation.local_comparison} />
        </>}
        {tab === 'improve' && <>
          <ScoreImpact impacts={analysis.impacts} weakFitCap={weakFitCapApplies(analysis)} />
          <ImprovementWorkspace data={improvements} draft={improvementDraft} busy={improvementBusy} error={improvementError}
            canGenerate={canGenerate} onGenerate={onGenerate} onAction={onAction} />
        </>}
        {tab === 'interview' && <div className="interview-prep">
          {analysis.job_fit_method === 'ai' && <p className="banner banner-info">The narrative below is AI-generated and unverified. Check it against the Requirements tab and the resume itself.</p>}
          <ItemList title="Suggested interview questions" items={analysis.interview_questions} ordered empty="None generated" />
          <ItemList title="Resume observations" items={analysis.strengths} />
          <ItemList title="Review considerations" items={analysis.weaknesses} />
          <ItemList title="Follow-up suggestions" items={analysis.suggestions} />
          {list(analysis.missing_sections).length > 0 && <p className="field-label">Missing from the resume: {analysis.missing_sections.join(', ')}</p>}
        </div>}
        {tab === 'document' && <DocumentChecks checks={candidate?.document_checks} />}
      </div>
    </div>
  )
}
