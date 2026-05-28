import { useState } from 'react'
import { useReviewTasks, useApproveTask, useRejectTask } from '../hooks/useReviewTasks'
import { useCurrentUser } from '../hooks/useAuth'

function ReviewPage() {
  const { data: user } = useCurrentUser()
  const role = user?.role || 'VIEWER'
  const canAct = role === 'ADMIN' || role === 'ANALYST'

  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState('PENDING')
  const [hoveredPager, setHoveredPager] = useState(null)
  const [selectedTaskId, setSelectedTaskId] = useState(null)
  const [actionNotes, setActionNotes] = useState('')
  const [action, setAction] = useState(null)

  // Admin can view all statuses; others only see PENDING
  const effectiveStatus = canAct && role === 'ADMIN' ? statusFilter : 'PENDING'

  const { data: taskList, isLoading } = useReviewTasks({ page, status: effectiveStatus })
  const selectedTask = taskList?.results?.find(t => t.id === selectedTaskId)

  const { mutate: approve, isPending: isApproving } = useApproveTask(selectedTaskId)
  const { mutate: reject, isPending: isRejecting } = useRejectTask(selectedTaskId)

  const handleApprove = () => {
    approve(actionNotes, {
      onSuccess: () => { setSelectedTaskId(null); setActionNotes(''); setAction(null) }
    })
  }

  const handleReject = () => {
    reject(actionNotes, {
      onSuccess: () => { setSelectedTaskId(null); setActionNotes(''); setAction(null) }
    })
  }

  const statusTabs = [
    { key: 'PENDING', label: 'Pending' },
    { key: 'APPROVED', label: 'Approved' },
    { key: 'REJECTED', label: 'Rejected' },
  ]

  return (
    <div className="page-container">
      <style>{`
        .pager-btn { transition: background 0.15s, transform 0.1s; }
        .pager-btn:not(:disabled):hover { background: #e2e6ea !important; border-color: #adb5bd !important; }
        .pager-btn:not(:disabled):active { background: #ced4da !important; transform: translateY(1px); }
        .pager-btn:disabled { cursor: not-allowed; }
      `}</style>
      {/* Header */}
      <div style={styles.header}>
        <div>
          <h1>Review Dashboard</h1>
          <p style={styles.subtitle}>
            {role === 'ADMIN' ? 'All records — approve, reject or audit decisions'
              : role === 'ANALYST' ? 'Records waiting for your approval'
              : 'Records queue — read only'}
          </p>
        </div>
        <span style={rolePillStyle(role)}>{role}</span>
      </div>

      {/* Status tabs — admin only */}
      {role === 'ADMIN' && (
        <div style={styles.tabs}>
          {statusTabs.map(tab => (
            <button
              key={tab.key}
              onClick={() => { setStatusFilter(tab.key); setPage(1) }}
              style={{
                ...styles.tab,
                ...(statusFilter === tab.key ? styles.tabActive : {})
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>
      )}

      {isLoading ? (
        <div style={styles.loading}>Loading tasks…</div>
      ) : !taskList?.results?.length ? (
        <div style={styles.emptyState}>
          <div style={styles.emptyIcon}>✓</div>
          <p style={styles.emptyTitle}>All caught up!</p>
          <p style={styles.emptyText}>No {effectiveStatus.toLowerCase()} review tasks.</p>
        </div>
      ) : (
        <>
          {/* Task Table */}
          <div className="table-scroll" style={{ marginBottom: 20 }}>
            <table style={styles.table}>
              <thead>
                <tr style={styles.thead}>
                  <th style={styles.th}>Facility</th>
                  <th style={styles.th}>Year</th>
                  <th style={styles.th}>Scope 1</th>
                  <th style={styles.th}>Scope 2</th>
                  <th style={styles.th}>Quality</th>
                  <th style={styles.th}>Priority</th>
                  {role === 'ADMIN' && statusFilter !== 'PENDING' && (
                    <th style={styles.th}>Reviewed By</th>
                  )}
                  <th style={styles.th}>Action</th>
                </tr>
              </thead>
              <tbody>
                {taskList.results.map((task) => (
                  <tr
                    key={task.id}
                    style={{
                      ...styles.tr,
                      backgroundColor: selectedTaskId === task.id ? '#e7f3ff' : undefined
                    }}
                  >
                    <td style={styles.td}>{task.facility_name || '—'}</td>
                    <td style={styles.td}>{task.reporting_year || '—'}</td>
                    <td style={styles.td}>{task.scope_1_emissions ?? '—'}</td>
                    <td style={styles.td}>{task.scope_2_emissions ?? '—'}</td>
                    <td style={styles.td}>
                      <span style={qualityBadge(task.data_quality_score)}>
                        {task.data_quality_score ?? '—'}
                      </span>
                    </td>
                    <td style={styles.td}>
                      <span style={priorityBadge(task.priority)}>{task.priority}</span>
                    </td>
                    {role === 'ADMIN' && statusFilter !== 'PENDING' && (
                      <td style={styles.td}>
                        {task.approved_by_name || task.rejected_by_name || '—'}
                      </td>
                    )}
                    <td style={styles.td}>
                      <button
                        onClick={() => { setSelectedTaskId(task.id); setAction(null); setActionNotes('') }}
                        style={styles.reviewBtn}
                      >
                        {canAct && task.status === 'PENDING' ? 'Review' : 'View'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div style={styles.pagination}>
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={!taskList?.previous}
              onMouseEnter={() => taskList?.previous && setHoveredPager('prev')}
              onMouseLeave={() => setHoveredPager(null)}
              style={{
                ...styles.pageBtn,
                opacity: taskList?.previous ? 1 : 0.4,
                cursor: taskList?.previous ? 'pointer' : 'not-allowed',
                backgroundColor: hoveredPager === 'prev' ? '#d0d7de' : '#f0f0f0',
                transform: hoveredPager === 'prev' ? 'translateY(1px)' : 'none',
                transition: 'background-color 0.15s, transform 0.1s'
              }}
            >
              ← Previous
            </button>
            <span style={styles.pageLabel}>Page {page}</span>
            <button
              onClick={() => setPage(p => p + 1)}
              disabled={!taskList?.next}
              onMouseEnter={() => taskList?.next && setHoveredPager('next')}
              onMouseLeave={() => setHoveredPager(null)}
              style={{
                ...styles.pageBtn,
                opacity: taskList?.next ? 1 : 0.4,
                cursor: taskList?.next ? 'pointer' : 'not-allowed',
                backgroundColor: hoveredPager === 'next' ? '#d0d7de' : '#f0f0f0',
                transform: hoveredPager === 'next' ? 'translateY(1px)' : 'none',
                transition: 'background-color 0.15s, transform 0.1s'
              }}
            >
              Next →
            </button>
          </div>
        </>
      )}

      {/* Detail Modal */}
      {selectedTask && (
        <div style={styles.overlay} onClick={() => setSelectedTaskId(null)}>
          <div style={styles.modal} onClick={e => e.stopPropagation()}>
            <div style={styles.modalHeader}>
              <h2 style={{ margin: 0 }}>{selectedTask.facility_name || 'Record'}</h2>
              <button style={styles.closeBtn} onClick={() => setSelectedTaskId(null)}>✕</button>
            </div>

            <div style={styles.detailGrid}>
              {[
                ['Facility',       selectedTask.facility_name],
                ['Year',           selectedTask.reporting_year],
                ['Scope 1 (MT)',   selectedTask.scope_1_emissions],
                ['Scope 2 (MT)',   selectedTask.scope_2_emissions],
                ['Scope 3 (MT)',   selectedTask.scope_3_emissions],
                ['Quality Score',  `${selectedTask.data_quality_score ?? '—'} / 100`],
                ['Status',         selectedTask.status],
                ['Priority',       selectedTask.priority],
              ].map(([label, value]) => (
                <div key={label} style={styles.detailRow}>
                  <span style={styles.detailLabel}>{label}</span>
                  <strong style={styles.detailValue}>{value ?? '—'}</strong>
                </div>
              ))}

              {selectedTask.validation_errors?.length > 0 && (
                <div style={{ gridColumn: '1 / -1', ...styles.errorsBox }}>
                  <strong>Validation Issues:</strong>
                  <ul style={{ margin: '6px 0 0 16px', fontSize: 13 }}>
                    {selectedTask.validation_errors.map((e, i) => (
                      <li key={i}>{e.field}: {e.error}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            {/* Action area */}
            {canAct && selectedTask.status === 'PENDING' && (
              <div style={styles.actionArea}>
                {!action ? (
                  <div style={styles.actionBtns}>
                    <button style={styles.approveBtn} onClick={() => setAction('approve')}>✓ Approve</button>
                    <button style={styles.rejectBtn}  onClick={() => setAction('reject')}>✗ Reject</button>
                  </div>
                ) : (
                  <>
                    <label style={styles.notesLabel}>
                      {action === 'approve' ? 'Approval notes (optional)' : 'Rejection reason'}
                    </label>
                    <textarea
                      value={actionNotes}
                      onChange={e => setActionNotes(e.target.value)}
                      placeholder="Enter notes…"
                      style={styles.textarea}
                    />
                    <div style={styles.actionBtns}>
                      <button
                        onClick={action === 'approve' ? handleApprove : handleReject}
                        disabled={isApproving || isRejecting}
                        style={action === 'approve' ? styles.approveBtn : styles.rejectBtn}
                      >
                        {isApproving || isRejecting ? 'Processing…' : 'Submit'}
                      </button>
                      <button style={styles.cancelBtn} onClick={() => { setAction(null); setActionNotes('') }}>
                        Cancel
                      </button>
                    </div>
                  </>
                )}
              </div>
            )}

            {!canAct && (
              <div style={styles.readOnlyNotice}>
                Your role ({role}) does not have permission to approve or reject records.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

/* ---- helpers ---- */
const rolePillStyle = (role) => {
  const bg = { ADMIN: '#dc3545', ANALYST: '#007bff', DATA_PROVIDER: '#fd7e14', VIEWER: '#6c757d' }
  return {
    padding: '4px 12px', borderRadius: 12, fontSize: 12, fontWeight: 700,
    background: bg[role] || '#6c757d', color: '#fff', alignSelf: 'flex-start'
  }
}

const qualityBadge = (score) => ({
  padding: '2px 8px', borderRadius: 4, fontSize: 12, fontWeight: 'bold', color: '#fff',
  backgroundColor: score == null ? '#aaa' : score >= 80 ? '#28a745' : score >= 60 ? '#ffc107' : '#dc3545'
})

const priorityBadge = (p) => ({
  padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600,
  backgroundColor: p === 'HIGH' ? '#f8d7da' : p === 'MEDIUM' ? '#fff3cd' : '#d4edda',
  color: p === 'HIGH' ? '#721c24' : p === 'MEDIUM' ? '#856404' : '#155724'
})

const styles = {
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24, borderBottom: '1px solid #ddd', paddingBottom: 20 },
  subtitle: { margin: '6px 0 0', color: '#666', fontSize: 14 },
  tabs: { display: 'flex', gap: 4, marginBottom: 20 },
  tab: { padding: '8px 20px', border: '1px solid #ddd', borderRadius: 4, background: '#f8f9fa', color: '#555', cursor: 'pointer', fontSize: 14 },
  tabActive: { background: '#007bff', color: '#fff', borderColor: '#007bff' },
  loading: { padding: 40, textAlign: 'center', color: '#666' },
  emptyState: { padding: '60px 40px', textAlign: 'center', background: '#d4edda', border: '1px solid #c3e6cb', borderRadius: 8, color: '#155724' },
  emptyIcon: { fontSize: 40, marginBottom: 12 },
  emptyTitle: { fontSize: 18, fontWeight: 600, margin: '0 0 6px' },
  emptyText: { margin: 0, fontSize: 14 },
  table: { width: '100%', borderCollapse: 'collapse', backgroundColor: 'white', fontSize: 14 },
  thead: { backgroundColor: '#f1f3f5' },
  th: { padding: '10px 14px', textAlign: 'left', fontWeight: 600, color: '#495057', borderBottom: '2px solid #dee2e6', whiteSpace: 'nowrap' },
  tr: { borderBottom: '1px solid #eee' },
  td: { padding: '10px 14px', color: '#333', whiteSpace: 'nowrap' },
  reviewBtn: { padding: '5px 14px', background: '#007bff', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: 12 },
  pagination: { display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 16 },
  pageBtn: { padding: '7px 16px', background: '#f0f0f0', border: '1px solid #ddd', borderRadius: 4, cursor: 'pointer' },
  pageLabel: { fontSize: 14, color: '#555' },
  overlay: { position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: 16 },
  modal: { background: '#fff', borderRadius: 8, padding: 28, width: '100%', maxWidth: 520, maxHeight: '90vh', overflowY: 'auto' },
  modalHeader: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20, paddingBottom: 14, borderBottom: '1px solid #eee' },
  closeBtn: { background: 'none', border: 'none', fontSize: 20, cursor: 'pointer', color: '#888', padding: 0 },
  detailGrid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0', marginBottom: 20 },
  detailRow: { display: 'flex', flexDirection: 'column', padding: '10px 0', borderBottom: '1px solid #f0f0f0' },
  detailLabel: { fontSize: 11, color: '#888', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 2 },
  detailValue: { fontSize: 14, color: '#333' },
  errorsBox: { padding: '10px 14px', background: '#fff3f3', border: '1px solid #f5c6cb', borderRadius: 6, fontSize: 13, color: '#721c24', marginTop: 8 },
  actionArea: { borderTop: '1px solid #eee', paddingTop: 20 },
  actionBtns: { display: 'flex', gap: 10 },
  approveBtn: { flex: 1, padding: '10px 16px', background: '#28a745', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer', fontWeight: 600 },
  rejectBtn: { flex: 1, padding: '10px 16px', background: '#dc3545', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer', fontWeight: 600 },
  cancelBtn: { flex: 1, padding: '10px 16px', background: '#6c757d', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer' },
  notesLabel: { display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 8 },
  textarea: { width: '100%', minHeight: 90, padding: 10, border: '1px solid #ddd', borderRadius: 4, fontFamily: 'inherit', fontSize: 13, marginBottom: 12 },
  readOnlyNotice: { marginTop: 20, padding: '10px 14px', background: '#f8f9fa', border: '1px solid #dee2e6', borderRadius: 4, fontSize: 13, color: '#666', textAlign: 'center' }
}

export default ReviewPage
