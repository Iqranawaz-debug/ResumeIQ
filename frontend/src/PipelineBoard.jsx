import React, { useState } from 'react'
import { REVIEW_STATUSES, evidenceSummary, groupByStatus, topTags } from './recruiterState.js'

const TONE = { Shortlisted: 'success', 'Under Review': 'warning', 'Not Selected': 'danger', 'Not Reviewed': 'neutral' }
const DRAG_TYPE = 'application/x-resumeiq-candidate'

// Review-status board. Columns are the existing statuses; cards keep upload order (no score ordering).
// Cards move by drag and drop or the keyboard-accessible "Move to" menu; both call onMove(row, status),
// which persists through the existing review endpoint.
export default function PipelineBoard(props) {
  const [dropTarget, setDropTarget] = useState(null)
  return <BoardView {...props} dropTarget={dropTarget} onDropTarget={setDropTarget} />
}

// Stateless view (exported for tests): the drop highlight is passed in via dropTarget/onDropTarget.
export function BoardView({ rows, busy, onMove, dropTarget = null, onDropTarget = () => {} }) {
  const setDropTarget = onDropTarget
  const byId = new Map((rows || []).map((row) => [row.id, row]))

  function drop(event, status) {
    event.preventDefault()
    setDropTarget(null)
    const row = byId.get(event.dataTransfer.getData(DRAG_TYPE))
    if (row && row.status !== status && !busy) onMove(row, status)
  }

  return (
    <div className="rw-board" role="region" aria-label="Pipeline board. Drag cards between columns or use each card's Move to menu." tabIndex={0}>
      {groupByStatus(rows).map((column) => (
        <section key={column.status} aria-labelledby={`board-${column.status.replace(/\s+/g, '-')}`}
          className={`rw-board-column ${dropTarget === column.status ? 'drop-target' : ''}`}
          onDragOver={(event) => { if (!busy) { event.preventDefault(); event.dataTransfer.dropEffect = 'move'; setDropTarget(column.status) } }}
          onDragLeave={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) setDropTarget(null) }}
          onDrop={(event) => drop(event, column.status)}>
          <header className="rw-board-head">
            <h3 id={`board-${column.status.replace(/\s+/g, '-')}`}><span className={`status-dot tone-${TONE[column.status]}`} aria-hidden="true" />{column.status}</h3>
            <span className="rw-board-count" aria-label={`${column.rows.length} candidates`}>{column.rows.length}</span>
          </header>
          {column.rows.length === 0 ? <p className="rw-board-empty">Drop candidates here</p> : (
            <ul className="rw-board-cards">
              {column.rows.map((row) => {
                const name = row.name || 'Name not found'
                const tags = topTags(row)
                return (
                  <li key={row.id} className="rw-board-card" draggable={!busy}
                    onDragStart={(event) => { event.dataTransfer.setData(DRAG_TYPE, row.id); event.dataTransfer.effectAllowed = 'move' }}
                    onDragEnd={() => setDropTarget(null)}>
                    <p className="rw-candidate-name">{name}</p>
                    <p className="rw-hint">{row.filename}</p>
                    {(tags.shown.length > 0) && <ul className="rw-tag-chips rw-tag-chips-static" aria-label={`Tags for ${name}`}>
                      {tags.shown.map((tag) => <li key={tag}>{tag}</li>)}{tags.hidden > 0 && <li>+{tags.hidden}</li>}
                    </ul>}
                    <p className="rw-board-evidence">{evidenceSummary(row)}</p>
                    <label className="rw-board-move">
                      <span>Move {name} to</span>
                      <select value={row.status} disabled={busy} onChange={(event) => { if (event.target.value !== row.status) onMove(row, event.target.value) }}>
                        {REVIEW_STATUSES.map((status) => <option key={status} value={status}>{status}</option>)}
                      </select>
                    </label>
                  </li>
                )
              })}
            </ul>
          )}
        </section>
      ))}
    </div>
  )
}
