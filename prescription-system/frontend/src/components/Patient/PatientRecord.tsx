import { DataSourceTag, DemoBanner, PageHeader, valueOrUnavailable } from '../common/ui'
import { useWorkspace } from '../../hooks/useWorkspace'
import { getDemoVitals } from '../../mock/adapter'

export function PatientRecord() {
  const { patient } = useWorkspace()
  const vitals = getDemoVitals(patient.patient_id)

  return (
    <div className="page dash-page">
      <PageHeader
        eyebrow="EHR Agent"
        title={`${patient.name}`}
        copy="Profile assembled from the EHR seed catalog (ehr-mcp/seed_data.py). The frontend does not open SQLite or MongoDB."
        extra={<DataSourceTag source="demo" label="EHR MCP has no HTTP API" />}
      />
      <DemoBanner />
      <section className="panel padded">
        <div className="section-heading"><div><p className="eyebrow">Identity</p><h2>Patient profile</h2></div><span className="id-chip">{patient.patient_id}</span></div>
        <div className="detail-grid">
          <div><span className="field-label">Name</span><strong>{patient.name}</strong></div>
          <div><span className="field-label">Age</span><strong>{patient.age}</strong></div>
          <div><span className="field-label">Gender</span><strong>{patient.gender}</strong></div>
          <div><span className="field-label">Emergency contact</span><strong>{patient.emergency_contact.name} ({patient.emergency_contact.relation})</strong></div>
          <div><span className="field-label">Phone</span><strong>{patient.emergency_contact.phone}</strong></div>
          <div><span className="field-label">EHR retrieval</span><strong>{patient.ehr_retrieval.status}</strong></div>
        </div>
        <p className="muted">{patient.ehr_retrieval.note} Last query {patient.ehr_retrieval.last_query}. Latency {valueOrUnavailable(patient.ehr_retrieval.latency_ms)} ms (demo).</p>
      </section>
      <div className="split-grid">
        <section className="panel padded">
          <p className="eyebrow">Problem list</p>
          <h2>Conditions</h2>
          {patient.conditions.length ? patient.conditions.map((item) => (
            <div className="list-row" key={item.name}><div><strong>{item.name}</strong><p>Onset {valueOrUnavailable(item.onset)} · {item.status}</p></div></div>
          )) : <p className="empty-state">No conditions in seed data.</p>}
        </section>
        <section className="panel padded">
          <p className="eyebrow">Safety</p>
          <h2>Allergies</h2>
          {patient.allergies.length ? patient.allergies.map((item) => (
            <div className="list-row" key={item.name}><div><strong>{item.name}</strong><p>Severity {item.severity}</p></div></div>
          )) : <p className="empty-state">No allergies documented.</p>}
        </section>
      </div>
      <section className="panel padded">
        <p className="eyebrow">Therapy</p>
        <h2>Medications</h2>
        <div className="medication-list">
          {patient.medications.length ? patient.medications.map((rx) => (
            <article className="medication-card ehr-med" key={rx.drug}>
              <div className="medication-name"><span className="medication-index">Rx</span><strong>{rx.drug}</strong></div>
              <div><span className="field-label">Dosage</span><span>{rx.dosage}</span></div>
              <div><span className="field-label">Frequency</span><span>{rx.frequency}</span></div>
              <div><span className="field-label">Started</span><span>{valueOrUnavailable(rx.prescribed_date)}</span></div>
              <div><span className="field-label">Active</span><span>{rx.active ? 'Yes' : 'No'}</span></div>
            </article>
          )) : <p className="empty-state">No active prescriptions in seed data.</p>}
        </div>
      </section>
      <div className="split-grid">
        <section className="panel padded">
          <p className="eyebrow">Telemetry</p>
          <h2>Recent vitals</h2>
          {vitals.map((vital) => (
            <div className="list-row" key={vital.id}>
              <div><strong>{vital.label}</strong><p>{vital.value} {vital.unit} · ref {vital.reference}</p></div>
              <span className={`level-badge level-${vital.level.toLowerCase()}`}>{vital.level}</span>
            </div>
          ))}
        </section>
        <section className="panel padded">
          <p className="eyebrow">History</p>
          <h2>Timeline</h2>
          <ol className="mini-timeline">
            {patient.medical_history.map((event) => (
              <li key={event.at}><strong>{event.title}</strong><span>{event.at} — {event.detail}</span></li>
            ))}
          </ol>
        </section>
      </div>
    </div>
  )
}
