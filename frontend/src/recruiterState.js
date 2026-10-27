export const REVIEW_STATUSES = ['Not Reviewed', 'Under Review', 'Shortlisted', 'Not Selected']
export const EMPTY_FILTERS = { search: '', review: '', analysis: '', source: '', matched: '', missing: '', processing: '' }
export function filterCandidates(rows, filters) {
  const contains = (value, term) => String(value ?? '').toLocaleLowerCase().includes(term.trim().toLocaleLowerCase())
  return (rows || []).filter((row) => {
    const haystack = [row.name, ...(row.skills || []), ...(row.education || []), ...(row.employment_titles || []), row.status].join(' ')
    return contains(haystack, filters.search || '') && (!filters.review || row.status === filters.review)
      && (!filters.analysis || row.analysis_state === filters.analysis)
      && (!filters.source || row.score_source === filters.source)
      && (!filters.processing || row.processing_status === filters.processing)
      && (!filters.matched || (row.matched_skills || []).some((skill) => contains(skill, filters.matched)))
      && (!filters.missing || (row.missing_skills || []).some((skill) => contains(skill, filters.missing)))
  })
}
export function validateBatch(files, limits) {
  if (!files.length || files.length > limits.files) return `Select 1–${limits.files} files.`
  if (files.reduce((total, file) => total + file.size, 0) > limits.batch_bytes) return 'Selected files exceed the 10 MB aggregate limit.'
  return ''
}
