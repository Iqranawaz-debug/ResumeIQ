export const REVIEW_STATUSES = ['Not Reviewed', 'Under Review', 'Shortlisted', 'Not Selected']
export const EMPTY_FILTERS = { search: '', review: '', analysis: '', source: '', matched: '', missing: '', processing: '', tag: '' }
// Mirrors backend/utils/limits.py defaults; the server's limits (from the workspace list) take precedence.
export const ANNOTATION_LIMITS = { note_chars: 2000, notes: 100, tags: 10, tag_chars: 30 }
const TAG_PATTERN = /^[\p{L}\p{N}][\p{L}\p{N}_ +#.&'-]*$/u
const fold = (value) => String(value ?? '').toLocaleLowerCase()

export function filterCandidates(rows, filters) {
  const contains = (value, term) => fold(value).includes(term.trim().toLocaleLowerCase())
  return (rows || []).filter((row) => {
    const haystack = [row.name, ...(row.skills || []), ...(row.education || []), ...(row.employment_titles || []), row.status,
      ...(row.tags || []), ...(row.notes || []).map((note) => note.text)].join(' ')
    return contains(haystack, filters.search || '') && (!filters.review || row.status === filters.review)
      && (!filters.analysis || row.analysis_state === filters.analysis)
      && (!filters.source || row.score_source === filters.source)
      && (!filters.processing || row.processing_status === filters.processing)
      && (!filters.matched || (row.matched_skills || []).some((skill) => contains(skill, filters.matched)))
      && (!filters.missing || (row.missing_skills || []).some((skill) => contains(skill, filters.missing)))
      && (!filters.tag || (row.tags || []).some((tag) => fold(tag) === fold(filters.tag)))
  })
}
export function validateBatch(files, limits) {
  if (!files.length || files.length > limits.files) return `Select 1–${limits.files} files.`
  if (files.reduce((total, file) => total + file.size, 0) > limits.batch_bytes) return 'Selected files exceed the 10 MB aggregate limit.'
  return ''
}

// Notes and tags: client-side checks mirror the backend so mistakes show before a request is sent.
export function normalizeTag(value) {
  return String(value ?? '').normalize('NFKC').replace(/\s+/g, ' ').trim()
}
export function tagError(value, existing = [], limits = ANNOTATION_LIMITS) {
  const tag = normalizeTag(value)
  if (!tag) return 'Enter a tag.'
  if (tag.length > limits.tag_chars) return `Tags are limited to ${limits.tag_chars} characters.`
  if (!TAG_PATTERN.test(tag)) return "Tags may contain letters, numbers, spaces and + # . & ' - and must start with a letter or number."
  const duplicate = existing.some((item) => fold(item) === fold(tag))
  if (!duplicate && existing.length >= limits.tags) return `A candidate can have up to ${limits.tags} tags.`
  return ''
}
export function noteError(text, limits = ANNOTATION_LIMITS) {
  const value = String(text ?? '').trim()
  if (!value) return 'Write a note first.'
  if (value.length > limits.note_chars) return `Notes are limited to ${limits.note_chars} characters.`
  return ''
}
// Distinct tags across candidates, alphabetical, for the tag filter. Candidate order is untouched.
export function allTags(rows) {
  const seen = new Map()
  for (const row of rows || []) for (const tag of row.tags || []) if (!seen.has(fold(tag))) seen.set(fold(tag), tag)
  return [...seen.values()].sort((a, b) => a.localeCompare(b, undefined, { sensitivity: 'base' }))
}
export function updateCandidate(rows, id, update) {
  return (rows || []).map((row) => (row.id === id ? update(row) : row))
}
export function withNote(row, note) {
  const notes = row.notes || []
  return { ...row, notes: notes.some((item) => item.id === note.id) ? notes.map((item) => (item.id === note.id ? note : item)) : [...notes, note] }
}
export function withoutNote(row, noteId) {
  return { ...row, notes: (row.notes || []).filter((note) => note.id !== noteId) }
}
export function withTags(row, tags) {
  return { ...row, tags: [...tags] }
}
