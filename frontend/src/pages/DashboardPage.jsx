import { useState } from 'react'
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell
} from 'recharts'
import { useEmissionsSummary } from '../hooks/useEmissions'

function DashboardPage() {
  const [filters, setFilters] = useState({
    year: 'all',
    facility: 'all',
    scope: 'all'
  })

  const { data: summary, isLoading } = useEmissionsSummary(filters)

  if (isLoading) {
    return <div style={styles.container}>Loading dashboard...</div>
  }

  if (!summary) {
    return <div style={styles.container}>No data available</div>
  }

  const scopeColors = {
    scope_1: '#FF6B6B',
    scope_2: '#4ECDC4',
    scope_3: '#45B7D1'
  }

  const qualityColors = {
    excellent: '#28a745',
    good: '#ffc107',
    poor: '#dc3545'
  }

  return (
    <div className="page-container">
      {/* Header */}
      <div style={styles.header}>
        <h1>Emissions Dashboard</h1>
        <p style={styles.subtitle}>Approved emissions data analysis and visualization</p>
      </div>

      {/* Filters */}
      <div className="dashboard-filters">
        <div className="filter-group">
          <label>Year:</label>
          <select
            value={filters.year}
            onChange={(e) => setFilters({ ...filters, year: e.target.value })}
          >
            <option value="all">All Years</option>
            {summary.available_years?.map(year => (
              <option key={year} value={year}>{year}</option>
            ))}
          </select>
        </div>

        <div className="filter-group">
          <label>Facility:</label>
          <select
            value={filters.facility}
            onChange={(e) => setFilters({ ...filters, facility: e.target.value })}
          >
            <option value="all">All Facilities</option>
            {summary.available_facilities?.map(facility => (
              <option key={facility} value={facility}>{facility}</option>
            ))}
          </select>
        </div>

        <div className="filter-group">
          <label>Scope:</label>
          <select
            value={filters.scope}
            onChange={(e) => setFilters({ ...filters, scope: e.target.value })}
          >
            <option value="all">All Scopes</option>
            <option value="scope_1">Scope 1 (Direct)</option>
            <option value="scope_2">Scope 2 (Indirect Energy)</option>
            <option value="scope_3">Scope 3 (Other Indirect)</option>
          </select>
        </div>
      </div>

      {/* Summary Metrics */}
      <div className="metrics-grid">
        <div style={styles.metricCard}>
          <div style={styles.metricLabel}>Total Emissions</div>
          <div style={styles.metricValue}>{summary.total_emissions?.toFixed(0) || 0}</div>
          <div style={styles.metricUnit}>metric tons CO2e</div>
        </div>

        <div style={styles.metricCard}>
          <div style={styles.metricLabel}>Active Facilities</div>
          <div style={styles.metricValue}>{summary.facility_count || 0}</div>
          <div style={styles.metricUnit}>facilities</div>
        </div>

        <div style={styles.metricCard}>
          <div style={styles.metricLabel}>Approved Records</div>
          <div style={styles.metricValue}>{summary.record_count || 0}</div>
          <div style={styles.metricUnit}>records</div>
        </div>

        <div style={styles.metricCard}>
          <div style={styles.metricLabel}>Data Quality Score</div>
          <div style={styles.metricValue}>{summary.average_quality_score?.toFixed(1) || 0}</div>
          <div style={styles.metricUnit}>/ 100</div>
        </div>
      </div>

      {/* Charts Grid */}
      <div className="charts-grid">
        {/* Emissions by Scope - Bar Chart */}
        {summary.by_scope && (
          <div style={styles.chartBox}>
            <h3>Emissions by Scope</h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={summary.by_scope}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="scope" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="value" fill="#007bff" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Emissions by Year - Line Chart */}
        {summary.by_year && (
          <div style={styles.chartBox}>
            <h3>Emissions Trend (By Year)</h3>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={summary.by_year}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="year" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="scope_1" stroke={scopeColors.scope_1} />
                <Line type="monotone" dataKey="scope_2" stroke={scopeColors.scope_2} />
                <Line type="monotone" dataKey="scope_3" stroke={scopeColors.scope_3} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Data Quality Distribution - Pie Chart */}
        {summary.quality_distribution && (
          <div style={styles.chartBox}>
            <h3>Records by Quality Tier</h3>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={summary.quality_distribution}
                  dataKey="count"
                  nameKey="tier"
                  cx="50%"
                  cy="50%"
                  outerRadius={80}
                  label
                >
                  <Cell fill={qualityColors.excellent} />
                  <Cell fill={qualityColors.good} />
                  <Cell fill={qualityColors.poor} />
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Data Completeness */}
        {summary.data_completeness && (
          <div style={styles.chartBox}>
            <h3>Data Completeness</h3>
            <div style={styles.gaugeContainer}>
              <div style={styles.gaugeValue}>
                {summary.data_completeness}%
              </div>
              <div style={styles.gaugeBar}>
                <div
                  style={{
                    ...styles.gaugeFill,
                    width: `${summary.data_completeness}%`,
                    backgroundColor: summary.data_completeness >= 80 ? '#28a745' : '#ffc107'
                  }}
                ></div>
              </div>
              <p style={styles.gaugeLabel}>
                {summary.data_completeness >= 80 ? 'Excellent' : 'Good'} coverage of required fields
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Approved Records Table */}
      {summary.approved_records && summary.approved_records.length > 0 && (
        <div style={styles.tableSection}>
          <h2>Approved Records</h2>
          <div className="table-scroll">
            <table style={styles.table}>
              <thead>
                <tr>
                  <th>Facility</th>
                  <th>Year</th>
                  <th>Scope 1</th>
                  <th>Scope 2</th>
                  <th>Scope 3</th>
                  <th>Quality</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {summary.approved_records.map((record) => (
                  <tr key={record.id}>
                    <td>{record.facility_name}</td>
                    <td>{record.reporting_year}</td>
                    <td>{record.scope_1_emissions?.toFixed(1) || '-'}</td>
                    <td>{record.scope_2_emissions?.toFixed(1) || '-'}</td>
                    <td>{record.scope_3_emissions?.toFixed(1) || '-'}</td>
                    <td>
                      <span style={getQualityBadgeStyle(record.data_quality_score)}>
                        {record.data_quality_score}
                      </span>
                    </td>
                    <td>{record.review_status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
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
    maxWidth: '1400px',
    margin: '0 auto',
    backgroundColor: '#f9f9f9',
    minHeight: '100vh'
  },
  header: {
    marginBottom: '30px',
    borderBottom: '1px solid #ddd',
    paddingBottom: '20px'
  },
  subtitle: {
    margin: '10px 0 0 0',
    color: '#666',
    fontSize: '16px'
  },
  filtersBox: {
    backgroundColor: 'white',
    padding: '20px',
    borderRadius: '8px',
    marginBottom: '30px',
    display: 'flex',
    gap: '20px',
    flexWrap: 'wrap',
    boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
  },
  filterGroup: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px'
  },
  select: {
    padding: '8px 12px',
    border: '1px solid #ddd',
    borderRadius: '4px',
    fontSize: '14px',
    cursor: 'pointer',
    minWidth: '150px'
  },
  metricsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
    gap: '15px',
    marginBottom: '30px'
  },
  metricCard: {
    backgroundColor: 'white',
    padding: '20px',
    borderRadius: '8px',
    boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
    textAlign: 'center'
  },
  metricLabel: {
    fontSize: '14px',
    color: '#666',
    marginBottom: '10px'
  },
  metricValue: {
    fontSize: '32px',
    fontWeight: 'bold',
    color: '#333',
    margin: '10px 0'
  },
  metricUnit: {
    fontSize: '12px',
    color: '#999'
  },
  chartsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))',
    gap: '20px',
    marginBottom: '30px'
  },
  chartBox: {
    backgroundColor: 'white',
    padding: '20px',
    borderRadius: '8px',
    boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
  },
  gaugeContainer: {
    padding: '20px',
    textAlign: 'center'
  },
  gaugeValue: {
    fontSize: '40px',
    fontWeight: 'bold',
    color: '#333',
    marginBottom: '15px'
  },
  gaugeBar: {
    height: '30px',
    backgroundColor: '#e9ecef',
    borderRadius: '15px',
    overflow: 'hidden',
    marginBottom: '10px'
  },
  gaugeFill: {
    height: '100%',
    transition: 'width 0.3s'
  },
  gaugeLabel: {
    fontSize: '13px',
    color: '#666',
    margin: 0
  },
  tableSection: {
    backgroundColor: 'white',
    padding: '20px',
    borderRadius: '8px',
    boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
  },
  tableWrapper: {
    overflowX: 'auto',
    marginTop: '15px'
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse'
  }
}

export default DashboardPage
