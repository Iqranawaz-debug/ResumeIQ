export function initializeDraft(data, previous = {}) {
  return {
    suggestions: Object.fromEntries((data?.suggestions || []).map((item) => [item.id,
      previous.suggestions?.[item.id] || { text: item.suggested_text || '', status: 'pending', edited: false }])),
    checklist: Object.fromEntries((data?.checklist || []).map((item) => [item.id, previous.checklist?.[item.id] || 'pending'])),
  }
}

export function updateDraft(data, draft, action) {
  if (!data || !draft || !action) return draft
  if (action.type === 'checklist') {
    if (!data.checklist?.some((item) => item.id === action.id) || !['pending', 'complete', 'not_applicable'].includes(action.status)) return draft
    return { ...draft, checklist: { ...draft.checklist, [action.id]: action.status } }
  }
  const item = data.suggestions?.find((entry) => entry.id === action.id)
  const current = draft.suggestions?.[action.id]
  if (!item || !current) return draft
  let next
  if (action.type === 'edit' && typeof action.text === 'string' && action.text.length <= 2000) next = { text: action.text, status: 'pending', edited: true }
  if (action.type === 'accept' && current.text.trim()) next = { ...current, status: 'accepted' }
  if (action.type === 'reject') next = { ...current, status: 'rejected' }
  if (action.type === 'restore') next = { text: item.original_text, status: 'restored', edited: false }
  return next ? { ...draft, suggestions: { ...draft.suggestions, [action.id]: next } } : draft
}

export function checklistCounts(draft) {
  const values = Object.values(draft?.checklist || {})
  return { total: values.length, completed: values.filter((v) => v === 'complete').length,
    remaining: values.filter((v) => v === 'pending').length, notApplicable: values.filter((v) => v === 'not_applicable').length }
}

export function improvementReport(data, draft) {
  if (!data) return 'No improvement report available.'
  const counts = checklistCounts(draft)
  const lines = ['RESUME IMPROVEMENT REPORT', 'Draft advice only. Original resume and score unchanged.', data.note || '',
    `Checklist: ${counts.completed} complete, ${counts.remaining} pending, ${counts.notApplicable} not applicable (${counts.total} total).`]
  for (const item of data.suggestions || []) {
    const state = draft?.suggestions?.[item.id]
    lines.push('', `${item.section} entry ${item.entry_index + 1} — ${state?.status || 'pending'}`,
      `Original: ${item.original_text}`, `Proposed: ${item.suggested_text || 'Clarification needed; no automatic rewrite.'}`,
      `Current draft: ${state?.text || '(none)'}`, `User edited: ${state?.edited ? 'yes — not automatically verified' : 'no'}`,
      `Reason: ${item.reason}`, `Source: ${item.source}`)
  }
  lines.push('', 'JOB REQUIREMENTS')
  for (const row of data.requirements || []) lines.push(`${row.skill}: ${row.status === 'matched' ? 'Listed skill match' : 'Not evidenced in resume'} (${(row.contexts || []).join(', ') || 'unspecified'})`)
  lines.push('', 'CHECKLIST')
  for (const item of data.checklist || []) lines.push(`[${draft?.checklist?.[item.id] || 'pending'}] ${item.category}: ${item.text}`)
  lines.push('', 'LIMITATIONS', ...(data.limitations || []))
  return lines.join('\n')
}
