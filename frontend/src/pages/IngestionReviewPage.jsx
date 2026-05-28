/**
 * Chunk 3.3: Ingestion Review Page
 *
 * Shows ingestion status, parsed rows, and allows triggering
 * parse/normalize workflow steps.
 */

import { useParams } from 'react-router-dom'
import { useIngestionDetail, useParse, useNormalize } from '../hooks/useIngestions'

function IngestionReviewPage() {
  const { id: ingestionId } = useParams()
  const { data: ingestion, isLoading } = useIngestionDetail(ingestionId)
  const { mutate: parse, isPending: isParsing } = useParse(ingestionId)
  const { mutate: normalize, isPending: isNormalizing, isError: normalizeError, error: normalizeErrorDetail } = useNormalize(ingestionId)

  if (isLoading) {
    return <div style={styles.container}>Loading ingestion...</div>
  }

  if (!ingestion) {
    return <div style={styles.container}>Ingestion not found</div>
  }

  const isParsed = ingestion.step !== 'UPLOADED'
  const isNormalized = ingestion.step === 'NORMALIZED'
  const isWorking = isParsing || isNormalizing

  const stepNumber = ingestion.step === 'UPLOADED' ? 1 : ingestion.step === 'PARSED' ? 2 : 3
  const stepLabel = isParsing ? 'Parsing…' : isNormalizing ? 'Normalizing…' : ingestion.step

  return (
    <div className="page-container" style={{ maxWidth: 1000 }}>
      <style>{`
        @keyframes slide {
          from { background-position: 0 0; }
          to { background-position: 40px 0; }
        }
      `}</style>
      <div style={styles.header}>
        <h1>Ingestion Review</h1>
        <p style={styles.dataSourceId}>{ingestion.data_source_id}</p>
      </div>

      {/* Status Card */}
      <div style={styles.statusCard}>
        <div style={styles.statusRow}>
          <span>Status:</span>
          <strong style={isWorking ? { color: '#007bff' } : {}}>{stepLabel}</strong>
        </div>
        <div className="status-row">
          <span>Progress:</span>
          <div className="progress-bar-wrap">
            <div style={{
              ...styles.progressFill,
              width: isWorking ? '100%' : `${ingestion.completion_percentage}%`,
              backgroundImage: isWorking
                ? 'repeating-linear-gradient(45deg, transparent, transparent 10px, rgba(255,255,255,0.15) 10px, rgba(255,255,255,0.15) 20px)'
                : 'none',
              animation: isWorking ? 'slide 1s linear infinite' : 'none',
              transition: isWorking ? 'none' : 'width 0.6s ease'
            }}></div>
          </div>
          <span style={{ fontSize: 13, color: '#495057', whiteSpace: 'nowrap' }}>
            {isWorking ? 'Working…' : `Step ${stepNumber} of 3 (${ingestion.completion_percentage}%)`}
          </span>
        </div>
        <div style={styles.stepHint}>
          Upload → Parse → Normalize
        </div>
      </div>

      {/* Action Buttons */}
      <div style={styles.actions}>
        {!isParsed && (
          <button
            onClick={() => parse()}
            disabled={isParsing}
            style={{
              ...styles.button,
              ...styles.primaryButton,
              opacity: isParsing ? 0.6 : 1
            }}
          >
            {isParsing ? 'Parsing...' : 'Parse CSV'}
          </button>
        )}

        {isParsed && !isNormalized && (
          <div>
            <button
              onClick={() => normalize()}
              disabled={isNormalizing}
              style={{
                ...styles.button,
                ...styles.primaryButton,
                opacity: isNormalizing ? 0.6 : 1
              }}
            >
              {isNormalizing ? 'Normalizing...' : 'Normalize & Validate'}
            </button>
            {normalizeError && (
              <div style={styles.errorBox}>
                Normalization failed: {normalizeErrorDetail?.response?.data?.error || normalizeErrorDetail?.message || 'Unknown error'}
              </div>
            )}
          </div>
        )}

        {isNormalized && (
          <div style={styles.successBox}>
            ✓ Normalization complete. Records are ready for review.
          </div>
        )}
      </div>

      {/* Sample Parsed Records */}
      {ingestion.sample_parsed_records && ingestion.sample_parsed_records.length > 0 && (
        <div style={styles.section}>
          <h2>Parsed Records (sample of {ingestion.sample_parsed_records.length})</h2>
          <div className="table-scroll">
            <table style={styles.dataTable}>
              <thead>
                <tr>
                  <th style={styles.th}>#</th>
                  {(ingestion.csv_columns || Object.keys(ingestion.sample_parsed_records[0].raw_values || {})).map(col => (
                    <th key={col} style={styles.th}>{col}</th>
                  ))}
                  <th style={styles.th}>Errors</th>
                </tr>
              </thead>
              <tbody>
                {ingestion.sample_parsed_records.map((record, idx) => (
                  <tr key={idx} style={idx % 2 === 0 ? styles.trEven : styles.trOdd}>
                    <td style={styles.td}>{record.source_row_number}</td>
                    {(ingestion.csv_columns || Object.keys(record.raw_values || {})).map(col => (
                      <td key={col} style={styles.td}>{record.raw_values?.[col] ?? '—'}</td>
                    ))}
                    <td style={{...styles.td, color: record.parsing_errors?.length > 0 ? '#dc3545' : '#666'}}>
                      {record.parsing_errors?.length > 0 ? record.parsing_errors.join(', ') : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Sample Normalized Records */}
      {ingestion.sample_normalized_records && ingestion.sample_normalized_records.length > 0 && (
        <div style={styles.section}>
          <h2>Normalized Records ({ingestion.sample_normalized_records.length})</h2>
          <div className="table-scroll">
            <table style={styles.dataTable}>
              <thead>
                <tr>
                  <th style={styles.th}>Facility</th>
                  <th style={styles.th}>Scope 1 (mtCO2e)</th>
                  <th style={styles.th}>Scope 2 (mtCO2e)</th>
                  <th style={styles.th}>Scope 3 (mtCO2e)</th>
                  <th style={styles.th}>Year</th>
                  <th style={styles.th}>Quality Score</th>
                  <th style={styles.th}>Valid</th>
                </tr>
              </thead>
              <tbody>
                {ingestion.sample_normalized_records.map((record, idx) => (
                  <tr key={idx} style={idx % 2 === 0 ? styles.trEven : styles.trOdd}>
                    <td style={styles.td}>{record.facility_name ?? '—'}</td>
                    <td style={styles.td}>{record.scope_1_emissions != null ? Number(record.scope_1_emissions).toFixed(4) : '—'}</td>
                    <td style={styles.td}>{record.scope_2_emissions != null ? Number(record.scope_2_emissions).toFixed(4) : '—'}</td>
                    <td style={styles.td}>{record.scope_3_emissions != null ? Number(record.scope_3_emissions).toFixed(4) : '—'}</td>
                    <td style={styles.td}>{record.reporting_year ?? '—'}</td>
                    <td style={styles.td}>{record.data_quality_score ?? '—'}</td>
                    <td style={{...styles.td, color: record.is_valid ? '#28a745' : '#dc3545', fontWeight: '600'}}>
                      {record.is_valid ? '✓ Valid' : '✗ Invalid'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Summary */}
      {ingestion.summary && (
        <div style={styles.summaryBox}>
          <h2>Summary</h2>
          <div style={styles.summaryGrid}>
            <div style={styles.summaryItem}>
              <span style={styles.summaryLabel}>Total Records</span>
              <span style={styles.summaryValue}>{ingestion.summary.total_records}</span>
            </div>
            <div style={styles.summaryItem}>
              <span style={styles.summaryLabel}>Valid</span>
              <span style={{...styles.summaryValue, color: '#28a745'}}>
                {ingestion.summary.valid_records}
              </span>
            </div>
            <div style={styles.summaryItem}>
              <span style={styles.summaryLabel}>Warnings</span>
              <span style={{...styles.summaryValue, color: '#ffc107'}}>
                {ingestion.summary.warning_records}
              </span>
            </div>
            <div style={styles.summaryItem}>
              <span style={styles.summaryLabel}>Errors</span>
              <span style={{...styles.summaryValue, color: '#dc3545'}}>
                {ingestion.summary.error_records}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

const styles = {
  container: {
    padding: '30px',
    maxWidth: '1000px',
    margin: '0 auto'
  },
  header: {
    marginBottom: '30px',
    borderBottom: '1px solid #ddd',
    paddingBottom: '20px'
  },
  dataSourceId: {
    margin: '10px 0 0 0',
    color: '#666',
    fontSize: '14px'
  },
  statusCard: {
    backgroundColor: '#f9f9f9',
    border: '1px solid #ddd',
    borderRadius: '8px',
    padding: '20px',
    marginBottom: '20px'
  },
  statusRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '15px',
    marginBottom: '15px',
    fontSize: '14px'
  },
  progressBar: {
    flex: 1,
    height: '20px',
    backgroundColor: '#e9ecef',
    borderRadius: '10px',
    overflow: 'hidden'
  },
  progressFill: {
    height: '100%',
    backgroundColor: '#007bff',
    transition: 'width 0.3s'
  },
  actions: {
    display: 'flex',
    gap: '12px',
    marginBottom: '30px'
  },
  button: {
    padding: '12px 24px',
    fontSize: '14px',
    fontWeight: '500',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer'
  },
  primaryButton: {
    backgroundColor: '#007bff',
    color: 'white'
  },
  successBox: {
    padding: '12px',
    backgroundColor: '#d4edda',
    border: '1px solid #c3e6cb',
    borderRadius: '4px',
    color: '#155724',
    fontSize: '14px'
  },
  errorBox: {
    marginTop: '10px',
    padding: '12px',
    backgroundColor: '#f8d7da',
    border: '1px solid #f5c6cb',
    borderRadius: '4px',
    color: '#721c24',
    fontSize: '14px'
  },
  section: {
    marginBottom: '30px'
  },
  table: {
    overflowX: 'auto',
    marginTop: '15px'
  },
  tableWrapper: {
    overflowX: 'auto',
    marginTop: '15px',
    borderRadius: '6px',
    border: '1px solid #dee2e6'
  },
  dataTable: {
    width: '100%',
    borderCollapse: 'collapse',
    fontSize: '13px'
  },
  th: {
    backgroundColor: '#f1f3f5',
    padding: '10px 14px',
    textAlign: 'left',
    fontWeight: '600',
    color: '#495057',
    borderBottom: '2px solid #dee2e6',
    whiteSpace: 'nowrap'
  },
  td: {
    padding: '9px 14px',
    borderBottom: '1px solid #e9ecef',
    color: '#333',
    whiteSpace: 'nowrap'
  },
  trEven: {
    backgroundColor: '#ffffff'
  },
  trOdd: {
    backgroundColor: '#f8f9fa'
  },
  progressLabel: {
    fontSize: '13px',
    color: '#495057',
    minWidth: '120px'
  },
  stepHint: {
    fontSize: '12px',
    color: '#888',
    marginTop: '6px'
  },
  summaryBox: {
    backgroundColor: '#f8f9fa',
    border: '1px solid #dee2e6',
    borderRadius: '8px',
    padding: '20px'
  },
  summaryGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
    gap: '15px',
    marginTop: '15px'
  },
  summaryItem: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px'
  },
  summaryLabel: {
    fontSize: '12px',
    color: '#666',
    fontWeight: '500',
    textTransform: 'uppercase'
  },
  summaryValue: {
    fontSize: '24px',
    fontWeight: 'bold',
    color: '#333'
  }
}

export default IngestionReviewPage
