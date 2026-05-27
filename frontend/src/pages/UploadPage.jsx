/**
 * Chunk 3.3: Upload Page
 *
 * CSV file upload with progress tracking.
 * Validates file, uploads to backend, shows ingestion ID.
 */

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useUploadCSV, useDataSources } from '../hooks/useIngestions'
import { getErrorMessage } from '../utils/errorHandler'

function UploadPage() {
  const navigate = useNavigate()
  const { mutate: upload, isPending, error, data } = useUploadCSV()
  const { data: dsData, isLoading: dsLoading } = useDataSources()

  const [file, setFile] = useState(null)
  const [dataSourceId, setDataSourceId] = useState('')
  const [touched, setTouched] = useState({})

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

  // After successful upload, show ingestion card with option to proceed
  if (data && !isPending) {
    return (
      <div style={styles.container}>
        <div style={styles.successCard}>
          <h2 style={styles.successTitle}>✓ Upload Successful</h2>
          <p style={styles.successText}>Your CSV has been uploaded and is ready for processing.</p>

          <div style={styles.details}>
            <p><strong>Ingestion ID:</strong> {data.ingestion_id}</p>
            <p><strong>File:</strong> {data.filename}</p>
            <p><strong>Rows:</strong> {data.line_count}</p>
            <p><strong>Status:</strong> {data.status}</p>
          </div>

          <div style={styles.actions}>
            <button
              style={styles.primaryButton}
              onClick={() => navigate(`/ingest/${data.ingestion_id}`)}
            >
              Review & Parse
            </button>
            <button
              style={styles.secondaryButton}
              onClick={() => {
                setFile(null)
                setDataSourceId('')
                setTouched({})
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
    <div style={styles.container}>
      <div style={styles.card}>
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
          <h3 style={styles.helpTitle}>CSV Format Requirements</h3>
          <p style={styles.helpText}>
            Your CSV should include these columns (exact names):
          </p>
          <ul style={styles.helpList}>
            <li><code>Facility</code> - Facility/plant name</li>
            <li><code>Scope 1 Emissions</code> - Scope 1 emissions (tCO2e)</li>
            <li><code>Scope 2 Emissions</code> - Scope 2 emissions (tCO2e)</li>
            <li><code>Scope 3 Emissions</code> - Scope 3 emissions (tCO2e)</li>
            <li><code>Year</code> - Reporting year (YYYY)</li>
          </ul>
          <p style={styles.helpText}>
            Missing or invalid values will be flagged during parsing.
          </p>
        </div>
      </div>
    </div>
  )
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
    display: 'inline-block'
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
  }
}

export default UploadPage
