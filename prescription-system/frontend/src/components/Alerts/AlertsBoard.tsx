import { DataSourceTag, DemoBanner, LevelBadge, PageHeader } from '../common/ui'
import { getDemoAlerts, getDemoNotifications } from '../../mock/adapter'
import { useWorkspace } from '../../hooks/useWorkspace'

export function AlertsBoard() {
  const { lastAnalysis } = useWorkspace()
  const alerts = getDemoAlerts()
  const history = getDemoNotifications()

  return (
    <div className="page dash-page">
      <PageHeader
        eyebrow="Safety queue"
        title="Alerts and escalation"
        copy="Critical vitals, interactions, human review, missing information, and notification history. Escalation never auto-dispatches SMS."
        extra={<DataSourceTag source="demo" label="Notification MCP has no HTTP API" />}
      />
      <DemoBanner />
      {lastAnalysis && (
        <section className="panel padded">
          <p className="eyebrow">Live session</p>
          <h2>Medical Agent review flag</h2>
          <p>{lastAnalysis.prescription_id}: {lastAnalysis.status}. Human review {lastAnalysis.human_review_required ? 'required' : 'flag not returned'}.</p>
          <DataSourceTag source="live" />
        </section>
      )}
      {alerts.map((alert) => (
        <article className="panel padded alert-card" key={alert.id}>
          <div className="section-heading">
            <div>
              <p className="eyebrow">{alert.kind.replaceAll('_', ' ')}</p>
              <h2>{alert.title}</h2>
            </div>
            <div className="status-wrap">
              <LevelBadge level={alert.severity} />
              <span className="count-chip">{alert.escalation_status}</span>
            </div>
          </div>
          <p>{alert.message}</p>
          <p className="muted">Patient {alert.patient_id}</p>
          <ol className="chain">
            {alert.chain.map((link) => (
              <li key={link.stage}>
                <strong>{link.stage}</strong>
                <span>{link.actor}</span>
                <p>{link.detail}</p>
              </li>
            ))}
          </ol>
        </article>
      ))}
      <section className="panel padded">
        <p className="eyebrow">Notification MCP</p>
        <h2>Notification history</h2>
        {history.map((item) => (
          <div className="list-row" key={item.id}>
            <div>
              <strong>{item.event_type} · {item.event_id}</strong>
              <p>{item.message}</p>
            </div>
            <span className="count-chip">{item.status}</span>
          </div>
        ))}
      </section>
    </div>
  )
}
