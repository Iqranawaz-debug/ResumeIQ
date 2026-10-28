import React from 'react'

const list = (value) => (Array.isArray(value) ? value : [])

export default function DocumentChecks({ checks, compact = false }) {
  if (!checks) return <p className="empty-state">Readability checks are unavailable for this upload.</p>
  const findings = list(checks.findings)
  const warnings = findings.filter((item) => item.severity === 'warning').length
  const shown = compact ? findings.filter((item) => item.severity === 'warning') : findings
  return (
    <section className="document-checks" aria-label="Document readability">
      <h3>Document readability</h3>
      <p className="document-meta">
        {[checks.format?.toUpperCase(), checks.pages ? `${checks.pages} page${checks.pages === 1 ? '' : 's'}` : null,
          Number.isFinite(checks.characters) ? `${checks.characters.toLocaleString()} characters read` : null].filter(Boolean).join(' · ')}
        {' · '}{warnings ? `${warnings} possible issue${warnings === 1 ? '' : 's'}` : 'No warnings'}
      </p>
      {shown.length > 0 && (
        <ul className="finding-list">
          {shown.map((item) => (
            <li key={item.id} className={`finding finding-${item.severity}`}>
              <span className={`status-chip tone-${item.severity === 'warning' ? 'warning' : 'neutral'}`}>{item.severity === 'warning' ? 'Warning' : 'Note'}</span>
              <div>
                <p className="finding-title">{item.title}</p>
                <p>{item.detail}</p>
                <p className="finding-fix"><strong>Fix:</strong> {item.fix}</p>
              </div>
            </li>
          ))}
        </ul>
      )}
      {compact && findings.length > shown.length && <p className="wizard-note">{findings.length - shown.length} additional note(s) appear in the Document tab after analysis.</p>}
      {!compact && list(checks.passed).length > 0 && (
        <ul className="passed-list" aria-label="Checks passed">
          {checks.passed.map((item) => <li key={item}>{item}</li>)}
        </ul>
      )}
      <p className="wizard-note">{checks.note}</p>
    </section>
  )
}
