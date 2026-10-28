import React, { useState } from 'react'
import { ANNOTATION_LIMITS, noteError, tagError } from './recruiterState.js'

const formatTime = (value) => {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

// Private reviewer notes and tags for one candidate. Text renders as React text nodes (escaped).
// Callbacks return a promise that resolves true on success, so drafts clear only after saving.
export default function CandidateAnnotations({ row, busy, limits = ANNOTATION_LIMITS, onAddNote, onEditNote, onDeleteNote, onAddTag, onRemoveTag }) {
  const [draft, setDraft] = useState('')
  const [editing, setEditing] = useState(null)
  const [tagDraft, setTagDraft] = useState('')
  const [localError, setLocalError] = useState('')
  const name = row.name || row.filename
  const notes = row.notes || []
  const tags = row.tags || []

  async function addTag(event) {
    event.preventDefault()
    const problem = tagError(tagDraft, tags, limits)
    setLocalError(problem)
    if (!problem && await onAddTag(row, tagDraft)) setTagDraft('')
  }
  async function addNote(event) {
    event.preventDefault()
    const problem = noteError(draft, limits)
    setLocalError(problem)
    if (!problem && await onAddNote(row, draft)) setDraft('')
  }
  async function saveEdit(event) {
    event.preventDefault()
    const problem = noteError(editing.text, limits)
    setLocalError(problem)
    if (!problem && await onEditNote(row, editing.id, editing.text)) setEditing(null)
  }

  return <section className="rw-annotations" aria-label={`Private notes and tags for ${name}`}>
    <h4>Tags</h4>
    {tags.length > 0 ? <ul className="rw-tag-chips" aria-label="Tags">
      {tags.map((tag) => <li key={tag}>
        <span>{tag}</span>
        <button type="button" aria-label={`Remove tag ${tag}`} disabled={busy} onClick={() => onRemoveTag(row, tag)}>×</button>
      </li>)}
    </ul> : <p className="rw-hint">No tags yet.</p>}
    {tags.length < limits.tags && <form className="rw-inline-form" onSubmit={addTag}>
      <label className="rw-field">Add tag for {name}
        <input value={tagDraft} maxLength={limits.tag_chars * 2} placeholder="e.g. Phone screen" disabled={busy} onChange={(e) => setTagDraft(e.target.value)} />
      </label>
      <button className="rw-button rw-small" disabled={busy || !tagDraft.trim()}>Add tag</button>
    </form>}
    <p className="rw-hint">{tags.length} of {limits.tags} tags</p>

    <h4>Notes</h4>
    {notes.length === 0 && <p className="rw-hint">No notes yet.</p>}
    <ol className="rw-notes">
      {notes.map((note) => <li key={note.id}>
        {editing?.id === note.id ? <form onSubmit={saveEdit}>
          <label className="rw-field">Edit note
            <textarea rows={3} value={editing.text} maxLength={limits.note_chars * 2} disabled={busy} onChange={(e) => setEditing({ ...editing, text: e.target.value })} />
          </label>
          <div className="rw-actions">
            <button className="rw-button rw-small rw-primary" disabled={busy}>Save note</button>
            <button type="button" className="rw-button rw-small" disabled={busy} onClick={() => { setEditing(null); setLocalError('') }}>Cancel</button>
            <span className="rw-hint">{editing.text.trim().length}/{limits.note_chars}</span>
          </div>
        </form> : <>
          <p className="rw-note-text">{note.text}</p>
          <p className="rw-hint">{formatTime(note.created_at)}{note.updated_at ? ` · edited ${formatTime(note.updated_at)}` : ''}</p>
          <div className="rw-actions">
            <button type="button" className="link-button" disabled={busy} onClick={() => { setEditing({ id: note.id, text: note.text }); setLocalError('') }}>Edit note</button>
            <button type="button" className="link-button rw-delete-link" disabled={busy} onClick={() => onDeleteNote(row, note.id)}>Delete note</button>
          </div>
        </>}
      </li>)}
    </ol>
    {notes.length < limits.notes ? <form onSubmit={addNote}>
      <label className="rw-field">Add note for {name}
        <textarea rows={3} value={draft} maxLength={limits.note_chars * 2} placeholder="Private to your account. Never sent to AI." disabled={busy} onChange={(e) => setDraft(e.target.value)} />
      </label>
      <div className="rw-actions">
        <button className="rw-button rw-small rw-primary" disabled={busy || !draft.trim()}>Add note</button>
        <span className="rw-hint">{draft.trim().length}/{limits.note_chars}</span>
      </div>
    </form> : <p className="rw-hint">Note limit reached ({limits.notes}). Delete a note to add another.</p>}
    {localError && <p className="status error" role="alert">{localError}</p>}
  </section>
}
