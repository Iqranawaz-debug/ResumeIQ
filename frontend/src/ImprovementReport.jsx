import React from 'react'
import { improvementReport } from './improvementState.js'

export default function ImprovementReport({ data, draft }) {
  if (!data) return null
  return <section className="print-section improvement-report" aria-label="Improvement report">
    <h2>Resume improvement drafts</h2>
    <pre>{improvementReport(data, draft)}</pre>
  </section>
}
