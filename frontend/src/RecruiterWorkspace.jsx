import React, { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { API_BASE_URL, addCandidateNote, addCandidateTag, apiRequest, deleteCandidateNote, editCandidateNote, exportComparisonCsv, removeCandidateTag } from './api'
import { ANNOTATION_LIMITS, EMPTY_FILTERS, REVIEW_STATUSES, allTags, filterCandidates, updateCandidate, validateBatch, withNote, withTags, withoutNote } from './recruiterState'
import RecruiterComparison from './RecruiterComparison'
import CandidateAnnotations from './CandidateAnnotations'
import ComparisonReport from './ComparisonReport'
import PipelineBoard from './PipelineBoard'

const STEPS = [
  { title: 'Create a job workspace', text: 'Add the job title and the job description every candidate will be compared against.' },
  { title: 'Upload resumes', text: 'Drop in up to 5 PDF or DOCX resumes at a time. Extraction runs locally; duplicates are detected.' },
  { title: 'Analyze, review, compare', text: 'Score everyone against the same job, set review statuses and compare up to 4 side by side.' },
]
const ANALYSIS_TONE = { completed: 'success', outdated: 'warning', pending: 'neutral' }
const REVIEW_TONE = { Shortlisted: 'success', 'Under Review': 'warning', 'Not Selected': 'danger', 'Not Reviewed': 'neutral' }
const OUTCOME_TONE = { success: 'success', duplicate: 'neutral' }

function saveFile(filename, content, type) {
  // A UTF-8 byte-order mark makes spreadsheet apps read accented names correctly.
  const url = URL.createObjectURL(new Blob(['\ufeff', content], { type }))
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

function formatBytes(bytes) {
  return bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`
}

export default function RecruiterWorkspace({ token }) {
  const [groups, setGroups] = useState([])
  const [group, setGroup] = useState(null)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [limits, setLimits] = useState({ files: 5, batch_bytes: 10485760, compare: 4 })
  const [files, setFiles] = useState([])
  const [batch, setBatch] = useState(null)
  const [selected, setSelected] = useState([])
  const [rows, setRows] = useState([])
  const [filters, setFilters] = useState(EMPTY_FILTERS)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [progress, setProgress] = useState(null)
  const [loaded, setLoaded] = useState(false)
  const [moreFilters, setMoreFilters] = useState(false)
  const [includeNotes, setIncludeNotes] = useState(false)
  const [exporting, setExporting] = useState(null)
  const [exportError, setExportError] = useState('')
  const [printData, setPrintData] = useState(null)
  const [view, setView] = useState('list')
  const alive = useRef(true)
  const controllers = useRef(new Set())
  const stop = useRef(false)
  const operation = useRef(false)

  async function request(path = '', options = {}) {
    const controller = new AbortController()
    controllers.current.add(controller)
    try {
      return await apiRequest(`${API_BASE_URL}/api/workspaces${path}`, { ...options, signal: controller.signal,
        headers: { Authorization: `Bearer ${token}`, ...options.headers } })
    } finally { controllers.current.delete(controller) }
  }
  // Registers an abortable call so leaving the page cancels it, like request() above.
  async function tracked(call) {
    const controller = new AbortController()
    controllers.current.add(controller)
    try { return await call({ signal: controller.signal }) } finally { controllers.current.delete(controller) }
  }
  const json = (method, body) => ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  async function list() { const data = await request(); if (alive.current) { setGroups(data.workspaces); setLimits(data.limits) } }
  useEffect(() => {
    alive.current = true
    const pending = controllers.current
    const controller = new AbortController()
    pending.add(controller)
    apiRequest(`${API_BASE_URL}/api/workspaces`, { signal: controller.signal, headers: { Authorization: `Bearer ${token}` } })
      .then((data) => { if (!controller.signal.aborted) { setGroups(data.workspaces); setLimits(data.limits) } })
      .catch((err) => { if (!controller.signal.aborted) setError(err.message) })
      .finally(() => { pending.delete(controller); if (!controller.signal.aborted) setLoaded(true) })
    return () => { alive.current = false; stop.current = true; for (const controller of pending) controller.abort() }
  }, [token])

  // The comparison report prints alone: the app shell is hidden while body[data-print=comparison] is set.
  useEffect(() => {
    if (!printData) return undefined
    document.body.dataset.print = 'comparison'
    const finish = () => setPrintData(null)
    window.addEventListener('afterprint', finish, { once: true })
    const timer = setTimeout(() => window.print(), 50)
    return () => { clearTimeout(timer); window.removeEventListener('afterprint', finish); delete document.body.dataset.print }
  }, [printData])

  async function exportComparison(kind) {
    if (operation.current) return
    operation.current = true; setExporting(kind); setExportError(''); setMessage('')
    const candidateIds = rows.map((row) => row.id)
    try {
      if (kind === 'csv') {
        const result = await tracked((o) => exportComparisonCsv(token, group.id, { candidateIds, version: group.version, includeNotes }, o))
        if (!alive.current) return
        saveFile(result.filename, result.content, 'text/csv;charset=utf-8')
        setMessage(`Exported ${candidateIds.length} candidate${candidateIds.length === 1 ? '' : 's'} to ${result.filename} ${result.include_notes ? 'including' : 'without'} private notes.`)
      } else {
        const result = await request(`/${group.id}/comparison`, json('POST', { candidate_ids: candidateIds, version: group.version }))
        if (!alive.current) return
        setPrintData({ rows: result.candidates, notice: result.notice, includeNotes, title: group.title, version: group.version, generatedAt: new Date().toISOString() })
        setMessage('Print dialog opened. Choose "Save as PDF" as the destination.')
      }
    } catch (err) {
      if (alive.current && err.name !== 'AbortError') setExportError(err.message)
    } finally {
      operation.current = false
      if (alive.current) setExporting(null)
    }
  }

  async function run(action) {
    if (operation.current) return
    operation.current = true; setBusy(true); setError(''); setMessage(''); setProgress(null)
    try { await action() } catch (err) { if (alive.current && err.name !== 'AbortError') setError(err.message) }
    finally { operation.current = false; if (alive.current) setBusy(false) }
  }
  async function open(id) {
    const data = await request(`/${id}`)
    if (!alive.current) return
    setGroup(data); setTitle(data.title); setDescription(data.description); setFiles([])
    setRows([]); setSelected([]); setBatch(data.batches[0] || null); setFilters(EMPTY_FILTERS); setProgress(null)
  }
  async function refresh(id) {
    const data = await request(`/${id}`)
    if (alive.current) setGroup(data)
    await list()
  }
  function reset() {
    setGroup(null); setTitle(''); setDescription(''); setFiles([]); setBatch(null); setRows([]); setSelected([]); setProgress(null); setError('')
  }
  async function save(event) {
    event.preventDefault()
    await run(async () => {
      const result = await request(group ? `/${group.id}` : '', json(group ? 'PATCH' : 'POST', { title, description, ...(group ? { version: group.version } : {}) }))
      await open(result.id); await list(); setMessage('Workspace saved. Only results from the current job version can be compared.')
    })
  }
  async function upload() {
    const validation = validateBatch(files, limits)
    if (validation) { setError(validation); return }
    await run(async () => {
      setMessage(`Processing ${files.length} files. Per-file outcomes will appear when the request completes.`)
      const body = new FormData(); files.forEach((file) => body.append('files', file))
      const result = await request(`/${group.id}/uploads`, { method: 'POST', body })
      if (!alive.current) return
      setBatch(result)
      setFiles(files.filter((_, index) => result.outcomes.some((item) => item.index === index && item.state === 'failed')))
      await refresh(group.id)
      setMessage(`${result.completed} completed (including duplicates), ${result.failed} failed. Failed files remain selected for retry or replacement.`)
    })
  }
  async function analyze(useAI) {
    await run(async () => {
      stop.current = false; setRows([])
      const ids = group.candidates.map((row) => row.id)
      let completed = 0, failed = 0
      for (const id of ids) {
        if (stop.current || !alive.current) break
        setProgress({ total: ids.length, completed, failed, pending: ids.length - completed - failed })
        try { await request(`/${group.id}/candidates/${id}/analyze`, json('POST', { version: group.version, use_ai: useAI })); completed++ }
        catch (err) { if (err.name === 'AbortError') break; failed++; if (alive.current) setError(err.message) }
        if (alive.current) setProgress({ total: ids.length, completed, failed, pending: ids.length - completed - failed })
      }
      if (alive.current) { await refresh(group.id); setMessage('Analysis pass finished. Successful candidates remain available; repeat to retry failures. Cached results are reused.') }
    })
  }
  async function review(row, status) {
    await run(async () => {
      const updated = await request(`/${group.id}/candidates/${row.id}/review`, json('PATCH', { status, revision: row.revision }))
      if (!alive.current) return
      setGroup((value) => ({ ...value, candidates: value.candidates.map((candidate) => candidate.id === row.id ? { ...candidate, ...updated } : candidate) }))
      setRows((values) => values.map((candidate) => candidate.id === row.id ? { ...candidate, ...updated } : candidate))
      setMessage('Manual review status saved. Evaluation scores are unchanged.')
    })
  }
  function applyToCandidate(id, update) {
    setGroup((value) => value && { ...value, candidates: updateCandidate(value.candidates, id, update) })
    setRows((values) => updateCandidate(values, id, update))
  }
  async function annotate(action, done) {
    let ok = false
    await run(async () => { await action(); if (alive.current) { setMessage(done); ok = true } })
    return ok
  }
  const annotationHandlers = {
    onAddNote: (row, text) => annotate(async () => { const note = await tracked((o) => addCandidateNote(token, group.id, row.id, text, o)); applyToCandidate(row.id, (r) => withNote(r, note)) }, 'Note saved. Notes are private to your account and never sent to AI.'),
    onEditNote: (row, noteId, text) => annotate(async () => { const note = await tracked((o) => editCandidateNote(token, group.id, row.id, noteId, text, o)); applyToCandidate(row.id, (r) => withNote(r, note)) }, 'Note updated.'),
    onDeleteNote: (row, noteId) => annotate(async () => { await tracked((o) => deleteCandidateNote(token, group.id, row.id, noteId, o)); applyToCandidate(row.id, (r) => withoutNote(r, noteId)) }, 'Note deleted.'),
    onAddTag: (row, tag) => annotate(async () => { const result = await tracked((o) => addCandidateTag(token, group.id, row.id, tag, o)); applyToCandidate(row.id, (r) => withTags(r, result.tags)) }, 'Tag saved.'),
    onRemoveTag: (row, tag) => annotate(async () => { const result = await tracked((o) => removeCandidateTag(token, group.id, row.id, tag, o)); applyToCandidate(row.id, (r) => withTags(r, result.tags)) }, 'Tag removed.'),
  }
  const annotationLimits = { ...ANNOTATION_LIMITS, ...Object.fromEntries(Object.keys(ANNOTATION_LIMITS).filter((key) => Number.isFinite(limits[key])).map((key) => [key, limits[key]])) }
  const visible = filterCandidates(group?.candidates, filters)
  function filter(key, value) { setFilters((state) => ({ ...state, [key]: value })) }
  const candidates = group?.candidates || []
  const analyzed = candidates.filter((row) => row.analysis_state === 'completed').length
  const shortlisted = candidates.filter((row) => row.status === 'Shortlisted').length
  const filtersActive = Object.values(filters).some(Boolean)
  const advancedActive = Boolean(filters.source || filters.processing || filters.matched || filters.missing)
  const tagOptions = allTags(group?.candidates)
  const progressPercent = progress ? Math.round(((progress.completed + progress.failed) / Math.max(progress.total, 1)) * 100) : 0

  const jobForm = (
      <form className="rw-card rw-job" onSubmit={save}>
        <div className="rw-card-head">
          <h2>{group ? 'Job details' : 'Create a job workspace'}</h2>
          {group && <span className="status-chip tone-neutral">Job version {group.version}</span>}
        </div>
        <label className="rw-field">Job title<input required maxLength={120} value={title} disabled={busy} placeholder="e.g. Senior Backend Engineer" onChange={(e) => setTitle(e.target.value)} /></label>
        <label className="rw-field">Shared job description<textarea required maxLength={100000} rows={6} value={description} disabled={busy} placeholder="Paste the full job description, including requirements and responsibilities." onChange={(e) => setDescription(e.target.value)} /></label>
        <div className="rw-actions">
          <button className="rw-button rw-primary" disabled={busy}>{group ? 'Save job changes' : 'Create workspace'}</button>
          {group && <span className="rw-hint">Changing the description starts a new job version; earlier analyses must be re-run before comparing.</span>}
        </div>
      </form>
  )
  const uploadSection = (
      <section className="rw-card" aria-labelledby="rw-upload-heading">
        <div className="rw-card-head">
          <h2 id="rw-upload-heading">Bulk upload</h2>
          <span className="rw-hint">Up to {limits.files} PDF/DOCX files · 10 MB per batch · processed locally, no AI</span>
        </div>
        <label className={`rw-dropzone ${busy ? 'disabled' : ''}`}>
          <input className="visually-hidden" aria-label="Select resumes" type="file" multiple accept=".pdf,.docx" disabled={busy} onChange={(e) => { setFiles(Array.from(e.target.files || [])); e.target.value = '' }} />
          <span className="dropzone-icon" aria-hidden="true">⬆</span>
          <span className="dropzone-text">Choose resumes to add to <strong>{group?.title}</strong></span>
          <span className="dropzone-hint">Duplicates of resumes already in this workspace are skipped automatically.</span>
        </label>
        {files.length > 0 && <ul className="rw-file-list">{files.map((file, index) => <li key={`${file.name}-${index}`}>
          <span className="rw-file-name">{file.name}</span><span className="rw-hint">{formatBytes(file.size)}</span>
          <button type="button" className="rw-icon-button" aria-label={`Remove file ${index + 1}`} title="Remove" disabled={busy} onClick={() => setFiles((values) => values.filter((_, i) => i !== index))}>Remove</button>
        </li>)}</ul>}
        <div className="rw-actions">
          <button type="button" className="rw-button rw-primary" disabled={busy || !files.length} onClick={upload}>Process selected files</button>
        </div>
        {batch && <div className="rw-batch" aria-label="Batch outcomes">
          <p className="rw-hint">Last batch: {batch.completed} completed · {batch.failed} failed · {batch.pending} pending · {batch.total} total</p>
          <ul>{batch.outcomes.map((item) => <li key={item.index}>
            <span className={`status-chip tone-${item.state === 'failed' ? 'danger' : OUTCOME_TONE[item.kind] || 'neutral'}`}>{item.state === 'failed' ? 'Failed' : item.kind === 'duplicate' ? 'Duplicate' : 'Added'}</span>
            <span className="rw-file-name">{item.filename}</span><span className="rw-hint">{item.message}</span>
          </li>)}</ul>
        </div>}
      </section>
  )
  const candidatesSection = (
      <section className="rw-card" aria-labelledby="rw-candidates-heading">
        <div className="rw-card-head">
          <h2 id="rw-candidates-heading">Candidates</h2>
          <div className="rw-actions rw-inline">
            <button type="button" className="rw-button rw-primary" disabled={busy || !candidates.length} onClick={() => analyze(false)}>Analyze group locally</button>
            <button type="button" className="rw-button" disabled={busy || !candidates.length} onClick={() => analyze(true)}>Analyze group with AI assistance</button>
            {busy && progress && <button type="button" className="rw-button rw-small" onClick={() => { stop.current = true; setMessage('Stopping after the current candidate completes.') }}>Stop after current candidate</button>}
          </div>
        </div>
        <p className="rw-hint">AI assistance sends allowlisted candidate fields and the shared job description to the configured provider, one candidate at a time. Contacts, organizations, projects and evidence records are excluded; redaction is best effort. Provider failures fall back to local rules.</p>
        {progress && <div className="rw-progress" role="status">
          <div className="rw-progress-track"><div className="rw-progress-fill" style={{ width: `${progressPercent}%` }} /></div>
          <span>{progress.completed} analyzed · {progress.failed} failed · {progress.pending} pending · {progress.total} total</span>
        </div>}

        {candidates.length > 0 && <div className="recruiter-filters">
          <label className="rw-field rw-search">Search candidates<input value={filters.search} placeholder="Name, skill, tag, note or status" onChange={(e) => filter('search', e.target.value)} /></label>
          <label className="rw-field">Tag filter<select value={filters.tag} disabled={!tagOptions.length} onChange={(e) => filter('tag', e.target.value)}><option value="">{tagOptions.length ? 'All tags' : 'No tags yet'}</option>{tagOptions.map((tag) => <option key={tag} value={tag}>{tag}</option>)}</select></label>
          <label className="rw-field">Review filter<select value={filters.review} onChange={(e) => filter('review', e.target.value)}><option value="">All reviews</option>{REVIEW_STATUSES.map((status) => <option key={status}>{status}</option>)}</select></label>
          <label className="rw-field">Analysis filter<select value={filters.analysis} onChange={(e) => filter('analysis', e.target.value)}><option value="">All analyses</option>{['pending', 'completed', 'outdated'].map((value) => <option key={value}>{value}</option>)}</select></label>
          {moreFilters && <>
            <label className="rw-field">Score source filter<select value={filters.source} onChange={(e) => filter('source', e.target.value)}><option value="">All sources</option><option value="rule-based">Local</option><option value="ai">AI</option></select></label>
            <label className="rw-field">Processing filter<select value={filters.processing} onChange={(e) => filter('processing', e.target.value)}><option value="">All processing states</option><option>processing</option><option>completed</option></select></label>
            <label className="rw-field">Matched skill filter<input value={filters.matched} placeholder="e.g. Python" onChange={(e) => filter('matched', e.target.value)} /></label>
            <label className="rw-field">Not-evidenced skill filter<input value={filters.missing} placeholder="e.g. Kubernetes" onChange={(e) => filter('missing', e.target.value)} /></label>
          </>}
          <div className="rw-filter-actions">
            <button type="button" className="link-button" aria-expanded={moreFilters} onClick={() => setMoreFilters((value) => !value)}>
              {moreFilters ? 'Fewer filters' : `More filters${advancedActive ? ' (active)' : ''}`}
            </button>
            <button type="button" className="rw-button rw-small" disabled={!filtersActive} onClick={() => setFilters(EMPTY_FILTERS)}>Clear filters</button>
          </div>
        </div>}

        {!candidates.length && <p className="empty-state rw-empty">No candidates yet. Upload resumes above to start screening.</p>}
        {candidates.length > 0 && <div className="rw-view-toggle">
          <span className="rw-segmented" role="group" aria-label="Candidate view">
            <button type="button" className={view === 'list' ? 'active' : ''} aria-pressed={view === 'list'} onClick={() => setView('list')}>List</button>
            <button type="button" className={view === 'board' ? 'active' : ''} aria-pressed={view === 'board'} onClick={() => setView('board')}>Board</button>
          </span>
          <span className="rw-hint">{view === 'board' ? 'Columns are review statuses; cards stay in upload order.' : 'Candidates stay in upload order.'}</span>
        </div>}
        {candidates.length > 0 && !visible.length && <p className="empty-state rw-empty">No candidates match these filters.</p>}
        {view === 'board' && visible.length > 0 && <PipelineBoard rows={visible} busy={busy} onMove={review} />}
        {view === 'list' && visible.length > 0 && <div className="recruiter-table" tabIndex={0} role="region" aria-label="Candidate list, scroll horizontally if needed">
          <table><thead><tr><th scope="col"><span className="visually-hidden">Select</span></th><th scope="col">Candidate</th><th scope="col">Analysis</th><th scope="col">Review status</th><th scope="col"><span className="visually-hidden">Actions</span></th></tr></thead>
            <tbody>{visible.map((row) => <tr key={row.id} className={selected.includes(row.id) ? 'selected' : ''}>
              <td><input aria-label={`Compare ${row.name || row.filename}`} type="checkbox" disabled={busy || (!selected.includes(row.id) && selected.length >= limits.compare)} checked={selected.includes(row.id)} onChange={(e) => { setSelected((values) => e.target.checked ? [...values, row.id] : values.filter((id) => id !== row.id)); setRows([]) }} /></td>
              <td>
                <p className="rw-candidate-name">{row.name || 'Name not found'}</p>
                <p className="rw-hint">{row.filename}</p>
                {(row.skills || []).length > 0 && <ul className="rw-skill-chips">{row.skills.slice(0, 6).map((skill) => <li key={skill}>{skill}</li>)}{row.skills.length > 6 && <li>+{row.skills.length - 6}</li>}</ul>}
                {(row.tags || []).length > 0 && <ul className="rw-tag-chips rw-tag-chips-static" aria-label={`Tags for ${row.name || row.filename}`}>{row.tags.map((tag) => <li key={tag}>{tag}</li>)}</ul>}
                {(row.notes || []).length > 0 && <p className="rw-hint">{row.notes.length} private note{row.notes.length === 1 ? '' : 's'}</p>}
              </td>
              <td>
                {row.overall_score != null && <p className="rw-score">{row.overall_score}<small>/100</small></p>}
                <span className={`status-chip tone-${ANALYSIS_TONE[row.analysis_state] || 'neutral'}`}>{row.analysis_state}</span>
                <p className="rw-hint">{row.score_source === 'ai' ? 'AI score' : row.score_source ? 'Local score' : 'Not scored yet'}</p>
                {row.analysis_error && <p className="rw-hint rw-error">{row.analysis_error}</p>}
              </td>
              <td><label className="rw-field rw-review">
                <span className="visually-hidden">Review {row.name || row.filename}</span>
                <span className={`status-chip tone-${REVIEW_TONE[row.status] || 'neutral'}`} aria-hidden="true">{row.status}</span>
                <select disabled={busy} value={row.status} onChange={(e) => review(row, e.target.value)}>{REVIEW_STATUSES.map((status) => <option key={status}>{status}</option>)}</select>
              </label></td>
              <td className="rw-row-actions">
                <button type="button" className="rw-button rw-small" disabled={busy} onClick={() => run(async () => { const detail = await request(`/${group.id}/candidates/${row.id}`); if (alive.current) setRows([detail]) })}>Review candidate</button>
                <button type="button" className="rw-button rw-small rw-quiet" disabled={busy} onClick={() => run(async () => { await request(`/${group.id}/candidates/${row.id}`, { method: 'DELETE' }); setRows([]); setSelected((values) => values.filter((id) => id !== row.id)); await refresh(group.id) })}>Remove candidate</button>
              </td>
            </tr>)}</tbody></table>
        </div>}

        {candidates.length > 0 && <div className="rw-compare-bar">
          <p className="rw-hint">{view === 'board' && 'Switch to List to choose candidates to compare. '}Select up to {limits.compare} analyzed candidates from this job version. AI and local scores are not equally calibrated. No automatic ranking is applied.</p>
          <button type="button" className="rw-button rw-primary" disabled={busy || !selected.length} onClick={() => run(async () => { const result = await request(`/${group.id}/comparison`, json('POST', { candidate_ids: selected, version: group.version })); if (alive.current) { setRows(result.candidates); setMessage(result.notice) } })}>Compare selected candidates</button>
        </div>}
      </section>
  )

  return <section className="recruiter-workspace" aria-label="Recruitment workspaces">
    <header className="rw-header">
      <p className="eyebrow">/ RECRUITMENT</p>
      <h1>Recruitment workspaces</h1>
      <p className="subtitle">Screen several candidates against one job description. Human review only: no automatic ranking, shortlisting or rejection.</p>
    </header>

    <div className="rw-card rw-switcher">
      <label className="rw-field">Open workspace
        <select disabled={busy || !groups.length} value={group?.id || ''} onChange={(event) => { if (event.target.value) run(() => open(event.target.value)); else reset() }}>
          <option value="">{groups.length ? 'Choose a workspace' : 'No workspaces yet'}</option>
          {groups.map((item) => <option key={item.id} value={item.id}>{item.title} ({item.candidate_count})</option>)}
        </select>
      </label>
      <button type="button" className="rw-button" disabled={busy} onClick={reset}>New workspace</button>
      <p className="rw-switcher-note">{groups.length} of {limits.groups ?? 5} workspaces · private to your account · kept as described under Privacy &amp; data</p>
    </div>

    {loaded && !groups.length && !group && (
      <ol className="rw-steps" aria-label="How recruitment workspaces work">
        {STEPS.map((step, index) => <li key={step.title} className="rw-card">
          <span className="rw-step-number" aria-hidden="true">{index + 1}</span>
          <h3>{step.title}</h3>
          <p>{step.text}</p>
        </li>)}
      </ol>
    )}

    {!group && jobForm}

    {error && <div role="alert" className="banner banner-warning rw-banner"><span>{error}</span> <button type="button" className="rw-button rw-small" disabled={busy} onClick={() => run(() => group ? open(group.id) : list())}>Refresh workspace</button></div>}
    {message && <p role="status" className="banner banner-info rw-banner">{message}</p>}

    {group && <>
      <dl className="rw-stats">
        <div className="rw-card"><dt>Candidates</dt><dd>{candidates.length}</dd></div>
        <div className="rw-card"><dt>Analyzed</dt><dd>{analyzed}<small>/{candidates.length}</small></dd></div>
        <div className="rw-card"><dt>Shortlisted</dt><dd>{shortlisted}</dd></div>
        <div className="rw-card"><dt>Selected to compare</dt><dd>{selected.length}<small>/{limits.compare}</small></dd></div>
      </dl>

      {candidates.length ? <>{candidatesSection}{uploadSection}</> : <>{uploadSection}{candidatesSection}</>}

      {rows.length > 0 && <div className="rw-card rw-export-bar" role="group" aria-label="Export comparison">
        <div className="rw-export-copy">
          <h3>Export {rows.length === 1 ? 'this candidate' : `these ${rows.length} candidates`}</h3>
          <p className="rw-hint">Exports keep the order shown below. Decision support only; human review required.</p>
        </div>
        <label className="rw-check"><input type="checkbox" checked={includeNotes} disabled={Boolean(exporting)} onChange={(e) => setIncludeNotes(e.target.checked)} /> Include private notes</label>
        <div className="rw-actions rw-inline">
          <button type="button" className="rw-button" disabled={busy || Boolean(exporting)} aria-busy={exporting === 'csv'} onClick={() => exportComparison('csv')}>{exporting === 'csv' ? 'Exporting CSV…' : 'Export CSV'}</button>
          <button type="button" className="rw-button" disabled={busy || Boolean(exporting)} aria-busy={exporting === 'pdf'} onClick={() => exportComparison('pdf')}>{exporting === 'pdf' ? 'Preparing PDF…' : 'Export PDF'}</button>
        </div>
        {exportError && <p className="status error rw-export-error" role="alert">{exportError}</p>}
      </div>}
      {printData && createPortal(<ComparisonReport {...printData} />, document.body)}
      {rows.length > 0 && <RecruiterComparison rows={rows} busy={busy} onReview={review}
        renderAnnotations={(row) => <CandidateAnnotations key={row.id} row={row} busy={busy} limits={annotationLimits} {...annotationHandlers} />} />}

      {jobForm}

      <div className="rw-danger">
        <div><h3>Remove this workspace</h3><p className="rw-hint">Deletes the job, its candidates, analyses and review history. This cannot be undone.</p></div>
        <button type="button" className="rw-button rw-danger-button" disabled={busy} onClick={() => run(async () => { await request(`/${group.id}`, { method: 'DELETE' }); reset(); await list() })}>Remove workspace and its candidates</button>
      </div>
    </>}
  </section>
}
