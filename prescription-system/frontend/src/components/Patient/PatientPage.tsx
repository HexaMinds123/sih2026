import { useState } from 'react'
import { Pill, AlertTriangle, Heart, Clock, ChevronDown, ChevronUp } from 'lucide-react'
import { MOCK_PATIENTS, ACTIVE_PATIENT } from '../../mock/patients'
import { MOCK_VITALS_HISTORY, getVitalStatus } from '../../mock/vitals'
import { DemoBadge, VitalBadge } from '../common/Badges'

export function PatientPage() {
  const [patientId, setPatientId] = useState(ACTIVE_PATIENT.patient_id)
  const [historyOpen, setHistoryOpen] = useState(false)
  const patient = MOCK_PATIENTS.find(p => p.patient_id === patientId) ?? ACTIVE_PATIENT

  return (
    <div className="page-content">
      <div className="page-header">
        <div>
          <p className="eyebrow">EHR Access</p>
          <h1 className="page-title">Patient / EHR</h1>
        </div>
        <DemoBadge />
      </div>

      <p className="page-note">
        <AlertTriangle size={13} /> Patient data is retrieved from the EHR-MCP server by the Orchestrator. This view shows mock seed data (P001–P003) for demonstration. Real-time EHR queries require the orchestrator endpoint.
      </p>

      {/* Patient selector */}
      <div className="patient-selector">
        {MOCK_PATIENTS.map(p => (
          <button
            key={p.patient_id}
            className={`patient-tab ${patientId === p.patient_id ? 'active' : ''}`}
            onClick={() => setPatientId(p.patient_id)}
          >
            <span className="patient-tab-id">{p.patient_id}</span>
            <span>{p.name}</span>
          </button>
        ))}
      </div>

      <div className="patient-grid">
        {/* Profile card */}
        <div className="panel patient-profile-card">
          <div className="patient-avatar-lg">{patient.name.split(' ').map(n => n[0]).join('')}</div>
          <div className="patient-profile-info">
            <h2>{patient.name}</h2>
            <p className="muted">{patient.patient_id}</p>
            <div className="profile-meta">
              <ProfileField label="Age" value={`${patient.age} years`} />
              <ProfileField label="Gender" value={patient.gender} />
              <ProfileField label="Blood Type" value={patient.bloodType ?? 'Not recorded'} />
            </div>
          </div>
          {patient.emergencyContact && (
            <div className="emergency-contact">
              <p className="field-label">Emergency Contact</p>
              <strong>{patient.emergencyContact.name}</strong>
              <p>{patient.emergencyContact.relation} · {patient.emergencyContact.phone}</p>
            </div>
          )}
        </div>

        {/* Conditions */}
        <div className="panel info-card">
          <div className="info-card-header"><Pill size={16} /><h3>Conditions</h3></div>
          <div className="tag-list">
            {patient.conditions.map(c => <span key={c} className="condition-tag">{c}</span>)}
          </div>
        </div>

        {/* Allergies */}
        <div className="panel info-card">
          <div className="info-card-header"><AlertTriangle size={16} /><h3>Allergies</h3></div>
          <div className="tag-list">
            {patient.allergies.length
              ? patient.allergies.map(a => <span key={a} className="allergy-tag">{a}</span>)
              : <span className="muted">No documented allergies</span>}
          </div>
        </div>

        {/* Current vitals */}
        <div className="panel info-card span-2">
          <div className="info-card-header">
            <Heart size={16} />
            <h3>Latest Vitals</h3>
            <span className="muted" style={{ marginLeft: 'auto', fontSize: 11 }}>
              {new Date(MOCK_VITALS_HISTORY[MOCK_VITALS_HISTORY.length - 1].timestamp).toLocaleString()}
            </span>
          </div>
          <div className="vitals-grid">
            {[
              { label: 'Heart Rate', param: 'heart_rate', value: MOCK_VITALS_HISTORY[MOCK_VITALS_HISTORY.length - 1].heart_rate, unit: 'bpm' },
              { label: 'SpO₂', param: 'spo2', value: MOCK_VITALS_HISTORY[MOCK_VITALS_HISTORY.length - 1].spo2, unit: '%' },
              { label: 'Systolic BP', param: 'systolic_bp', value: MOCK_VITALS_HISTORY[MOCK_VITALS_HISTORY.length - 1].systolic_bp, unit: 'mmHg' },
              { label: 'Diastolic BP', param: 'diastolic_bp', value: MOCK_VITALS_HISTORY[MOCK_VITALS_HISTORY.length - 1].diastolic_bp, unit: 'mmHg' },
              { label: 'Temperature', param: 'temperature', value: MOCK_VITALS_HISTORY[MOCK_VITALS_HISTORY.length - 1].temperature, unit: '°C' },
              { label: 'Glucose', param: 'glucose', value: MOCK_VITALS_HISTORY[MOCK_VITALS_HISTORY.length - 1].glucose, unit: 'mg/dL' },
            ].map(v => (
              <div key={v.label} className="vital-detail-card">
                <span className="field-label">{v.label}</span>
                <strong>{v.value} <span className="vital-unit">{v.unit}</span></strong>
                <VitalBadge status={getVitalStatus(v.param, v.value)} />
              </div>
            ))}
          </div>
        </div>

        {/* History accordion */}
        <div className="panel span-full">
          <button className="audit-toggle" onClick={() => setHistoryOpen(o => !o)}>
            <span>
              <p className="eyebrow">Historical record</p>
              <strong style={{ fontFamily: "'Space Grotesk',sans-serif", fontSize: 17 }}>Vitals History</strong>
            </span>
            {historyOpen ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
          </button>
          {historyOpen && (
            <div className="vitals-table-wrap">
              <table className="vitals-table">
                <thead>
                  <tr>
                    <th><Clock size={12} /> Time</th>
                    <th>HR (bpm)</th><th>SpO₂ (%)</th>
                    <th>Systolic</th><th>Diastolic</th>
                    <th>Temp (°C)</th><th>Glucose</th>
                  </tr>
                </thead>
                <tbody>
                  {[...MOCK_VITALS_HISTORY].reverse().map(v => (
                    <tr key={v.timestamp}>
                      <td>{new Date(v.timestamp).toLocaleTimeString()}</td>
                      <td className={`vt-${getVitalStatus('heart_rate', v.heart_rate).toLowerCase()}`}>{v.heart_rate}</td>
                      <td className={`vt-${getVitalStatus('spo2', v.spo2).toLowerCase()}`}>{v.spo2}</td>
                      <td className={`vt-${getVitalStatus('systolic_bp', v.systolic_bp).toLowerCase()}`}>{v.systolic_bp}</td>
                      <td className={`vt-${getVitalStatus('diastolic_bp', v.diastolic_bp).toLowerCase()}`}>{v.diastolic_bp}</td>
                      <td className={`vt-${getVitalStatus('temperature', v.temperature).toLowerCase()}`}>{v.temperature}</td>
                      <td className={`vt-${getVitalStatus('glucose', v.glucose).toLowerCase()}`}>{v.glucose}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function ProfileField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span className="field-label">{label}</span>
      <strong>{value}</strong>
    </div>
  )
}
