import { useState } from 'react'
import { Heart, Activity, Thermometer, Droplet, Clock, Zap } from 'lucide-react'
import { MOCK_VITALS_HISTORY, CURRENT_VITALS, getVitalStatus } from '../../mock/vitals'
import { ACTIVE_PATIENT } from '../../mock/patients'
import { DemoBadge, VitalBadge } from '../common/Badges'

export function VitalsPage() {
  const [selectedParam, setSelectedParam] = useState<string>('all')

  const vitalsList = [
    {
      id: 'heart_rate',
      label: 'Heart Rate',
      value: CURRENT_VITALS.heart_rate,
      unit: 'bpm',
      normalRange: '60 - 100 bpm',
      status: getVitalStatus('heart_rate', CURRENT_VITALS.heart_rate),
      icon: <Heart size={20} className="vital-icon-hr" />,
      desc: 'Normal resting sinus rhythm with slight elevation during evening readings.',
    },
    {
      id: 'spo2',
      label: 'Oxygen Saturation (SpO₂)',
      value: CURRENT_VITALS.spo2,
      unit: '%',
      normalRange: '95 - 100%',
      status: getVitalStatus('spo2', CURRENT_VITALS.spo2),
      icon: <Activity size={20} className="vital-icon-spo2" />,
      desc: 'Adequate peripheral capillary oxygen saturation. Monitored for pulmonary stability.',
    },
    {
      id: 'systolic_bp',
      label: 'Blood Pressure',
      value: `${CURRENT_VITALS.systolic_bp}/${CURRENT_VITALS.diastolic_bp}`,
      unit: 'mmHg',
      normalRange: '< 120/80 mmHg',
      status: getVitalStatus('systolic_bp', CURRENT_VITALS.systolic_bp),
      icon: <Zap size={20} className="vital-icon-bp" />,
      desc: 'Stage 1 Hypertension threshold detected. Correlated with documented EHR condition.',
    },
    {
      id: 'temperature',
      label: 'Body Temperature',
      value: CURRENT_VITALS.temperature,
      unit: '°C',
      normalRange: '36.5 - 37.5 °C',
      status: getVitalStatus('temperature', CURRENT_VITALS.temperature),
      icon: <Thermometer size={20} className="vital-icon-temp" />,
      desc: 'Afebrile core temperature reading across all monitored time windows.',
    },
    {
      id: 'glucose',
      label: 'Blood Glucose',
      value: CURRENT_VITALS.glucose,
      unit: 'mg/dL',
      normalRange: '70 - 140 mg/dL',
      status: getVitalStatus('glucose', CURRENT_VITALS.glucose),
      icon: <Droplet size={20} className="vital-icon-glucose" />,
      desc: 'Postprandial peak observed at 10:00. Monitored under Type 2 Diabetes protocol.',
    },
  ]

  const filteredHistory = [...MOCK_VITALS_HISTORY].reverse()

  return (
    <div className="page-content">
      <div className="page-header">
        <div>
          <p className="eyebrow">Real-Time Telemetry Stream</p>
          <h1 className="page-title">Live Vitals Monitoring</h1>
        </div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <span className="live-indicator"><span className="pulse-live" /> LIVE FEED</span>
          <DemoBadge />
        </div>
      </div>

      <div className="patient-banner-compact panel">
        <div className="patient-avatar-sm">{ACTIVE_PATIENT.name.split(' ').map(n => n[0]).join('')}</div>
        <div>
          <strong>{ACTIVE_PATIENT.name}</strong> ({ACTIVE_PATIENT.patient_id})
          <span className="muted" style={{ marginLeft: 8 }}>{ACTIVE_PATIENT.age}y · {ACTIVE_PATIENT.gender}</span>
        </div>
        <div style={{ marginLeft: 'auto' }}>
          <span className="status-badge status-informational" style={{ padding: '4px 8px', fontSize: '11px' }}>
            Telemetry Node Active (P001)
          </span>
        </div>
      </div>

      <div className="vitals-cards-grid">
        {vitalsList.map((v) => (
          <div key={v.id} className={`panel vital-card-large vital-card-${v.status.toLowerCase()}`}>
            <div className="vital-card-top">
              <div className="vital-card-icon-wrap">{v.icon}</div>
              <VitalBadge status={v.status} />
            </div>
            <div className="vital-card-middle">
              <span className="field-label">{v.label}</span>
              <div className="vital-big-number">
                {v.value} <span className="vital-unit-sub">{v.unit}</span>
              </div>
            </div>
            <div className="vital-card-bottom">
              <span className="vital-range">Normal: {v.normalRange}</span>
              <p className="vital-desc-note">{v.desc}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="panel vitals-history-panel" style={{ marginTop: '24px' }}>
        <div className="section-heading">
          <div>
            <p className="eyebrow">Historical Trend</p>
            <h2>Telemetry Stream Log</h2>
          </div>
          <div className="table-filter-chips">
            <button
              className={`chip-btn ${selectedParam === 'all' ? 'active' : ''}`}
              onClick={() => setSelectedParam('all')}
            >
              All Readings
            </button>
            <button
              className={`chip-btn ${selectedParam === 'critical' ? 'active' : ''}`}
              onClick={() => setSelectedParam('critical')}
            >
              Alerts Only
            </button>
          </div>
        </div>

        <div className="vitals-table-wrap">
          <table className="vitals-table">
            <thead>
              <tr>
                <th><Clock size={13} style={{ verticalAlign: 'middle', marginRight: 4 }} /> Timestamp</th>
                <th>Heart Rate</th>
                <th>SpO₂</th>
                <th>Blood Pressure</th>
                <th>Temperature</th>
                <th>Glucose</th>
                <th>Risk State</th>
              </tr>
            </thead>
            <tbody>
              {filteredHistory
                .filter(row => {
                  if (selectedParam === 'critical') {
                    return (
                      getVitalStatus('heart_rate', row.heart_rate) !== 'NORMAL' ||
                      getVitalStatus('spo2', row.spo2) !== 'NORMAL' ||
                      getVitalStatus('systolic_bp', row.systolic_bp) !== 'NORMAL' ||
                      getVitalStatus('glucose', row.glucose) !== 'NORMAL'
                    )
                  }
                  return true
                })
                .map((row) => {
                  const hrStatus = getVitalStatus('heart_rate', row.heart_rate)
                  const spo2Status = getVitalStatus('spo2', row.spo2)
                  const bpStatus = getVitalStatus('systolic_bp', row.systolic_bp)
                  const glucStatus = getVitalStatus('glucose', row.glucose)
                  const hasWarning = [hrStatus, spo2Status, bpStatus, glucStatus].includes('WARNING')
                  const hasCritical = [hrStatus, spo2Status, bpStatus, glucStatus].includes('CRITICAL')
                  const rowOverall = hasCritical ? 'CRITICAL' : hasWarning ? 'WARNING' : 'NORMAL'

                  return (
                    <tr key={row.timestamp} className={`vrow-${rowOverall.toLowerCase()}`}>
                      <td>{new Date(row.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</td>
                      <td>
                        <strong>{row.heart_rate}</strong> <span className="muted">bpm</span>
                      </td>
                      <td>
                        <strong>{row.spo2}%</strong>
                      </td>
                      <td>
                        <strong>{row.systolic_bp}/{row.diastolic_bp}</strong> <span className="muted">mmHg</span>
                      </td>
                      <td>
                        <strong>{row.temperature}°C</strong>
                      </td>
                      <td>
                        <strong>{row.glucose}</strong> <span className="muted">mg/dL</span>
                      </td>
                      <td>
                        <VitalBadge status={rowOverall} />
                      </td>
                    </tr>
                  )
                })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
