/**
 * Chunk 3.4: Review Dashboard
 *
 * Analyst views pending review tasks, approves/rejects records.
 */

import { useState } from 'react'
import { useReviewTasks, useApproveTask, useRejectTask } from '../hooks/useReviewTasks'
import { getErrorMessage } from '../utils/errorHandler'

function ReviewPage() {
  const [page, setPage] = useState(1)
  const [selectedTaskId, setSelectedTaskId] = useState(null)
  const [actionNotes, setActionNotes] = useState('')
  const [action, setAction] = useState(null) // 'approve' or 'reject'

  const { data: taskList, isLoading } = useReviewTasks({ page, status: 'PENDING' })
  const selectedTask = taskList?.results?.find(t => t.id === selectedTaskId)

  const { mutate: approve, isPending: isApproving } = useApproveTask(selectedTaskId)
  const { mutate: reject, isPending: isRejecting } = useRejectTask(selectedTaskId)

  if (isLoading) {
    return <div style={styles.container}>Loading review tasks...</div>
  }

  const tasks = taskList?.results || []

  const handleApprove = () => {
    approve(actionNotes, {
      onSuccess: () => {
        setSelectedTaskId(null)
        setActionNotes('')
        setAction(null)
      }
    })
  }

  const handleReject = () => {
    reject(actionNotes, {
      onSuccess: () => {
        setSelectedTaskId(null)
        setActionNotes('')
        setAction(null)
      }
    })
  }

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h1>Review Dashboard</h1>
        <p style={styles.subtitle}>Pending Records for Approval</p>
      </div>

      {tasks.length === 0 ? (
        <div style={styles.emptyState}>
          <p>✓ All caught up! No pending reviews.</p>
        </div>
      ) : (
        <>
          {/* Task Table */}
          <div style={styles.tableWrapper}>
            <table style={styles.table}>
              <thead>
                <tr>
                  <th>Facility</th>
                  <th>Scope 1</th>
                  <th>Year</th>
                  <th>Quality</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {tasks.map((task) => (
                  <tr
                    key={task.id}
                    style={{
                      ...styles.tableRow,
                      backgroundColor: selectedTaskId === task.id ? '#e7f3ff' : undefined
                    }}
                  >
                    <td>{task.normalized_record?.facility_name}</td>
                    <td>{task.normalized_record?.scope_1_emissions}</td>
                    <td>{task.normalized_record?.reporting_year}</td>
                    <td>
                      <span style={getQualityBadgeStyle(task.data_quality_score)}>
                        {task.data_quality_score}
                      </span>
                    </td>
                    <td>
                      <button
                        onClick={() => setSelectedTaskId(task.id)}
                        style={styles.reviewButton}
                      >
                        Review
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
              style={{...styles.paginationButton, opacity: !taskList?.previous ? 0.5 : 1}}
            >
              Previous
            </button>
            <span>Page {page}</span>
            <button
              onClick={() => setPage(p => p + 1)}
              disabled={!taskList?.next}
              style={{...styles.paginationButton, opacity: !taskList?.next ? 0.5 : 1}}
            >
              Next
            </button>
          </div>
        </>
      )}

      {/* Detail Modal */}
      {selectedTask && (
        <div style={styles.modal}>
          <div style={styles.modalContent}>
            <div style={styles.modalHeader}>
              <h2>{selectedTask.normalized_record?.facility_name}</h2>
              <button
                onClick={() => setSelectedTaskId(null)}
                style={styles.closeButton}
              >
                ✕
              </button>
            </div>

            <div style={styles.details}>
              <div style={styles.detailRow}>
                <span>Facility:</span>
                <strong>{selectedTask.normalized_record?.facility_name}</strong>
              </div>
              <div style={styles.detailRow}>
                <span>Scope 1:</span>
                <strong>{selectedTask.normalized_record?.scope_1_emissions}</strong>
              </div>
              <div style={styles.detailRow}>
                <span>Scope 2:</span>
                <strong>{selectedTask.normalized_record?.scope_2_emissions}</strong>
              </div>
              <div style={styles.detailRow}>
                <span>Year:</span>
                <strong>{selectedTask.normalized_record?.reporting_year}</strong>
              </div>
              <div style={styles.detailRow}>
                <span>Quality Score:</span>
                <strong>{selectedTask.data_quality_score}/100</strong>
              </div>
              <div style={styles.detailRow}>
                <span>Status:</span>
                <strong>{selectedTask.review_status}</strong>
              </div>
            </div>

            {/* Action Section */}
            {!action ? (
              <div style={styles.actionButtons}>
                <button
                  onClick={() => setAction('approve')}
                  style={{...styles.button, ...styles.approveButton}}
                >
                  ✓ Approve
                </button>
                <button
                  onClick={() => setAction('reject')}
                  style={{...styles.button, ...styles.rejectButton}}
                >
                  ✗ Reject
                </button>
              </div>
            ) : (
              <div style={styles.actionForm}>
                <label style={styles.label}>
                  {action === 'approve' ? 'Approval Notes (optional):' : 'Rejection Reason:'}
                </label>
                <textarea
                  value={actionNotes}
                  onChange={(e) => setActionNotes(e.target.value)}
                  placeholder="Enter notes..."
                  style={styles.textarea}
                />
                <div style={styles.formButtons}>
                  <button
                    onClick={action === 'approve' ? handleApprove : handleReject}
                    disabled={isApproving || isRejecting}
                    style={{...styles.button, ...styles.submitButton}}
                  >
                    {isApproving || isRejecting ? 'Processing...' : 'Submit'}
                  </button>
                  <button
                    onClick={() => {
                      setAction(null)
                      setActionNotes('')
                    }}
                    style={{...styles.button, ...styles.cancelButton}}
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function getQualityBadgeStyle(score) {
  let color = '#28a745'
  if (score < 70) color = '#dc3545'
  else if (score < 80) color = '#ffc107'

  return {
    padding: '4px 8px',
    backgroundColor: color,
    color: 'white',
    borderRadius: '4px',
    fontSize: '12px',
    fontWeight: 'bold'
  }
}

const styles = {
  container: {
    padding: '30px',
    maxWidth: '1200px',
    margin: '0 auto'
  },
  header: {
    marginBottom: '30px',
    borderBottom: '1px solid #ddd',
    paddingBottom: '20px'
  },
  subtitle: {
    margin: '10px 0 0 0',
    color: '#666',
    fontSize: '14px'
  },
  emptyState: {
    padding: '40px',
    textAlign: 'center',
    backgroundColor: '#d4edda',
    border: '1px solid #c3e6cb',
    borderRadius: '8px',
    color: '#155724'
  },
  tableWrapper: {
    overflowX: 'auto',
    marginBottom: '20px'
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
    backgroundColor: 'white',
    boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
  },
  tableRow: {
    borderBottom: '1px solid #eee',
    cursor: 'pointer',
    transition: 'background-color 0.2s'
  },
  reviewButton: {
    padding: '6px 12px',
    backgroundColor: '#007bff',
    color: 'white',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
    fontSize: '12px'
  },
  pagination: {
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    gap: '12px',
    marginTop: '20px'
  },
  paginationButton: {
    padding: '8px 16px',
    backgroundColor: '#f0f0f0',
    border: '1px solid #ddd',
    borderRadius: '4px',
    cursor: 'pointer'
  },
  modal: {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(0,0,0,0.5)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1000
  },
  modalContent: {
    backgroundColor: 'white',
    borderRadius: '8px',
    padding: '30px',
    maxWidth: '500px',
    width: '90%',
    maxHeight: '90vh',
    overflowY: 'auto'
  },
  modalHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '20px',
    borderBottom: '1px solid #eee',
    paddingBottom: '15px'
  },
  closeButton: {
    backgroundColor: 'transparent',
    border: 'none',
    fontSize: '20px',
    cursor: 'pointer'
  },
  details: {
    marginBottom: '20px'
  },
  detailRow: {
    display: 'flex',
    justifyContent: 'space-between',
    padding: '10px 0',
    borderBottom: '1px solid #f0f0f0',
    fontSize: '14px'
  },
  actionButtons: {
    display: 'flex',
    gap: '12px'
  },
  button: {
    padding: '10px 16px',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
    fontSize: '14px',
    fontWeight: '500'
  },
  approveButton: {
    flex: 1,
    backgroundColor: '#28a745',
    color: 'white'
  },
  rejectButton: {
    flex: 1,
    backgroundColor: '#dc3545',
    color: 'white'
  },
  actionForm: {
    marginTop: '20px'
  },
  label: {
    display: 'block',
    marginBottom: '8px',
    fontSize: '14px',
    fontWeight: '500'
  },
  textarea: {
    width: '100%',
    minHeight: '100px',
    padding: '10px',
    border: '1px solid #ddd',
    borderRadius: '4px',
    marginBottom: '12px',
    fontFamily: 'inherit'
  },
  formButtons: {
    display: 'flex',
    gap: '12px'
  },
  submitButton: {
    flex: 1,
    backgroundColor: '#007bff',
    color: 'white'
  },
  cancelButton: {
    flex: 1,
    backgroundColor: '#6c757d',
    color: 'white'
  }
}

export default ReviewPage
