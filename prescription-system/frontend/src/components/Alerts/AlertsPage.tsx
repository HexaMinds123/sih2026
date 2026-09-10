import { useState } from 'react'
import { CheckCircle, Clock, UserCheck, XCircle, ArrowRight } from 'lucide-react'
import { MOCK_ALERTS } from '../../mock/alerts'
import { SeverityBadge, DemoBadge } from '../common/Badges'
import { EscalationChain } from '../common/Timeline'
import type { Alert, AlertSeverity } from '../../types/index'

export function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>(MOCK_ALERTS)
  const [selectedFilter, setSelectedFilter] = useState<'ALL' | AlertSeverity>('ALL')
  const [activeAlertId, setActiveAlertId] = useState<string | null>(MOCK_ALERTS[0]?.id ?? null)

  const handleDecision = (id: string, decision: 'CONFIRMED' | 'REJECTED') => {
    setAlerts(prev =>
      prev.map(a => {
        if (a.id === id) {
          const updatedChain = a.escalation_chain.map(step => {
            if (step.actor.includes('Dr.') || step.step.includes('decision')) {
              return { ...step, status: 'done' as const, timestamp: new Date().toLocaleTimeString() }
            }
            if (step.step.includes('SMS') && decision === 'CONFIRMED') {
              return { ...step, status: 'done' as const, timestamp: new Date().toLocaleTimeString() }
            }
            if (step.step.includes('SMS') && decision === 'REJECTED') {
              return { ...step, status: 'skipped' as const, timestamp: 'Declined' }
            }
            return step
          })
          return {
            ...a,
            status: decision,
            escalation_chain: updatedChain,
          }
        }
        return a
      })
    )
  }

  const filteredAlerts = alerts.filter(a => selectedFilter === 'ALL' || a.severity === selectedFilter)
  const activeAlert = alerts.find(a => a.id === activeAlertId) || alerts[0]

  return (
    <div className="page-content">
      <div className="page-header">
        <div>
          <p className="eyebrow">Clinical Escalations & Notifications</p>
          <h1 className="page-title">Alerts & Escalation Protocol</h1>
        </div>
        <DemoBadge />
      </div>

      <div className="escalation-banner panel">
        <div className="chain-diagram-horizontal">
          <span className="chain-pill">1. EVENT</span>
          <ArrowRight size={14} className="chain-arr" />
          <span className="chain-pill">2. AGENT EVALUATION</span>
          <ArrowRight size={14} className="chain-arr" />
          <span className="chain-pill">3. ORCHESTRATOR RISK SYNTHESIS</span>
          <ArrowRight size={14} className="chain-arr" />
          <span className="chain-pill chain-gate">4. HUMAN DECISION GATE</span>
          <ArrowRight size={14} className="chain-arr" />
          <span className="chain-pill">5. NOTIFICATION DISPATCH</span>
        </div>
        <p className="escalation-rule-text">
          <strong>Safety Invariant #2:</strong> AI never triggers automated SMS or emergency dispatches directly. High-risk escalations require an attending clinician to explicitly confirm or reject the event.
        </p>
      </div>

      <div className="alerts-layout-grid">
        {/* Left: Alert List */}
        <div className="alerts-sidebar-column">
          <div className="filter-chips-row">
            {(['ALL', 'CRITICAL', 'HIGH', 'MODERATE'] as const).map(sev => (
              <button
                key={sev}
                className={`chip-btn ${selectedFilter === sev ? 'active' : ''}`}
                onClick={() => setSelectedFilter(sev)}
              >
                {sev}
              </button>
            ))}
          </div>

          <div className="alerts-cards-list">
            {filteredAlerts.map(alert => (
              <div
                key={alert.id}
                className={`panel alert-selectable-card ${activeAlertId === alert.id ? 'selected' : ''} sev-card-${alert.severity.toLowerCase()}`}
                onClick={() => setActiveAlertId(alert.id)}
              >
                <div className="alert-card-header">
                  <SeverityBadge severity={alert.severity} />
                  <span className="alert-status-pill">{alert.status}</span>
                </div>
                <strong className="alert-card-title">{alert.title}</strong>
                <p className="alert-card-patient">
                  {alert.patient_name} <span className="muted">({alert.patient_id})</span>
                </p>
                <div className="alert-card-footer">
                  <span className="alert-time"><Clock size={12} /> {new Date(alert.timestamp).toLocaleTimeString()}</span>
                  {alert.event_id && <span className="alert-event-id">{alert.event_id}</span>}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right: Active Alert Detail & Action */}
        {activeAlert && (
          <div className="panel alert-detail-column">
            <div className="alert-detail-header">
              <div>
                <SeverityBadge severity={activeAlert.severity} />
                <h2 style={{ marginTop: 8, marginBottom: 4 }}>{activeAlert.title}</h2>
                <p className="muted">Patient: {activeAlert.patient_name} ({activeAlert.patient_id}) · Timestamp: {new Date(activeAlert.timestamp).toLocaleString()}</p>
              </div>
              <div className="alert-action-badge">
                <span className={`status-pill pill-${activeAlert.status.toLowerCase()}`}>{activeAlert.status}</span>
              </div>
            </div>

            <div className="alert-description-box">
              <p className="field-label">Clinical Situation & Finding</p>
              <p className="alert-detail-desc">{activeAlert.detail}</p>
            </div>

            {/* Decision Gate Actions */}
            {activeAlert.status === 'PENDING_CONFIRMATION' && (
              <div className="clinician-decision-box">
                <div className="decision-box-top">
                  <UserCheck size={18} className="decision-icon" />
                  <div>
                    <strong>Attending Clinician Gate</strong>
                    <p className="muted">Review the multi-factor risk synthesis below before taking clinical action.</p>
                  </div>
                </div>
                <div className="decision-buttons-row">
                  <button
                    className="primary-button btn-confirm"
                    onClick={() => handleDecision(activeAlert.id, 'CONFIRMED')}
                  >
                    <CheckCircle size={16} /> Confirm & Dispatch SMS Alert
                  </button>
                  <button
                    className="btn-reject"
                    onClick={() => handleDecision(activeAlert.id, 'REJECTED')}
                  >
                    <XCircle size={16} /> Reject Escalation
                  </button>
                </div>
              </div>
            )}

            {activeAlert.status === 'CONFIRMED' && (
              <div className="decision-result-box result-confirmed">
                <CheckCircle size={18} />
                <div>
                  <strong>Clinician Confirmed</strong>
                  <p>Single-use cryptographic confirmation token was minted. Emergency notification dispatch acknowledged.</p>
                </div>
              </div>
            )}

            {activeAlert.status === 'REJECTED' && (
              <div className="decision-result-box result-rejected">
                <XCircle size={18} />
                <div>
                  <strong>Clinician Rejected Escalation</strong>
                  <p>Attending physician determined no emergency dispatch is required. Audit log updated with rejection.</p>
                </div>
              </div>
            )}

            <div className="escalation-trace-section">
              <p className="eyebrow" style={{ marginTop: 24 }}>Audited Escalation Chain</p>
              <EscalationChain steps={activeAlert.escalation_chain} />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
