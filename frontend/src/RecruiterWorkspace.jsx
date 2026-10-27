import React, { useEffect, useRef, useState } from 'react'
import { API_BASE_URL, apiRequest } from './api'
import { EMPTY_FILTERS, REVIEW_STATUSES, filterCandidates, validateBatch } from './recruiterState'
import RecruiterComparison from './RecruiterComparison'

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
      .finally(() => pending.delete(controller))
    return () => { alive.current = false; stop.current = true; for (const controller of pending) controller.abort() }
  }, [token])

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
  const visible = filterCandidates(group?.candidates, filters)
  function filter(key, value) { setFilters((state) => ({ ...state, [key]: value })) }
  return <section className="recruiter-workspace" aria-label="Recruitment workspaces">
    <h1>Recruitment workspaces</h1>
    <p>Private to your account. Stored in server memory only; restart loses workspaces and review decisions. Human review is required. No automatic ranking, shortlisting or rejection.</p>
    <div className="improvement-actions">
      <button disabled={busy} onClick={reset}>New workspace</button>
      <label>Open workspace<select disabled={busy} value={group?.id || ''} onChange={(event) => { if (event.target.value) run(() => open(event.target.value)); else reset() }}>
        <option value="">Choose a workspace</option>{groups.map((item) => <option key={item.id} value={item.id}>{item.title} ({item.candidate_count})</option>)}
      </select></label>
    </div>
    <form onSubmit={save}>
      <label>Job title<input required maxLength={120} value={title} disabled={busy} onChange={(e) => setTitle(e.target.value)} /></label>
      <label>Shared job description<textarea required maxLength={100000} rows={5} value={description} disabled={busy} onChange={(e) => setDescription(e.target.value)} /></label>
      <button className="evaluate-button" disabled={busy}>{group ? 'Save job changes' : 'Create workspace'}</button>
    </form>
    {error && <p role="alert" className="status error">{error} <button disabled={busy} onClick={() => run(() => group ? open(group.id) : list())}>Refresh workspace</button></p>}
    {message && <p role="status">{message}</p>}
    {group && <>
      <p>Job version {group.version} · {group.candidates.length} candidates. Changing the description invalidates prior comparisons.</p>
      <h2>Bulk upload</h2>
      <p>Up to {limits.files} PDF/DOCX files per batch; 10 MB total and the existing individual file limit. Uploads are local; no AI calls.</p>
      <label>Select resumes<input type="file" multiple accept=".pdf,.docx" disabled={busy} onChange={(e) => { setFiles(Array.from(e.target.files || [])); e.target.value = '' }} /></label>
      <ul>{files.map((file, index) => <li key={`${file.name}-${index}`}>{file.name} ({file.size} bytes) <button disabled={busy} onClick={() => setFiles((values) => values.filter((_, i) => i !== index))}>Remove file {index + 1}</button></li>)}</ul>
      <button disabled={busy || !files.length} onClick={upload}>Process selected files</button>
      {batch && <div aria-label="Batch outcomes"><p>{batch.completed} completed · {batch.failed} failed · {batch.pending} pending · {batch.total} total</p>
        <ul>{batch.outcomes.map((item) => <li key={item.index}>{item.filename}: {item.state} ({item.kind}) — {item.message}</li>)}</ul></div>}
      <h2>Candidates</h2>
      <div className="improvement-actions">
        <button disabled={busy || !group.candidates.length} onClick={() => analyze(false)}>Analyze group locally</button>
        <button disabled={busy || !group.candidates.length} onClick={() => analyze(true)}>Analyze group with AI assistance</button>
        {busy && progress && <button onClick={() => { stop.current = true; setMessage('Stopping after the current candidate completes.') }}>Stop after current candidate</button>}
      </div>
      <p>AI assistance explicitly sends existing allowlisted candidate fields and the shared job description to the configured provider, sequentially. Contacts, organizations, projects and evidence records are excluded; redaction is best effort. Provider failures fall back locally.</p>
      {progress && <p role="status">{progress.completed} analyzed · {progress.failed} failed · {progress.pending} pending · {progress.total} total</p>}
      <div className="recruiter-filters">
        <label>Search candidates<input value={filters.search} onChange={(e) => filter('search', e.target.value)} /></label>
        <label>Review filter<select value={filters.review} onChange={(e) => filter('review', e.target.value)}><option value="">All reviews</option>{REVIEW_STATUSES.map((status) => <option key={status}>{status}</option>)}</select></label>
        <label>Analysis filter<select value={filters.analysis} onChange={(e) => filter('analysis', e.target.value)}><option value="">All analyses</option>{['pending', 'completed', 'outdated'].map((value) => <option key={value}>{value}</option>)}</select></label>
        <label>Score source filter<select value={filters.source} onChange={(e) => filter('source', e.target.value)}><option value="">All sources</option><option value="rule-based">Local</option><option value="ai">AI</option></select></label>
        <label>Processing filter<select value={filters.processing} onChange={(e) => filter('processing', e.target.value)}><option value="">All processing states</option><option>processing</option><option>completed</option></select></label>
        <label>Matched skill filter<input value={filters.matched} onChange={(e) => filter('matched', e.target.value)} /></label>
        <label>Not-evidenced skill filter<input value={filters.missing} onChange={(e) => filter('missing', e.target.value)} /></label>
        <button onClick={() => setFilters(EMPTY_FILTERS)}>Clear filters</button>
      </div>
      {!visible.length && <p>No candidates match these filters. Upload resumes or clear filters.</p>}
      <div className="recruiter-table" tabIndex={0} role="region" aria-label="Candidate list, scroll horizontally if needed">
        <table><thead><tr><th>Select</th><th>Candidate</th><th>Analysis</th><th>Review status</th><th>Actions</th></tr></thead>
          <tbody>{visible.map((row) => <tr key={row.id}>
            <td><input aria-label={`Compare ${row.name || row.filename}`} type="checkbox" disabled={busy || (!selected.includes(row.id) && selected.length >= limits.compare)} checked={selected.includes(row.id)} onChange={(e) => { setSelected((values) => e.target.checked ? [...values, row.id] : values.filter((id) => id !== row.id)); setRows([]) }} /></td>
            <td>{row.name || 'Name not found'}<br />{row.filename}<br />{(row.skills || []).join(', ')}</td>
            <td>{row.analysis_state} · {row.score_source || 'No score'}{row.overall_score != null && ` · ${row.overall_score} / 100`}{row.analysis_error && <p>{row.analysis_error}</p>}</td>
            <td><label>Review {row.name || row.filename}<select disabled={busy} value={row.status} onChange={(e) => review(row, e.target.value)}>{REVIEW_STATUSES.map((status) => <option key={status}>{status}</option>)}</select></label></td>
            <td><button disabled={busy} onClick={() => run(async () => { const detail = await request(`/${group.id}/candidates/${row.id}`); if (alive.current) setRows([detail]) })}>Review candidate</button>
              <button disabled={busy} onClick={() => run(async () => { await request(`/${group.id}/candidates/${row.id}`, { method: 'DELETE' }); setRows([]); setSelected((values) => values.filter((id) => id !== row.id)); await refresh(group.id) })}>Remove candidate</button></td>
          </tr>)}</tbody></table>
      </div>
      <button disabled={busy || !selected.length} onClick={() => run(async () => { const result = await request(`/${group.id}/comparison`, json('POST', { candidate_ids: selected, version: group.version })); if (alive.current) { setRows(result.candidates); setMessage(result.notice) } })}>Compare selected candidates</button>
      <p>Select up to {limits.compare} candidates from this job version. AI and local scores are not equally calibrated. No automatic ranking is applied.</p>
      <RecruiterComparison rows={rows} busy={busy} onReview={review} />
      <button disabled={busy} onClick={() => run(async () => { await request(`/${group.id}`, { method: 'DELETE' }); reset(); await list() })}>Remove workspace and its candidates</button>
    </>}
  </section>
}
