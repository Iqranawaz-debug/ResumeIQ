// Pure view-model helpers for the results dashboard. No scoring happens here:
// every number shown comes from the backend analysis.

export const RECOMMENDATION_CLASS = {
  'Highly Recommended': 'rec-highly',
  Recommended: 'rec-recommended',
  Consider: 'rec-consider',
  'Not Recommended': 'rec-not',
}

export const REQUIREMENT_STATUS = {
  matched: { label: 'Matched', tone: 'success' },
  partial: { label: 'Partial', tone: 'warning' },
  not_evidenced: { label: 'Not evidenced', tone: 'danger' },
  unclear: { label: "Can't assess", tone: 'neutral' },
}

export const EVIDENCE_BASIS = {
  explicit: 'Resume evidence',
  inference: 'Inference — verify',
  none: 'No evidence found',
}

export const CONTEXT_LABELS = {
  required: 'Required',
  unspecified: 'Other requirements',
  responsibilities: 'Responsibilities',
  preferred: 'Preferred / nice to have',
}

export const RESULT_TABS = [
  { id: 'requirements', label: 'Requirements' },
  { id: 'score', label: 'Score breakdown' },
  { id: 'improve', label: 'Improve' },
  { id: 'interview', label: 'Interview prep' },
  { id: 'document', label: 'Document' },
  { id: 'versions', label: 'Versions' },
]

const list = (value) => (Array.isArray(value) ? value : [])

export function formatDelta(value) {
  if (!Number.isFinite(value) || value === 0) return '0'
  return value > 0 ? `+${value}` : String(value)
}

export function hasPlaceholder(text) {
  return /\[[^[\]]+\]/.test(text || '')
}

// Which score is the main one, and whether a local score should sit beside it.
export function scoreSources(analysis) {
  const hasJobFit = Number.isFinite(analysis?.job_fit_score)
  const ai = analysis?.job_fit_method === 'ai'
  return {
    hasJobFit,
    mainLabel: !hasJobFit ? 'Resume-only score' : ai ? 'AI-assisted score' : 'Local rules score',
    local: ai && Number.isFinite(analysis?.local_overall_score)
      ? { overall: analysis.local_overall_score, jobFit: analysis.local_job_fit_score, label: analysis.local_job_fit_label }
      : null,
    banner: analysis?.ai_status === 'fallback' ? analysis.processing_note : null,
  }
}

// Top matched requirements and the most important gaps, for the summary header.
export function summaryHighlights(analysis, limit = 3) {
  const rows = list(analysis?.explanation?.requirement_lines?.rows)
  const rank = { required: 0, unspecified: 1, responsibilities: 2, preferred: 3 }
  const byContext = (a, b) => (rank[a.context] ?? 4) - (rank[b.context] ?? 4)
  const matches = rows.filter((row) => row.status === 'matched').sort(byContext).slice(0, limit)
  const gaps = rows
    .filter((row) => row.status === 'not_evidenced' || (row.status === 'partial' && row.context !== 'preferred'))
    .sort((a, b) => byContext(a, b) || (a.status === 'not_evidenced' ? -1 : 1) - (b.status === 'not_evidenced' ? -1 : 1))
    .slice(0, limit)
  return { matches, gaps, counts: analysis?.explanation?.requirement_lines?.counts || null }
}

export function groupRequirements(rows) {
  const groups = {}
  for (const row of list(rows)) (groups[row.context] ||= []).push(row)
  return Object.keys(CONTEXT_LABELS).filter((key) => groups[key]).map((key) => ({ context: key, label: CONTEXT_LABELS[key], rows: groups[key] }))
}

export function retentionText(seconds) {
  if (!Number.isFinite(seconds)) return 'a limited time'
  const hours = seconds / 3600
  return hours >= 1 ? `${Number.isInteger(hours) ? hours : hours.toFixed(1)} hour${hours === 1 ? '' : 's'}` : `${Math.round(seconds / 60)} minutes`
}

export function weakFitCapApplies(analysis) {
  return Number.isFinite(analysis?.explanation?.blend?.weak_fit_cap)
}
