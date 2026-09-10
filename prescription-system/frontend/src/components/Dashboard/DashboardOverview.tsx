import { Activity, Bell, Brain, HeartPulse, Pill, Workflow } from 'lucide-react'
import { Link } from 'react-router-dom'
import { StatusBadge } from '../Prescription/PrescriptionWorkspace'
import { DataSourceTag, DemoBanner, LevelBadge, PageHeader, valueOrUnavailable } from '../common/ui'
import { useWorkspace } from '../../hooks/useWorkspace'
import { getDemoAlerts, getDemoNotifications, getDemoOrchestration, getDemoVitals } from '../../mock/adapter'

export function DashboardOverview() {
  const { patient, lastExtraction, lastAnalysis, backend } = useWorkspace()
  const vitals = getDemoVitals(patient.patient_id)
  const alerts = getDemoAlerts(patient.patient_id)
  const notes = getDemoNotifications(patient.patient_id)
  const orchestration = getDemoOrchestration()
  const healthLevel = vitals.some((item) => item.level === 'CRITICAL') ? 'CRITICAL' : vitals.some((item) => item.level === 'WARNING') ? 'WARNING' : 'NORMAL'

  return (
    <div className="page dash-page">
      <PageHeader
        eyebrow="Clinical command center"
        title="HealthEase dashboard"
        copy="Patient context, vitals, prescriptions, and agent activity in one view. Central reasoning stays with the orchestrator."
        extra={<DataSourceTag source="demo" label="EHR / vitals / alerts" />}
      />
      <DemoBanner />
      <div className="stat-grid">
        <article className="panel stat-card">
          <p className="eyebrow">Patient</p>
          <h2>{patient.name}</h2>
          <p className="muted">{patient.patient_id} · {patient.age} · {patient.gender}</p>
          <p>{patient.conditions.map((item) => item.name).join(', ') || 'No documented conditions'}</p>
        </article>
        <article className="panel stat-card">
          <p className="eyebrow">Current health status</p>
          <h2><LevelBadge level={healthLevel} /></h2>
          <p className="muted">Derived from demo wearable thresholds used by orchestrator.detect_anomalies.</p>
        </article>
        <article className="panel stat-card">
          <p className="eyebrow">Prescription API</p>
          <h2>{backend.status === 'ok' ? 'Connected' : backend.status === 'down' ? 'Offline' : 'Checking'}</h2>
          <p className="muted">{backend.message}</p>
        </article>
        <article className="panel stat-card">
          <p className="eyebrow">Orchestrator</p>
          <h2>{orchestration.risk_level}</h2>
          <p className="muted">{orchestration.status} · approved={String(orchestration.approved)}</p>
        </article>
      </div>
      <div className="split-grid">
        <section className="panel padded">
          <div className="section-heading">
            <div><p className="eyebrow">Attention</p><h2>Active alerts</h2></div>
            <Link to="/alerts" className="text-link">Open queue</Link>
          </div>
          {alerts.length ? alerts.map((alert) => (
            <div className="list-row" key={alert.id}>
              <Bell size={16} />
              <div>
                <strong>{alert.title}</strong>
                <p>{alert.message}</p>
              </div>
              <LevelBadge level={alert.severity} />
            </div>
          )) : <p className="empty-state">No demo alerts for this patient.</p>}
        </section>
        <section className="panel padded">
          <div className="section-heading">
            <div><p className="eyebrow">Intake</p><h2>Recent prescriptions</h2></div>
            <Link to="/prescription" className="text-link">Analyze</Link>
          </div>
          {lastExtraction ? (
            <div className="list-row">
              <Pill size={16} />
              <div>
                <strong>{lastExtraction.prescription_id}</strong>
                <p>{valueOrUnavailable(lastExtraction.prescription.condition)} · {lastExtraction.prescription.medications.map((item) => item.name).join(', ') || 'No medications'}</p>
              </div>
              <DataSourceTag source="live" />
            </div>
          ) : null}
          {patient.medications.map((rx) => (
            <div className="list-row" key={`${rx.drug}-${rx.prescribed_date}`}>
              <Pill size={16} />
              <div>
                <strong>{rx.drug}</strong>
                <p>{rx.dosage} · {rx.frequency}</p>
              </div>
              <DataSourceTag source="demo" />
            </div>
          ))}
          {lastAnalysis && (
            <div className="list-row">
              <StatusBadge status={lastAnalysis.status} />
              <div>
                <strong>Last Medical Agent result</strong>
                <p>Human review {lastAnalysis.human_review_required ? 'required' : 'flag not returned'}</p>
              </div>
            </div>
          )}
        </section>
      </div>
      <div className="split-grid">
        <section className="panel padded">
          <div className="section-heading">
            <div><p className="eyebrow">Telemetry</p><h2>Recent vitals</h2></div>
            <Link to="/vitals" className="text-link">Live view</Link>
          </div>
          <div className="vital-mini-grid">
            {vitals.map((vital) => (
              <div key={vital.id} className="vital-mini">
                <HeartPulse size={14} />
                <span>{vital.label}</span>
                <strong>{vital.value} {vital.unit}</strong>
                <LevelBadge level={vital.level} />
              </div>
            ))}
          </div>
        </section>
        <section className="panel padded">
          <div className="section-heading">
            <div><p className="eyebrow">Multi-agent</p><h2>Agent status</h2></div>
            <Link to="/agents" className="text-link">Monitor</Link>
          </div>
          <div className="agent-pills">
            <span><Workflow size={14} /> Orchestrator · demo</span>
            <span><Brain size={14} /> Medical Agent · {lastAnalysis ? 'session live' : 'awaiting analyze'}</span>
            <span><Activity size={14} /> EHR Agent · demo</span>
            <span><Bell size={14} /> Notification Agent · demo</span>
          </div>
        </section>
      </div>
      <div className="split-grid">
        <section className="panel padded">
          <div className="section-heading">
            <div><p className="eyebrow">Reasoning</p><h2>Orchestration activity</h2></div>
            <Link to="/orchestrator" className="text-link">Timeline</Link>
          </div>
          <ol className="mini-timeline">
            {orchestration.steps.slice(0, 5).map((step) => (
              <li key={step.id}><strong>{step.title}</strong><span>{step.actor}</span></li>
            ))}
          </ol>
        </section>
        <section className="panel padded">
          <div className="section-heading">
            <div><p className="eyebrow">Notification MCP</p><h2>Recent notifications</h2></div>
            <Link to="/alerts" className="text-link">Escalations</Link>
          </div>
          {notes.map((note) => (
            <div className="list-row" key={note.id}>
              <div>
                <strong>{note.event_type}</strong>
                <p>{note.message}</p>
              </div>
              <span className="count-chip">{note.status}</span>
            </div>
          ))}
        </section>
      </div>
    </div>
  )
}
