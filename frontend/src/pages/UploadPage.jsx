import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useUploadCSV, useDataSources, useIngestions } from '../hooks/useIngestions'
import { getErrorMessage } from '../utils/errorHandler'

function UploadPage() {
  const navigate = useNavigate()
  const { mutate: upload, isPending, error, data, reset } = useUploadCSV()
  const { data: dsData, isLoading: dsLoading } = useDataSources()
  const { data: historyData, isLoading: historyLoading, isError: historyError } = useIngestions()

  const [file, setFile] = useState(null)
  const [dataSourceId, setDataSourceId] = useState('')
  const [touched, setTouched] = useState({})
  const [selectedIngestionId, setSelectedIngestionId] = useState(null)

  const handleFileChange = (e) => {
    const selectedFile = e.target.files?.[0]
    if (selectedFile) {
      // Validate: only CSV files
      if (!selectedFile.name.endsWith('.csv')) {
        alert('Only .csv files are allowed')
        return
      }
      setFile(selectedFile)
      setTouched({ ...touched, file: true })
    }
  }

  const handleBlur = (field) => {
    setTouched({ ...touched, [field]: true })
  }

  const handleSubmit = (e) => {
    e.preventDefault()

    // Validate
    if (!file || !dataSourceId) {
      setTouched({ file: true, dataSourceId: true })
      return
    }

    // Upload
    upload({ file, dataSourceId })
  }

  // After successful upload, show success banner + full ingestion history
  if (data && !isPending) {
    const justUploadedId = data.ingestion_id
    const activeId = selectedIngestionId || justUploadedId
    const allIngestions = historyData?.results || []

    return (
      <div className="page-container" style={{ maxWidth: 900 }}>
        {/* Success banner */}
        <div style={styles.successBanner}>
          <span style={styles.successIcon}>✓</span>
          <div>
            <strong>{data.filename}</strong> uploaded successfully — {data.line_count} rows
          </div>
        </div>

        {/* History table with selection */}
        <div style={styles.historyCard}>
          <div style={styles.historyCardHeader}>
            <h2 style={styles.historyTitle}>Your Uploads</h2>
            <p style={styles.historySubtitle}>Select a file below, then click Review &amp; Parse</p>
          </div>

          <div className="table-scroll">
            <table style={styles.historyTable}>
              <thead>
                <tr style={styles.historyThead}>
                  <th style={{ ...styles.historyTh, width: 36 }}></th>
                  <th style={styles.historyTh}>File</th>
                  <th style={styles.historyTh}>Data Source</th>
                  <th style={styles.historyTh}>Rows</th>
                  <th style={styles.historyTh}>Step</th>
                  <th style={styles.historyTh}>Uploaded</th>
                </tr>
              </thead>
              <tbody>
                {historyLoading ? (
                  <tr><td colSpan={6} style={{ ...styles.historyTd, textAlign: 'center', color: '#888' }}>Loading uploads…</td></tr>
                ) : historyError || allIngestions.length === 0 ? (
                  <tr><td colSpan={6} style={{ ...styles.historyTd, textAlign: 'center', color: '#888' }}>No uploads found</td></tr>
                ) : allIngestions.map((ing) => {
                  const isSelected = ing.id === activeId
                  const isNew = ing.id === justUploadedId
                  return (
                    <tr
                      key={ing.id}
                      onClick={() => setSelectedIngestionId(ing.id)}
                      style={{
                        ...styles.historyTr,
                        backgroundColor: isSelected ? '#e7f3ff' : undefined,
                        cursor: 'pointer'
                      }}
                    >
                      <td style={styles.historyTd}>
                        <input
                          type="radio"
                          name="ingestion"
                          checked={isSelected}
                          onChange={() => setSelectedIngestionId(ing.id)}
                          style={{ cursor: 'pointer' }}
                        />
                      </td>
                      <td style={styles.historyTd}>
                        {ing.filename}
                        {isNew && <span style={styles.newBadge}>NEW</span>}
                      </td>
                      <td style={styles.historyTd}>{ing.data_source_name}</td>
                      <td style={styles.historyTd}>{ing.line_count}</td>
                      <td style={styles.historyTd}>
                        <span style={stepBadge(ing.step)}>{ing.step}</span>
                      </td>
                      <td style={styles.historyTd}>
                        {new Date(ing.created_at).toLocaleString()}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          <div style={styles.historyActions}>
            <button
              style={styles.primaryButton}
              onClick={() => navigate(`/ingest/${activeId}`)}
            >
              Review &amp; Parse
            </button>
            <button
              style={styles.secondaryButton}
              onClick={() => {
                reset()
                setFile(null)
                setDataSourceId('')
                setTouched({})
                setSelectedIngestionId(null)
              }}
            >
              Upload Another
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="page-container" style={{ maxWidth: 640 }}>
      <div className="page-card">
        <h1 style={styles.title}>Upload Emissions Data</h1>
        <p style={styles.description}>
          Upload a CSV file containing emissions data. We'll parse it, validate each record, and flag issues.
        </p>

        <form onSubmit={handleSubmit} style={styles.form}>
          {/* Error Alert */}
          {error && (
            <div style={styles.alert}>
              <strong>Upload Failed</strong>
              <p>{getErrorMessage(error)}</p>
            </div>
          )}

          {/* File Input */}
          <div style={styles.formGroup}>
            <label style={styles.label}>CSV File *</label>
            <div style={styles.fileInput}>
              <input
                type="file"
                accept=".csv"
                onChange={handleFileChange}
                disabled={isPending}
                style={styles.hiddenInput}
                id="file-input"
              />
              <label htmlFor="file-input" style={styles.fileLabel}>
                {file ? `📄 ${file.name}` : '📁 Click to select CSV file'}
              </label>
            </div>
            {touched.file && !file && (
              <p style={styles.errorText}>CSV file is required</p>
            )}
            {file && (
              <p style={styles.fileSelectedText}>✓ File selected: {file.name}</p>
            )}
          </div>

          {/* Data Source Dropdown */}
          <div style={styles.formGroup}>
            <label htmlFor="datasource" style={styles.label}>Data Source *</label>
            <select
              id="datasource"
              value={dataSourceId}
              onChange={(e) => setDataSourceId(e.target.value)}
              onBlur={() => handleBlur('dataSourceId')}
              disabled={isPending || dsLoading}
              style={{
                ...styles.input,
                borderColor: touched.dataSourceId && !dataSourceId ? '#dc3545' : undefined
              }}
            >
              <option value="">{dsLoading ? 'Loading...' : '— Select a data source —'}</option>
              {(Array.isArray(dsData) ? dsData : dsData?.results || []).map(ds => (
                <option key={ds.id} value={ds.id}>{ds.name}</option>
              ))}
            </select>
            {touched.dataSourceId && !dataSourceId && (
              <p style={styles.errorText}>Data source is required</p>
            )}
          </div>

          {/* Submit Button */}
          <button
            type="submit"
            disabled={isPending || !file}
            style={{
              ...styles.button,
              opacity: isPending || !file ? 0.6 : 1,
              cursor: isPending || !file ? 'not-allowed' : 'pointer'
            }}
          >
            {isPending ? (
              <>
                <span style={styles.spinner}></span>
                Uploading...
              </>
            ) : (
              'Upload CSV'
            )}
          </button>
        </form>

        {/* CSV Format Help */}
        <div style={styles.helpBox}>
          <h3 style={styles.helpTitle}>CSV Format by Data Source</h3>
          <p style={styles.helpText}><strong>SAP GHG Export</strong> — semicolon-delimited:</p>
          <ul style={styles.helpList}>
            <li><code>Werksname</code> — facility/plant name</li>
            <li><code>Buchungsjahr</code> — reporting year (YYYY)</li>
            <li><code>Scope1_tCO2e</code>, <code>Scope2_tCO2e</code>, <code>Scope3_tCO2e</code> — emissions</li>
          </ul>
          <p style={styles.helpText}><strong>Utility Portal CSV</strong> — comma-delimited:</p>
          <ul style={styles.helpList}>
            <li><code>Site_Name</code> — facility name</li>
            <li><code>Billing_Start</code> — billing period start date</li>
            <li><code>Usage_kWh</code> — electricity consumed (kWh)</li>
          </ul>
          <p style={styles.helpText}><strong>Concur Travel Export</strong> — comma-delimited:</p>
          <ul style={styles.helpList}>
            <li><code>Employee_ID</code>, <code>Transaction_Date</code>, <code>Expense_Type</code></li>
            <li><code>Distance_km</code> (flights/ground) or <code>Hotel_Nights</code></li>
          </ul>
        </div>
      </div>
    </div>
  )
}

const stepBadge = (step) => {
  const colors = {
    UPLOADED:   { bg: '#fff3cd', color: '#856404' },
    PARSED:     { bg: '#cff4fc', color: '#055160' },
    NORMALIZED: { bg: '#d1e7dd', color: '#0a3622' },
  }
  const c = colors[step] || { bg: '#e2e3e5', color: '#383d41' }
  return {
    padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600,
    backgroundColor: c.bg, color: c.color
  }
}

const styles = {
  container: {
    padding: '40px 20px',
    maxWidth: '600px',
    margin: '0 auto'
  },
  card: {
    backgroundColor: 'white',
    borderRadius: '8px',
    boxShadow: '0 2px 10px rgba(0, 0, 0, 0.1)',
    padding: '40px'
  },
  title: {
    margin: '0 0 10px 0',
    fontSize: '28px',
    color: '#333'
  },
  description: {
    margin: '0 0 30px 0',
    color: '#666',
    fontSize: '14px',
    lineHeight: '1.6'
  },
  form: {
    display: 'flex',
    flexDirection: 'column',
    gap: '24px',
    marginBottom: '30px'
  },
  formGroup: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px'
  },
  label: {
    fontSize: '14px',
    fontWeight: '500',
    color: '#333'
  },
  fileInput: {
    position: 'relative',
    display: 'block'
  },
  hiddenInput: {
    display: 'none'
  },
  fileLabel: {
    display: 'block',
    padding: '16px',
    border: '2px dashed #007bff',
    borderRadius: '4px',
    textAlign: 'center',
    cursor: 'pointer',
    backgroundColor: '#f8f9ff',
    transition: 'all 0.2s'
  },
  input: {
    padding: '12px',
    fontSize: '14px',
    border: '1px solid #ddd',
    borderRadius: '4px'
  },
  errorText: {
    margin: '0',
    fontSize: '12px',
    color: '#dc3545'
  },
  fileSelectedText: {
    margin: '0',
    fontSize: '12px',
    color: '#28a745'
  },
  button: {
    padding: '12px',
    fontSize: '16px',
    fontWeight: '500',
    color: 'white',
    backgroundColor: '#007bff',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '8px'
  },
  spinner: {
    display: 'inline-block',
    width: '14px',
    height: '14px',
    border: '2px solid rgba(255, 255, 255, 0.3)',
    borderTop: '2px solid white',
    borderRadius: '50%',
    animation: 'spin 0.6s linear infinite'
  },
  alert: {
    padding: '12px',
    backgroundColor: '#f8d7da',
    border: '1px solid #f5c6cb',
    borderRadius: '4px',
    color: '#721c24',
    fontSize: '14px'
  },
  helpBox: {
    backgroundColor: '#e7f3ff',
    border: '1px solid #b3d9ff',
    borderRadius: '4px',
    padding: '16px'
  },
  helpTitle: {
    margin: '0 0 12px 0',
    fontSize: '14px',
    fontWeight: '500',
    color: '#004085'
  },
  helpText: {
    margin: '8px 0',
    fontSize: '13px',
    color: '#004085',
    lineHeight: '1.5'
  },
  helpList: {
    margin: '12px 0',
    paddingLeft: '20px',
    fontSize: '13px',
    color: '#004085'
  },
  successCard: {
    backgroundColor: '#d4edda',
    border: '1px solid #c3e6cb',
    borderRadius: '8px',
    padding: '30px',
    color: '#155724'
  },
  successTitle: {
    margin: '0 0 10px 0',
    fontSize: '24px'
  },
  successText: {
    margin: '0 0 20px 0',
    fontSize: '14px'
  },
  details: {
    backgroundColor: 'rgba(255, 255, 255, 0.7)',
    padding: '15px',
    borderRadius: '4px',
    marginBottom: '20px',
    fontSize: '14px'
  },
  actions: {
    display: 'flex',
    gap: '12px'
  },
  primaryButton: {
    flex: 1,
    padding: '12px',
    backgroundColor: '#28a745',
    color: 'white',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
    fontSize: '14px',
    fontWeight: '500'
  },
  secondaryButton: {
    flex: 1,
    padding: '12px',
    backgroundColor: '#6c757d',
    color: 'white',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
    fontSize: '14px',
    fontWeight: '500'
  },
  successBanner: {
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    backgroundColor: '#d1e7dd',
    border: '1px solid #a3cfbb',
    borderRadius: 8,
    padding: '14px 20px',
    marginBottom: 20,
    color: '#0a3622',
    fontSize: 14
  },
  successIcon: {
    fontSize: 22,
    fontWeight: 700,
    color: '#198754'
  },
  historyCard: {
    backgroundColor: 'white',
    borderRadius: 8,
    boxShadow: '0 2px 10px rgba(0,0,0,0.08)',
    overflow: 'hidden'
  },
  historyCardHeader: {
    padding: '20px 24px 16px',
    borderBottom: '1px solid #eee'
  },
  historyTitle: {
    margin: 0,
    fontSize: 18,
    fontWeight: 700,
    color: '#212529'
  },
  historySubtitle: {
    margin: '4px 0 0',
    fontSize: 13,
    color: '#6c757d'
  },
  historyTable: {
    width: '100%',
    borderCollapse: 'collapse',
    fontSize: 13
  },
  historyThead: {
    backgroundColor: '#f8f9fa'
  },
  historyTh: {
    padding: '10px 14px',
    textAlign: 'left',
    fontWeight: 600,
    color: '#495057',
    borderBottom: '2px solid #dee2e6',
    whiteSpace: 'nowrap'
  },
  historyTr: {
    borderBottom: '1px solid #eee'
  },
  historyTd: {
    padding: '10px 14px',
    color: '#333',
    whiteSpace: 'nowrap'
  },
  newBadge: {
    marginLeft: 8,
    padding: '1px 6px',
    borderRadius: 3,
    fontSize: 10,
    fontWeight: 700,
    backgroundColor: '#0d6efd',
    color: 'white',
    verticalAlign: 'middle'
  },
  historyActions: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: 12,
    padding: '16px 24px',
    borderTop: '1px solid #eee',
    backgroundColor: '#f8f9fa'
  }
}

export default UploadPage
