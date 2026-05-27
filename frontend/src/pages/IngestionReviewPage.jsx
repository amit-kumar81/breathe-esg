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
  const { mutate: normalize, isPending: isNormalizing } = useNormalize(ingestionId)

  if (isLoading) {
    return <div style={styles.container}>Loading ingestion...</div>
  }

  if (!ingestion) {
    return <div style={styles.container}>Ingestion not found</div>
  }

  const isParsed = ingestion.step !== 'UPLOADED'
  const isNormalized = ingestion.step === 'NORMALIZED'

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h1>Ingestion Review</h1>
        <p style={styles.dataSourceId}>{ingestion.data_source_id}</p>
      </div>

      {/* Status Card */}
      <div style={styles.statusCard}>
        <div style={styles.statusRow}>
          <span>Status:</span>
          <strong>{ingestion.step}</strong>
        </div>
        <div style={styles.statusRow}>
          <span>Progress:</span>
          <div style={styles.progressBar}>
            <div style={{
              ...styles.progressFill,
              width: `${ingestion.completion_percentage}%`
            }}></div>
          </div>
          <span>{ingestion.completion_percentage}%</span>
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
          <div style={styles.table}>
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  {Object.keys(ingestion.sample_parsed_records[0].raw_values || {}).map(col => (
                    <th key={col}>{col}</th>
                  ))}
                  <th>Errors</th>
                </tr>
              </thead>
              <tbody>
                {ingestion.sample_parsed_records.map((record, idx) => (
                  <tr key={idx}>
                    <td>{record.source_row_number}</td>
                    {Object.values(record.raw_values || {}).map((val, i) => (
                      <td key={i}>{val ?? 'N/A'}</td>
                    ))}
                    <td>{record.parsing_errors?.length > 0 ? record.parsing_errors.join(', ') : '—'}</td>
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
          <div style={styles.table}>
            <table>
              <thead>
                <tr>
                  <th>Facility</th>
                  <th>Scope 1</th>
                  <th>Year</th>
                  <th>Quality Score</th>
                  <th>Valid</th>
                </tr>
              </thead>
              <tbody>
                {ingestion.sample_normalized_records.map((record, idx) => (
                  <tr key={idx}>
                    <td>{record.facility_name}</td>
                    <td>{record.scope_1_emissions}</td>
                    <td>{record.reporting_year}</td>
                    <td>{record.data_quality_score}</td>
                    <td>{record.is_valid ? '✓' : '✗'}</td>
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
  section: {
    marginBottom: '30px'
  },
  table: {
    overflowX: 'auto',
    marginTop: '15px'
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
