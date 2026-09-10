import { HeartPulse } from 'lucide-react'
import { DataSourceTag, DemoBanner, LevelBadge, PageHeader } from '../common/ui'
import { useWorkspace } from '../../hooks/useWorkspace'
import { getDemoVitals } from '../../mock/adapter'

export function VitalsBoard() {
  const { patient } = useWorkspace()
  const vitals = getDemoVitals(patient.patient_id)

  return (
    <div className="page dash-page">
      <PageHeader
        eyebrow="Wearable stream"
        title="Live vitals"
        copy="Heart rate, SpO2, blood pressure, temperature, glucose, and activity with NORMAL / WARNING / CRITICAL bands matching orchestrator anomaly thresholds where applicable."
        extra={<DataSourceTag source="demo" label="No vitals REST API" />}
      />
      <DemoBanner />
      <p className="muted">Patient {patient.patient_id}. P001 values follow orchestrator.run_demo() (HR 128, SpO2 87).</p>
      <div className="vital-grid">
        {vitals.map((vital) => (
          <article className={`panel vital-card level-border-${vital.level.toLowerCase()}`} key={vital.id}>
            <div className="vital-head">
              <HeartPulse size={18} />
              <LevelBadge level={vital.level} />
            </div>
            <p className="eyebrow">{vital.label}</p>
            <h2>{vital.value} <small>{vital.unit}</small></h2>
            <p className="muted">Reference {vital.reference}</p>
            <p className="field-label">Updated {vital.updated_at}</p>
          </article>
        ))}
      </div>
    </div>
  )
}
